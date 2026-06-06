"""向 LangGraph 自定义事件流推送进度事件 (供前端实时展示"内部怎么执行")。

在图的任意节点(含子Agent调用)里调用 emit_event(...)，事件会经
stream_mode=["updates","custom"] 的 "custom" 通道实时流出；
若当前不在 custom 流式上下文中(如 .invoke / CLI)，则自动 no-op。
"""


def emit_event(event: dict) -> None:
    if isinstance(event, dict) and event.get("type") == "tool":   # 工具调用 → 落 tool_log(运营监控)
        try:
            from src.utils.usage import log_tool
            log_tool(event.get("agent", ""), event.get("tool", ""))
        except Exception:
            pass
    try:
        from langgraph.config import get_stream_writer
        get_stream_writer()(event)
    except Exception:
        pass  # 非 custom 流式上下文 -> 静默忽略


def summarize_tool_result(raw: str) -> str:
    """把工具返回整理成可读文本：tavily 搜索结果取 概要 + 各条标题/摘要；其余原样截断。

    供 general(通用助手) 与 子Agent 复用，避免前端看到一坨 JSON。
    """
    import json
    try:
        d = json.loads(raw)
    except Exception:
        return raw[:800]
    if not isinstance(d, dict):
        return raw[:800]
    parts = []
    if d.get("answer"):
        parts.append(f"Summary: {d['answer']}\n")
    for i, r in enumerate(d.get("results") or [], 1):       # 显示全部结果
        title = r.get("title", "")
        content = str(r.get("content", "")).strip()[:350]
        url = r.get("url", "")
        parts.append(f"{i}. {title}\n   {content}\n   🔗 {url}")
    return "\n".join(parts) if parts else raw[:800]
