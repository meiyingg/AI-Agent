"""FastAPI 后端：把多Agent投资顾问 + 记忆 暴露为 HTTP/SSE 接口, 供前端消费。

接口：
- POST /api/chat            对话(SSE 流式)，转发结构化事件 triage/agent_done/message/final/done
- GET  /api/memory          读全局企业档案(长期记忆)
- PUT  /api/memory          手改全局档案
- GET  /api/threads/{id}    读某会话历史(短期记忆)
- GET  /api/health          健康检查

短期记忆按 thread_id 隔离(checkpointer)，长期记忆是全局单一档案。
"""
import os
import sys
import json
import uuid
import shutil
import threading

# 把项目根加入 sys.path, 保证无论从哪启动都能 import src / server
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from src.graph.supervisor import InvestmentAdvisor
from src.memory.profile import load_profile, save_profile
from src.memory.threads import list_threads, touch_thread
from src.memory.reports import save_report, list_reports, get_report, delete_report
from src.rag.kb_service import (
    kind_of, process_upload, list_docs, delete_doc, search_chunks, get_doc_text, get_original_url,
    find_doc_by_filehash,
)
from src.utils import db
from src.utils.files import sha256_of_file
from src.utils.config import (
    abs_of, update_settings,
    model_conf, memory_conf, multiagent_conf, kb_conf,
)
from src.utils.logger import logger

app = FastAPI(title="Chamber Investment Advisor API", version="1.0")

# 开发期放开跨域 (前端 :3000 调后端 :8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- 访问口令：保护后端，防止公网被人直接刷 API / 烧 quota ----
# 仅当设置了环境变量 APP_PASSWORD 时启用；未设则放行(本地开发不受影响)。
# 口令值放在部署平台(Render)的环境变量里，绝不写进代码库。
APP_USER = os.getenv("APP_USER", "admin")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
_OPEN_PATHS = {"/api/health", "/api/login"}


@app.middleware("http")
async def _access_gate(request, call_next):
    if APP_PASSWORD and request.method != "OPTIONS":
        p = request.url.path
        if p.startswith("/api/") and p not in _OPEN_PATHS:
            if request.headers.get("X-Access-Code") != APP_PASSWORD:
                # 本中间件在 CORS 外层，手动补 CORS 头，确保浏览器能读到这个 401
                return JSONResponse(
                    {"detail": "Unauthorized"}, status_code=401,
                    headers={"Access-Control-Allow-Origin": "*"},
                )
    return await call_next(request)


class LoginReq(BaseModel):
    username: str
    password: str


@app.post("/api/login")
def login(req: LoginReq):
    """校验账号口令。未配置 APP_PASSWORD 时(本地)直接放行。"""
    if APP_PASSWORD and (req.username != APP_USER or req.password != APP_PASSWORD):
        return JSONResponse({"ok": False, "detail": "Wrong username or password"}, status_code=401)
    return {"ok": True}


# 单例：持有 checkpointer(短期记忆)与图，进程内复用
advisor = InvestmentAdvisor()


class ChatReq(BaseModel):
    message: str
    thread_id: str | None = None


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@app.post("/api/chat")
def chat(req: ChatReq):
    """对话：SSE 流式返回结构化事件。前端据此渲染左对话 + 右工作台。"""
    tid = req.thread_id or uuid.uuid4().hex[:8]
    touch_thread(tid, req.message)               # 登记/更新会话注册表

    def gen():
        from src.utils.usage import set_thread
        set_thread(tid)                          # 本次会话 id → 成本/工具记录按会话归属
        yield _sse({"type": "thread", "thread_id": tid})
        try:
            for ev in advisor.execute_events(req.message, thread_id=tid):
                if ev.get("type") == "final" and ev.get("report"):
                    try:
                        save_report(tid, req.message, ev.get("report") or {}, ev.get("findings") or {})
                    except Exception:
                        logger.warning("[Reports] 保存失败")
                yield _sse(ev)
            advisor.maybe_learn(tid)          # 阶段3b: 对话结束自动提炼(默认关)
        except Exception as e:
            logger.exception("[/api/chat] 流式出错")
            yield _sse({"type": "error", "message": str(e)})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/memory")
def get_memory():
    """读全局企业档案(长期记忆)。"""
    return load_profile()


@app.put("/api/memory")
def put_memory(data: dict):
    """手改全局档案(长期记忆)。支持部分字段。"""
    return save_profile(data)


@app.get("/api/threads")
def get_threads():
    """历史会话列表(供前端左侧会话栏)。"""
    return list_threads()


@app.get("/api/threads/{thread_id}")
def get_thread(thread_id: str):
    """读某会话历史(短期记忆), 供前端恢复对话。"""
    msgs = advisor.get_messages(thread_id)
    return {
        "thread_id": thread_id,
        "messages": [
            {"role": getattr(m, "type", "?"), "content": getattr(m, "content", "")}
            for m in msgs if getattr(m, "content", "")
        ],
    }


