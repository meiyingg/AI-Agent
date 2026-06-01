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
from src.rag.kb_service import kind_of, process_upload, list_docs, delete_doc, search_chunks, get_doc_text
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


def _kb_job(job_id: str, raw_path: str, name: str):
    """后台任务：音视频转写 + 入库(慢)。"""
    try:
        doc = process_upload(raw_path, name)
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
        raw_path = os.path.join(up_dir, f"{uuid.uuid4().hex[:8]}_{os.path.basename(name)}")
        with open(raw_path, "wb") as out:
            shutil.copyfileobj(f.file, out)        # 流式落盘, 大文件也不爆内存
        if kind == "doc":
            try:
                doc = process_upload(raw_path, name)
                results.append({"name": name, "status": "done", "doc": doc})
            except Exception as e:
                logger.exception(f"[KB] 文档处理失败 {name}")
                results.append({"name": name, "status": "error", "error": str(e)})
            finally:
                _discard(raw_path)
        else:                                       # 音视频 → 后台转写
            job_id = uuid.uuid4().hex[:10]
            KB_JOBS[job_id] = {"id": job_id, "name": name, "kind": kind, "status": "processing"}
            threading.Thread(target=_kb_job, args=(job_id, raw_path, name), daemon=True).start()
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


@app.on_event("startup")
def _bootstrap_kb():
    """部署首启：后台把示例语料(data/samples)灌入向量库，让"内部知识"演示有内容。

    幂等：已入库的内容按 MD5 跳过；后台线程执行，不阻塞启动；失败仅记日志(不崩)。
    """
    def _run():
        try:
            from src.rag.meeting_kb import MeetingKB
            logger.info(f"[startup] KB ingest: {MeetingKB().ingest()}")
        except Exception as e:
            logger.warning(f"[startup] KB ingest skipped: {e}")
    threading.Thread(target=_run, daemon=True).start()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
