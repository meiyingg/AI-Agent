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

# 把项目根加入 sys.path, 保证无论从哪启动都能 import src / server
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.graph.supervisor import InvestmentAdvisor
from src.memory.profile import load_profile, save_profile
from src.memory.threads import list_threads, touch_thread
from src.utils.logger import logger

app = FastAPI(title="商会企业投资顾问 API", version="1.0")

# 开发期放开跨域 (前端 :3000 调后端 :8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.get("/api/health")
def health():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
