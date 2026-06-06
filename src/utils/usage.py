"""LLM 用量 / 成本回调。

挂在 ChatTongyi 上(见 factory.py)→ 覆盖所有 qwen 调用:
每次调用结束读真实 token 用量,按 pricing 真实价表算成本,线程安全累计 + 打日志。
LangSmith 自身也会追踪(走环境变量),这里是"我们自己算的、确定性的真实成本"。
"""
import threading

from langchain_core.callbacks import BaseCallbackHandler
from src.utils.pricing import cost_yuan
from src.utils.logger import logger

_lock = threading.Lock()
_totals = {"calls": 0, "in_tokens": 0, "out_tokens": 0, "yuan": 0.0, "unpriced": 0}


def usage_totals() -> dict:
    """累计用量与成本(供 /api/usage 或日志展示)。"""
    with _lock:
        return dict(_totals)


def reset_usage() -> None:
    with _lock:
        _totals.update(calls=0, in_tokens=0, out_tokens=0, yuan=0.0, unpriced=0)


def _tokens_from(response):
    """从 LLMResult 尽量取 (in_tokens, out_tokens),兼容流式 / 不同返回形态。"""
    lo = getattr(response, "llm_output", None) or {}
    tu = lo.get("token_usage") or lo.get("usage") or {}
    in_t = tu.get("input_tokens") or tu.get("prompt_tokens") or 0
    out_t = tu.get("output_tokens") or tu.get("completion_tokens") or 0
    if in_t or out_t:
        return int(in_t), int(out_t)
    try:                                    # 回退:generations 里的 message 元数据
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
    """记录每次 LLM 调用的真实 token + 成本。"""

    raise_error = False                     # 回调异常绝不拖垮主流程

    def __init__(self, default_model: str = ""):
        self._model_by_run = {}             # run_id -> model name(start 时记下,end 时用)
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
        c = cost_yuan(model, in_t, out_t)
        with _lock:
            _totals["calls"] += 1
            _totals["in_tokens"] += in_t
            _totals["out_tokens"] += out_t
            if c is None:
                _totals["unpriced"] += 1
            else:
                _totals["yuan"] += c
        logger.info(f"[cost] {model or '?'} in={in_t} out={out_t} " +
                    (f"≈¥{c:.4f}  累计¥{_totals['yuan']:.4f}" if c is not None else "(无价表, 未计费)"))


_handler = None


def cost_handler() -> CostCallbackHandler:
    """全局单例,挂到模型上。"""
    global _handler
    if _handler is None:
        _handler = CostCallbackHandler()
    return _handler