# ============================================================
# 知识库上传 (公司内部资料 → RAG)
# ============================================================
KB_JOBS: dict = {}   # job_id -> {id, name, kind, status, error?, doc?}


def _discard(path: str) -> None:
    """删除原始上传文件：提取/转写后的文本已存入 kb_dir，原文件不再被使用。"""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        logger.warning(f"[KB] 清理原始上传失败: {path}")


def _r2_store(raw_path: str, raw_name: str) -> str:
    """把原始文件存到 R2(设了 R2 才存)。返回 r2_key 或空串。"""
    if not db.USE_R2:
        return ""
    try:
        with open(raw_path, "rb") as fh:
            db.r2_put(f"original/{raw_name}", fh.read())
        return f"original/{raw_name}"
    except Exception as e:
        logger.warning(f"[KB] R2 存原件失败 {raw_name}: {e}")
        return ""


def _kb_job(job_id: str, raw_path: str, name: str, r2_key: str = "", file_hash: str = ""):
    """后台任务：音视频转写 + 入库(慢)。"""
    try:
        doc = process_upload(raw_path, name, r2_key, file_hash)
        KB_JOBS[job_id] = {**KB_JOBS[job_id], "status": "done", "doc": doc}
    except Exception as e:
        logger.exception(f"[KB] 后台处理失败 {name}")
        KB_JOBS[job_id] = {**KB_JOBS[job_id], "status": "error", "error": str(e)}
    finally:
        _discard(raw_path)


@app.post("/api/kb/upload")
async def kb_upload(files: list[UploadFile] = File(...)):
    """上传文件入知识库。文档同步入库；音视频转后台任务(返回 job_id 轮询)。"""
    up_dir = abs_of("uploads_dir")
    os.makedirs(up_dir, exist_ok=True)
    results = []
    for f in files:
        name = f.filename or "file"
        kind = kind_of(name)
        if not kind:
            results.append({"name": name, "status": "error", "error": "Unsupported file type"})
            continue
        raw_name = f"{uuid.uuid4().hex[:8]}_{os.path.basename(name)}"
        raw_path = os.path.join(up_dir, raw_name)
        with open(raw_path, "wb") as out:
            shutil.copyfileobj(f.file, out)        # 流式落盘, 大文件也不爆内存
        # ① 文件字节指纹预检：完全相同的文件之前传过 → 当场跳过(不上传 R2、不抽取/转写)
        file_hash = sha256_of_file(raw_path) or ""
        dup_doc = find_doc_by_filehash(file_hash)
        if dup_doc:
            logger.info(f"[KB] 跳过重复(同一个文件已存在): {name}")
            results.append({"name": name, "status": "done", "doc": dup_doc, "duplicate": True})
            _discard(raw_path)
            continue
        r2_key = _r2_store(raw_path, raw_name)     # 原件存 R2(可下载)
        if kind == "doc":
            try:
                doc = process_upload(raw_path, name, r2_key, file_hash)
                results.append({"name": name, "status": "done", "doc": doc})
            except Exception as e:
                logger.exception(f"[KB] 文档处理失败 {name}")
                results.append({"name": name, "status": "error", "error": str(e)})
            finally:
                _discard(raw_path)
        else:                                       # 音视频 → 后台转写
            job_id = uuid.uuid4().hex[:10]
            KB_JOBS[job_id] = {"id": job_id, "name": name, "kind": kind, "status": "processing"}
            threading.Thread(target=_kb_job, args=(job_id, raw_path, name, r2_key, file_hash), daemon=True).start()
            results.append({"name": name, "status": "processing", "job_id": job_id, "kind": kind})
    return {"results": results}


@app.get("/api/kb/jobs/{job_id}")
def kb_job_status(job_id: str):
    return KB_JOBS.get(job_id, {"id": job_id, "status": "unknown"})


@app.get("/api/kb/docs")
def kb_list():
    return {"docs": list_docs()}


@app.get("/api/kb/docs/{doc_id}/content")
def kb_doc_content(doc_id: str):
    """查看某份已入库资料的提取文本(AI 实际读到的内容)。"""
    return {"text": get_doc_text(doc_id) or ""}


@app.get("/api/kb/docs/{doc_id}/original")
def kb_doc_original(doc_id: str):
    """原始文件的临时下载链接(存在 R2 才有)。"""
    url = get_original_url(doc_id)
    if not url:
        return JSONResponse({"detail": "No original file"}, status_code=404)
    return {"url": url}


@app.delete("/api/kb/docs/{doc_id}")
def kb_delete(doc_id: str):
    delete_doc(doc_id)
    return {"ok": True}


class KbSearchReq(BaseModel):
    query: str


@app.post("/api/kb/search")
def kb_search(req: KbSearchReq):
    """RAG 检索预览：返回命中的片段(透明展示混合检索+重排)。"""
    return {"results": search_chunks(req.query)}


