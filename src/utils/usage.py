"""LLM / 向量 用量 + 真实成本记录 + 工具调用日志(运营监控数据源)。

- 挂在 ChatTongyi 上(factory.py)→ 捕获所有 qwen 对话/推理调用的真实 token;
- 包一层 dashscope.TextEmbedding.call → 捕获向量化的**精确** token(LangChain 默认丢弃);
- 每条按真实价表算成本:内存累计(/api/usage)+ **异步落 Neon**(usage_log);
- 工具调用 → tool_log(供"Agent/工具统计"面板)。
"""
import queue
import threading
from contextvars import ContextVar

from langchain_core.callbacks import BaseCallbackHandler
from src.utils.pricing import cost_yuan
from src.utils.logger import logger

_lock = threading.Lock()
_totals = {"calls": 0, "in_tokens": 0, "out_tokens": 0, "yuan": 0.0, "unpriced": 0}

# 当前请求的会话 id(请求线程内有效;后台转写线程为 None)
_thread_ctx: ContextVar = ContextVar("usage_thread", default=None)


def set_thread(tid) -> None:
    _thread_ctx.set(tid)


def usage_totals() -> dict:
    with _lock:
        return dict(_totals)


def reset_usage() -> None:
    with _lock:
        _totals.update(calls=0, in_tokens=0, out_tokens=0, yuan=0.0, unpriced=0)


# ---------------- 异步写库(不卡用户请求) ----------------

_q: "queue.Queue" = queue.Queue()
_worker_started = False
_wlock = threading.Lock()


def _worker():
    from src.utils import db
    while True:
        kind, args = _q.get()
        try:
            if kind == "usage":
                db.usage_insert(*args)
            elif kind == "tool":
                db.tool_insert(*args)
        except Exception as e:
            logger.warning(f"[usage] 写库失败: {e}")
        finally:
            _q.task_done()


def _ensure_worker():
    global _worker_started
    if not _worker_started:
        with _wlock:
            if not _worker_started:
                threading.Thread(target=_worker, daemon=True).start()
                _worker_started = True


def _enqueue(kind, args):
    from src.utils import db
    if not db.USE_DB:
        return
    _ensure_worker()
    _q.put((kind, args))


# ---------------- 统一记录:内存累计 + 异步落库 ----------------

def _record(model: str, kind: str, in_t: int, out_t: int) -> None:
    c = cost_yuan(model, in_t, out_t)
    with _lock:
        _totals["calls"] += 1
        _totals["in_tokens"] += in_t
        _totals["out_tokens"] += out_t
        if c is None:
            _totals["unpriced"] += 1
        else:
            _totals["yuan"] += c
        running = _totals["yuan"]
    _enqueue("usage", (model or "?", kind, in_t, out_t, c or 0.0, _thread_ctx.get()))
    logger.info(f"[cost] {model or '?'}({kind}) in={in_t} out={out_t} " +
                (f"≈¥{c:.4f} 累计¥{running:.4f}" if c is not None else "(无价表)"))


def log_tool(agent: str, tool: str) -> None:
    """工具调用落库(供 Agent/工具统计面板)。"""
    _enqueue("tool", (agent or "", tool or "", _thread_ctx.get()))


# ---------------- 对话/推理模型:回调捕获 token ----------------

def _tokens_from(response):
    """从 LLMResult 尽量取 (in_tokens, out_tokens),兼容流式 / 不同返回形态。"""
    lo = getattr(response, "llm_output", None) or {}
    tu = lo.get("token_usage") or lo.get("usage") or {}
    in_t = tu.get("input_tokens") or tu.get("prompt_tokens") or 0
    out_t = tu.get("output_tokens") or tu.get("completion_tokens") or 0
    if in_t or out_t:
        return int(in_t), int(out_t)
    try:
        gen = response.generations[0][0]
        msg = getattr(gen, "message", None)
        um = getattr(msg, "usage_metadata", None) or {}
        in_t = um.get("input_tokens", 0)
        out_t = um.get("output_tokens", 0)
        if not (in_t or out_t):
            tu2 = (getattr(msg, "response_metadata", None) or {}).get("token_usage", {})
            in_t = tu2.get("input_tokens", 0) or tu2.get("prompt_tokens", 0)
            out_t = tu2.get("output_tokens", 0) or tu2.get("completion_tokens", 0)
    except Exception:
        pass
    return int(in_t or 0), int(out_t or 0)


class CostCallbackHandler(BaseCallbackHandler):
    """记录每次对话/推理 LLM 调用的真实 token + 成本。"""

    raise_error = False                     # 回调异常绝不拖垮主流程

    def __init__(self, default_model: str = ""):
        self._model_by_run = {}             # run_id -> model name
        self.default_model = default_model  # 兜底:该 handler 绑定的模型名

    def _remember_model(self, run_id, kwargs):
        params = kwargs.get("invocation_params") or {}
        model = params.get("model") or params.get("model_name") or ""
        if run_id is not None:
            self._model_by_run[run_id] = model

    def on_chat_model_start(self, serialized, messages, *, run_id=None, **kwargs):
        self._remember_model(run_id, kwargs)

    def on_llm_start(self, serialized, prompts, *, run_id=None, **kwargs):
        self._remember_model(run_id, kwargs)

    def on_llm_end(self, response, *, run_id=None, **kwargs):
        in_t, out_t = _tokens_from(response)
        if not (in_t or out_t):
            return
        model = (self._model_by_run.pop(run_id, "") or
                 (getattr(response, "llm_output", None) or {}).get("model_name", "") or
                 self.default_model)
        kind = "reason" if "qwq" in (model or "").lower() else "chat"
        _record(model, kind, in_t, out_t)


# ---------------- 向量化:包 dashscope.TextEmbedding.call 抓精确 token ----------------

def _install_embedding_hook():
    """LangChain 的 DashScopeEmbeddings 把 API 的 usage 丢了;在底层 SDK 这一层兜住,拿精确 token。"""
    try:
        import dashscope
        if getattr(dashscope.TextEmbedding, "_cost_hooked", False):
            return
        _orig = dashscope.TextEmbedding.call

        def _patched(*args, **kwargs):
            resp = _orig(*args, **kwargs)
            try:
                u = getattr(resp, "usage", None) or {}
                tot = u.get("total_tokens") if isinstance(u, dict) else getattr(u, "total_tokens", 0)
                if tot:
                    model = kwargs.get("model") or (args[0] if args else "") or "text-embedding-v4"
                    _record(model, "embed", int(tot), 0)
            except Exception:
                pass
            return resp

        dashscope.TextEmbedding.call = _patched
        dashscope.TextEmbedding._cost_hooked = True
        logger.info("[cost] embedding hook installed (dashscope.TextEmbedding.call)")
    except Exception as e:
        logger.warning(f"[cost] embedding hook 安装失败: {e}")


_install_embedding_hook()
