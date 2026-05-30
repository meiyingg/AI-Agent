"""统一智能助手 ReAct Agent。

一个 Agent 带两类能力的工具，由模型自动判断走哪边：
- 内部问题  -> search_meeting_minutes (高级 RAG)
- 外部/最新 -> tavily_search (LangChain 官方在线检索工具)
- 出报告    -> generate_decision_report (触发报告模式)
"""
from langchain.agents import create_agent
from src.models.factory import reasoning_model
from src.utils.paths import get_abs_path
from src.utils.files import read_text
from src.utils.config import agent_conf, search_conf
from src.utils.logger import logger
from src.agent.tools import search_meeting_minutes, generate_decision_report
from src.agent.middleware import monitor_tool, log_before_model, report_prompt_switch


def _build_tools():
    tools = [search_meeting_minutes, generate_decision_report]
    # LangChain 官方 Tavily 在线检索工具 (实时, 不落库)
    try:
        from langchain_tavily import TavilySearch
        tools.insert(1, TavilySearch(max_results=search_conf.get("max_results", 5)))
    except Exception as e:
        logger.warning(f"[Agent] Tavily 工具不可用(检查 langchain-tavily 与 TAVILY_API_KEY): {e}")
    return tools


class Assistant:
    def __init__(self):
        self.agent = create_agent(
            model=reasoning_model,
            system_prompt=read_text(get_abs_path(agent_conf["system_prompt_path"])),
            tools=_build_tools(),
            middleware=[monitor_tool, log_before_model, report_prompt_switch],
        )

    def execute_stream(self, query: str = None, messages=None):
        # messages 传入则带上对话历史 (短期记忆); 否则按单句 query 构造
        msgs = messages if messages is not None else [{"role": "user", "content": query}]
        input_dict = {"messages": msgs}
        for chunk in self.agent.stream(input_dict, stream_mode="values", context={"report": False}):
            latest = chunk["messages"][-1]
            if latest.content:
                yield latest.content.strip() + "\n"

    def execute(self, query: str = None, messages=None) -> str:
        last = ""
        for chunk in self.execute_stream(query=query, messages=messages):
            last = chunk
        return last

    def stream_run(self, messages):
        """流式执行：('reasoning',思考链) / ('token',答案) / ('tool',名,入参) / ('result',名,可读返回) / ('final',最终答)。

        reasoning = qwq-plus 的原生思考链(Gemini 式)；token = 答案打字机；tool/result = 工具轨迹。
        """
        from src.utils.stream import summarize_tool_result
        final_answer = ""
        for mode, data in self.agent.stream(
            {"messages": messages}, stream_mode=["messages", "updates"], context={"report": False}
        ):
            if mode == "messages":
                chunk = data[0] if isinstance(data, tuple) else data
                ak = getattr(chunk, "additional_kwargs", {}) or {}
                rc = ak.get("reasoning_content")
                if isinstance(rc, str) and rc:
                    yield ("reasoning", rc)
                txt = getattr(chunk, "content", "")
                if isinstance(txt, str) and txt:
                    yield ("token", txt)
            elif mode == "updates":
                for _node, upd in (data or {}).items():
                    if not isinstance(upd, dict):
                        continue
                    for msg in upd.get("messages", []) or []:
                        for tc in getattr(msg, "tool_calls", None) or []:
                            yield ("tool", tc.get("name", ""), tc.get("args", {}))
                        if getattr(msg, "type", None) == "tool":
                            yield ("result", getattr(msg, "name", ""),
                                   summarize_tool_result(str(getattr(msg, "content", ""))))
                        if (getattr(msg, "type", None) == "ai"
                                and getattr(msg, "content", "")
                                and not getattr(msg, "tool_calls", None)):
                            final_answer = msg.content
        yield ("final", final_answer)


if __name__ == "__main__":
    a = Assistant()
    for c in a.execute_stream("跨境物流方案的会议决议是什么"):
        print(c, end="", flush=True)