# ============================================================
# 概览统计 + 设置
# ============================================================
@app.get("/api/stats")
def get_stats():
    docs = list_docs()
    prof = load_profile()
    return {
        "kb": {
            "files": len(docs),
            "chars": sum(d.get("chars", 0) for d in docs),
            "chunks": sum(d.get("chunks", 0) for d in docs),
        },
        "threads": len(list_threads()),
        "profile": {"has": bool(prof.get("profile")), "facts": len(prof.get("facts") or [])},
        "models": {
            "chat": model_conf.get("chat_model_name"),
            "reasoning": model_conf.get("reasoning_model_name"),
            "embedding": model_conf.get("embedding_model_name"),
        },
    }


@app.get("/api/settings")
def get_settings():
    return {"model": model_conf, "memory": memory_conf, "multiagent": multiagent_conf, "kb": kb_conf}


class SettingsPatch(BaseModel):
    section: str
    patch: dict


@app.put("/api/settings")
def put_settings(body: SettingsPatch):
    return update_settings(body.section, body.patch)


@app.get("/api/reports")
def get_reports():
    return list_reports()


@app.get("/api/reports/{rid}")
def get_report_detail(rid: str):
    return get_report(rid) or {}


@app.delete("/api/reports/{rid}")
def del_report(rid: str):
    delete_report(rid)
    return {"ok": True}


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/usage")
def api_usage():
    """LLM 真实用量与成本:qwen token 用量按 DashScope 官方价表实时累计(元)。"""
    from src.utils.usage import usage_totals
    from src.utils import pricing
    return {**usage_totals(), "endpoint": "intl (Singapore)",
            "prices_per_million_yuan": pricing.PRICING}


@app.get("/api/admin/usage/summary")
def admin_usage_summary():
    """总计 + 今日 + 按模型拆分(持久化, 来自 usage_log)。"""
    from src.utils import db
    return db.usage_summary()


@app.get("/api/admin/usage/timeseries")
def admin_usage_timeseries(days: int = 14):
    """近 N 天每天的成本 / tokens / 调用数。"""
    from src.utils import db
    return {"series": db.usage_timeseries(days)}


@app.get("/api/admin/usage/recent")
def admin_usage_recent(limit: int = 50):
    """最近 N 次调用流水。"""
    from src.utils import db
    return {"rows": db.usage_recent(limit)}


@app.get("/api/admin/usage/tools")
def admin_usage_tools():
    """Agent / 工具调用统计。"""
    from src.utils import db
    return db.tool_stats()


# ---- Eval (RAGAS,子进程运行 eval/run_eval.py) ----
EVAL_STATUS: dict = {"state": "idle", "msg": ""}


def _eval_job(limit: int):
    import subprocess
    EVAL_STATUS.update(state="running", msg=f"running (limit={limit or 'all'})…")
    try:
        cmd = [sys.executable, os.path.join(_ROOT, "eval", "run_eval.py")]
        if limit:
            cmd += ["--limit", str(limit)]
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=_ROOT, timeout=1800)
        EVAL_STATUS.update(state="done" if p.returncode == 0 else "error",
                           msg="done" if p.returncode == 0 else (p.stderr or p.stdout or "")[-400:])
    except Exception as e:
        EVAL_STATUS.update(state="error", msg=str(e)[:400])


@app.get("/api/admin/eval/latest")
def admin_eval_latest():
    """最近一次 RAG 评测结果(分卡 + 每题),供 Eval 页展示。"""
    p = os.path.join(_ROOT, "eval", "last_result.json")
    if not os.path.exists(p):
        return {"summary": {}, "items": [], "ts": None, "n": 0}

    def _nn(o):                              # NaN → None,保证返回合法 JSON(NaN 会让浏览器解析崩)
        if isinstance(o, float) and o != o:
            return None
        if isinstance(o, dict):
            return {k: _nn(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_nn(v) for v in o]
        return o
    try:
        with open(p, encoding="utf-8") as f:
            return _nn(json.load(f))
    except Exception:
        return {"summary": {}, "items": [], "ts": None, "n": 0}


@app.get("/api/admin/eval/status")
def admin_eval_status():
    return EVAL_STATUS


@app.post("/api/admin/eval/run")
def admin_eval_run(limit: int = 5):
    """后台跑一次评测(子进程,不阻塞)。limit=0 = 全量。"""
    if EVAL_STATUS.get("state") == "running":
        return {"state": "running"}
    threading.Thread(target=_eval_job, args=(limit,), daemon=True).start()
    return {"state": "started", "limit": limit}


# 启动时打印可观测/计费状态
_ls_on = (os.getenv("LANGSMITH_TRACING") or "").lower() == "true" and bool(os.getenv("LANGSMITH_API_KEY"))
logger.info("[obs] LangSmith tracing " + (
    f"ON · project={os.getenv('LANGSMITH_PROJECT') or 'default'}" if _ls_on
    else "OFF (设 LANGSMITH_TRACING=true + LANGSMITH_API_KEY 开启)"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
