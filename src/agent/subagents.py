"""三个执行型子Agent：行业调研 / 内部知识 / 量化分析。

每个 = 一个 create_agent(ReAct)，自带工具与人设；由 Supervisor 调度。
对外暴露 run_research / run_knowledge / run_analysis，均带 @degrade 兜底
(单个子Agent 失败不拖垮整图)。
"""
from datetime import date
from langchain.agents import create_agent
from src.models.factory import reasoning_model
from src.agent.tools import search_meeting_minutes, list_kb_files
from src.agent.code_tools import run_python
from src.utils.config import search_conf
from src.utils.robust import degrade
from src.utils.logger import logger
from src.utils.stream import emit_event, summarize_tool_result

_research = _knowledge = _analysis = None


def _today() -> str:
    return f"Today is {date.today().isoformat()}; treat it as the reference for the latest info, and do not use stale years."


def _build_research():
    tools = []
    try:
        from langchain_tavily import TavilySearch
        tools.append(TavilySearch(max_results=search_conf.get("max_results", 5)))
    except Exception as e:
        logger.warning(f"[subagents] Tavily 不可用: {e}")
    return create_agent(
        model=reasoning_model,
        system_prompt=f"You are an industry-research expert. {_today()} Use web search to gather the "
                      f"industry status, market data, and policy developments relevant to the question, "
                      f"and output key points with source links.",
        tools=tools,
    )


def _build_knowledge():
    return create_agent(
        model=reasoning_model,
        system_prompt="You are the chamber's internal-knowledge expert. Use search_meeting_minutes to retrieve "
                      "internal meeting minutes, regional investment-promotion policies, member experience, and "
                      "user-uploaded materials; for 'what files are there' use list_kb_files. "
                      "Output key points strictly and only from what you retrieve; if nothing is found, honestly say "
                      "'not mentioned in internal materials' — never fabricate or guess.",
        tools=[search_meeting_minutes, list_kb_files],
    )


def _build_analysis():
    return create_agent(
        model=reasoning_model,
        system_prompt="You are a data & computation analyst. For any quantitative question — math, statistics, "
                      "financial modelling, ROI/payback, data crunching, option comparison — write Python and run it "
                      "with the run_python tool instead of computing in your head; then explain the result in "
                      "plain words. Write COMPLETE self-contained snippets and print() what you want to see; numpy and "
                      "pandas are available. State any assumptions you had to make about the inputs.",
        tools=[run_python],
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


@degrade("(No results from the industry-research step.)")
def run_research(query: str) -> str:
    global _research
    if _research is None:
        _research = _build_research()
    return _run(_research, f"For the company question: {query}\nSearch the web for the latest relevant industry/policy/market developments, and give key points with sources.", "research")


@degrade("(No results from the internal-knowledge step.)")
def run_knowledge(query: str) -> str:
    global _knowledge
    if _knowledge is None:
        _knowledge = _build_knowledge()
    return _run(_knowledge, f"For the company question: {query}\nSearch the chamber's internal materials and give the relevant internal key points.", "knowledge")


@degrade("(No results from the quant-analysis step.)")
def run_analysis(query: str) -> str:
    global _analysis
    if _analysis is None:
        _analysis = _build_analysis()
    return _run(_analysis, f"For the company question: {query}\nCall the analysis tools to give quantitative conclusions on market / ROI / risk / option comparison, etc.", "analysis")
