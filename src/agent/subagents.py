"""三个执行型子Agent：行业调研 / 内部知识 / 量化分析。

每个 = 一个 create_agent(ReAct)，自带工具与人设；由 Supervisor 调度。
对外暴露 run_research / run_knowledge / run_analysis，均带 @degrade 兜底
(单个子Agent 失败不拖垮整图)。
"""
from datetime import date
from langchain.agents import create_agent
from src.models.factory import reasoning_model
from src.agent.tools import search_meeting_minutes, list_kb_files
from src.agent.analysis_tools import ANALYSIS_TOOLS
from src.utils.config import search_conf
from src.utils.robust import degrade
from src.utils.logger import logger
from src.utils.stream import emit_event, summarize_tool_result

_research = _knowledge = _analysis = None


def _today() -> str:
    return f"今天是 {date.today().isoformat()}，涉及最新信息以此为准，勿用过时年份。"


def _build_research():
    tools = []
    try:
        from langchain_tavily import TavilySearch
        tools.append(TavilySearch(max_results=search_conf.get("max_results", 5)))
    except Exception as e:
        logger.warning(f"[subagents] Tavily 不可用: {e}")
    return create_agent(
        model=reasoning_model,
        system_prompt=f"你是行业调研专家。{_today()} 用联网搜索收集与问题相关的"
                      f"行业现状、市场数据、政策动态，输出要点并附来源链接。",
        tools=tools,
    )


def _build_knowledge():
    return create_agent(
        model=reasoning_model,
        system_prompt="你是商会内部知识专家。用 search_meeting_minutes 检索内部会议纪要、"
                      "区域招商政策、会员经验、用户上传资料；问'有哪些文件'用 list_kb_files。"
                      "严格只依据检索到的内容输出要点，检索不到就如实说'内部资料未提及'，绝不编造或脑补。",
        tools=[search_meeting_minutes, list_kb_files],
    )


def _build_analysis():
    return create_agent(
        model=reasoning_model,
        system_prompt="你是投资量化分析师。根据问题自主选择调用分析工具"
                      "(市场概况/ROI/风险/成本/方案对比/政策红利)，输出关键量化结论。"
                      "注意：工具为模拟数据，结论需标注'基于模拟测算'。",
        tools=ANALYSIS_TOOLS,
    )


def _run(agent, instruction: str, key: str) -> str:
    """流式执行子Agent：原生思考链(reasoning) + 工具(入参) + 可读返回 + 结论，经 emit_event 推送。

    key = 该专家的状态键(research/analysis/knowledge)，前端据此把事件归到对应步骤(并行时不串)。
    """
    final = ""
    for mode, data in agent.stream(
        {"messages": [{"role": "user", "content": instruction}]},
        stream_mode=["messages", "updates"],
    ):
        if mode == "messages":                                  # qwq-plus 原生思考链(流式)
            chunk = data[0] if isinstance(data, tuple) else data
            rc = (getattr(chunk, "additional_kwargs", {}) or {}).get("reasoning_content")
            if isinstance(rc, str) and rc:
                emit_event({"type": "reasoning", "agent": key, "delta": rc})
        elif mode == "updates":
            for _node, upd in (data or {}).items():
                if not isinstance(upd, dict):
                    continue
                for msg in upd.get("messages", []) or []:
                    mtype = getattr(msg, "type", None)
                    content = getattr(msg, "content", "") or ""
                    for tc in getattr(msg, "tool_calls", None) or []:   # 工具调用 + 入参
                        emit_event({"type": "tool", "agent": key, "tool": tc.get("name", ""),
                                    "args": tc.get("args", {})})
                    if mtype == "tool":                                  # 工具返回(可读)
                        emit_event({"type": "tool_result", "agent": key,
                                    "tool": getattr(msg, "name", ""),
                                    "preview": summarize_tool_result(str(content))})
                    if mtype == "ai" and content and not getattr(msg, "tool_calls", None):
                        final = content                                  # 最终结论
    return str(final).strip()


@degrade("（行业调研环节暂无结果）")
def run_research(query: str) -> str:
    global _research
    if _research is None:
        _research = _build_research()
    return _run(_research, f"针对企业问题：{query}\n请联网检索相关行业/政策/市场最新动态，给出要点与来源。", "research")


@degrade("（内部知识环节暂无结果）")
def run_knowledge(query: str) -> str:
    global _knowledge
    if _knowledge is None:
        _knowledge = _build_knowledge()
    return _run(_knowledge, f"针对企业问题：{query}\n请检索商会内部资料，给出相关内部信息要点。", "knowledge")


@degrade("（量化分析环节暂无结果）")
def run_analysis(query: str) -> str:
    global _analysis
    if _analysis is None:
        _analysis = _build_analysis()
    return _run(_analysis, f"针对企业问题：{query}\n请调用分析工具给出市场/ROI/风险/方案对比等量化结论。", "analysis")
