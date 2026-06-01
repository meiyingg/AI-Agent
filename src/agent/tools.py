"""自定义工具集 (会议/文档侧)。

在线检索不在这里写——直接用 LangChain 官方的 TavilySearch 工具
(在 react_agent.py 里加入工具列表)。

懒加载单例：用到才初始化，避免无谓加载模型/向量库。
"""
from langchain_core.tools import tool

_kb = None


def _meeting_kb():
    global _kb
    if _kb is None:
        from src.rag.meeting_kb import MeetingKB
        _kb = MeetingKB()
    return _kb


@tool(description="Search the company's [internal documents / meeting minutes / uploaded materials] to answer a question. Use it when the user asks about internal info like 'last meeting / a project decision / who is responsible / internal parameters / what a file says'. Arg query is the search keywords.")
def search_meeting_minutes(query: str) -> str:
    answer, sources = _meeting_kb().search_with_sources(query)
    if sources:
        answer += f"\n\n[Sources] {', '.join(sources)}"
    return answer


@tool(description="List [which uploaded files/materials currently exist] in the company knowledge base. Call it when the user asks 'what files are in the knowledge base / what materials were uploaded / which documents exist'. No args; returns the real list directly (do not invent entries).")
def list_kb_files() -> str:
    from src.rag.kb_service import list_docs
    docs = list_docs()
    if not docs:
        return "The knowledge base currently has no user-uploaded files."
    kind = {"doc": "document", "audio": "audio", "video": "video"}
    lines = [f"- {d['name']} ({kind.get(d['kind'], d['kind'])}, ~{d['chars']} chars)" for d in docs]
    return f"The knowledge base has {len(docs)} uploaded item(s):\n" + "\n".join(lines)


@tool(description="When the user asks to generate an industry-insight / decision / analysis report, you must call this tool first to enter report-writing mode. No args. After calling it, gather data via web search and write the report.")
def generate_decision_report() -> str:
    return "Entered report-writing mode: first gather enough data via web search, then write a structured report."
