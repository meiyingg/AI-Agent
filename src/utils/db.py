"""永久存储后端:Neon Postgres(kv 存储 + pgvector + 对话 checkpointer)+ Cloudflare R2(原始文件)。

设计:**全部惰性**。
- 设了环境变量 DATABASE_URL → 走云端 (USE_DB=True);没设 → 各模块回退本地文件(原行为)。
- 设了 R2_* → 上传原件到 R2;没设 → 跳过。

各 JSON 类数据(档案/报告/会话/设置/KB登记)统一存进一张 kv_store(key, value jsonb) 表,
各模块逻辑不变,只是把"读写文件"换成 store_load/store_save。
"""
import json
import logging
import os
import threading

logger = logging.getLogger("mia")
_lock = threading.Lock()

# 确保 .env 已加载(无论 import 顺序),再读环境变量
try:
    from dotenv import load_dotenv
    from src.utils.paths import get_abs_path
    load_dotenv(get_abs_path(".env"))
except Exception:
    pass

DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()
USE_DB = bool(DATABASE_URL)

R2_BUCKET = (os.getenv("R2_BUCKET") or "").strip()
USE_R2 = bool(os.getenv("R2_ENDPOINT_URL") and os.getenv("R2_ACCESS_KEY_ID") and R2_BUCKET)

_engine = None
_inited = False
_r2 = None


# ---------------- Postgres 引擎 + 初始化 ----------------

def _sa_url() -> str:
    """转成 SQLAlchemy + psycopg3 的 URL。"""
    u = DATABASE_URL
    if u.startswith("postgresql://"):
        u = "postgresql+psycopg://" + u[len("postgresql://"):]
    return u


def get_engine():
    global _engine
    if _engine is None:
        with _lock:                    # 防并发首次建多个引擎
            if _engine is None:
                from sqlalchemy import create_engine
                _engine = create_engine(
                    _sa_url(),
                    pool_pre_ping=True,        # Neon 空闲会休眠,断连自动重建
                    pool_recycle=300,
                    connect_args={"prepare_threshold": None},  # 兼容 Neon pooler(PgBouncer)
                )
    return _engine


def ready():
    """确保扩展 + kv_store 已建(幂等,只跑一次)。返回引擎。线程安全(防并发建扩展)。"""
    global _inited
    eng = get_engine()
    if not _inited:
        with _lock:                    # 双检锁:只让一个线程跑 DDL
            if not _inited:
                from sqlalchemy import text
                with eng.begin() as conn:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                    conn.execute(text("CREATE TABLE IF NOT EXISTS kv_store (key text PRIMARY KEY, value jsonb NOT NULL)"))
                _inited = True
                logger.info("[db] Postgres ready (kv_store + pgvector)")
    return eng


# ---------------- kv 存储(JSON blob) ----------------

def kv_get(key: str, default=None):
    from sqlalchemy import text
    with ready().connect() as conn:
        row = conn.execute(text("SELECT value FROM kv_store WHERE key=:k"), {"k": key}).first()
    return row[0] if row else default


def kv_set(key: str, value) -> None:
    from sqlalchemy import text
    with ready().begin() as conn:
        conn.execute(
            text("INSERT INTO kv_store(key, value) VALUES (:k, CAST(:v AS jsonb)) "
                 "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"),
            {"k": key, "v": json.dumps(value, ensure_ascii=False)},
        )


def kv_delete(key: str) -> None:
    from sqlalchemy import text
    with ready().begin() as conn:
        conn.execute(text("DELETE FROM kv_store WHERE key=:k"), {"k": key})


def registry_upsert(doc_id: str, entry: dict, file_path: str) -> None:
    """把一份文档**原子地**并入 kb_registry。

    并发上传(多个文件/后台转写线程)时,若用"读整块→改→写回整块"会互相覆盖(lost update);
    这里用 Postgres 的 jsonb `||` 合并 + 行锁,保证每条各自落库、不丢。
    """
    if USE_DB:
        from sqlalchemy import text
        with ready().begin() as conn:
            conn.execute(
                text("INSERT INTO kv_store(key, value) "
                     "VALUES ('kb_registry', jsonb_build_object(CAST(:id AS text), CAST(:e AS jsonb))) "
                     "ON CONFLICT (key) DO UPDATE "
                     "SET value = kv_store.value || jsonb_build_object(CAST(:id AS text), CAST(:e AS jsonb))"),
                {"id": doc_id, "e": json.dumps(entry, ensure_ascii=False)},
            )
    else:
        reg = store_load("kb_registry", file_path, {})
        reg[doc_id] = entry
        store_save("kb_registry", file_path, reg)


def registry_delete(doc_id: str, file_path: str) -> None:
    """从 kb_registry 原子地移除一条。"""
    if USE_DB:
        from sqlalchemy import text
        with ready().begin() as conn:
            conn.execute(text("UPDATE kv_store SET value = value - CAST(:id AS text) WHERE key='kb_registry'"),
                         {"id": doc_id})
    else:
        reg = store_load("kb_registry", file_path, {})
        reg.pop(doc_id, None)
        store_save("kb_registry", file_path, reg)


def store_load(key: str, file_path: str, default):
    """统一读:USE_DB 走 kv,否则读本地 json 文件。"""
    if USE_DB:
        v = kv_get(key, None)
        return v if v is not None else default
    try:
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def store_save(key: str, file_path: str, data) -> None:
    """统一写:USE_DB 走 kv,否则写本地 json 文件。"""
    if USE_DB:
        kv_set(key, data)
        return
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------- 对话 checkpointer ----------------

def make_checkpointer():
    """USE_DB → PostgresSaver(连接池);否则交回 None 让调用方用本地 SqliteSaver。"""
    if not USE_DB:
        return None
    from psycopg_pool import ConnectionPool
    from psycopg.rows import dict_row
    from langgraph.checkpoint.postgres import PostgresSaver
    pool = ConnectionPool(
        conninfo=DATABASE_URL, max_size=10, open=True,
        kwargs={"autocommit": True, "prepare_threshold": None, "row_factory": dict_row},
    )
    cp = PostgresSaver(pool)
    cp.setup()
    logger.info("[db] checkpointer = PostgresSaver (Neon)")
    return cp


# ---------------- Cloudflare R2(S3 兼容) ----------------

def r2_client():
    global _r2
    if _r2 is None:
        import boto3
        _r2 = boto3.client(
            "s3",
            endpoint_url=os.environ["R2_ENDPOINT_URL"],
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
        )
    return _r2


def r2_put(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    r2_client().put_object(Bucket=R2_BUCKET, Key=key, Body=data, ContentType=content_type)


def r2_presigned_url(key: str, expires: int = 3600) -> str:
    return r2_client().generate_presigned_url(
        "get_object", Params={"Bucket": R2_BUCKET, "Key": key}, ExpiresIn=expires)


def r2_delete(key: str) -> None:
    try:
        r2_client().delete_object(Bucket=R2_BUCKET, Key=key)
    except Exception as e:
        logger.warning(f"[db] R2 delete failed {key}: {e}")
