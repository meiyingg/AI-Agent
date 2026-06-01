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


@tool(description="检索公司【内部文档/会议纪要/上传资料】来回答问题。当用户问'上次会议/某项目决议/谁负责/内部参数/某文件写了什么'等内部信息时使用，入参 query 为检索关键词")
def search_meeting_minutes(query: str) -> str:
    return _meeting_kb().search(query)


@tool(description="列出公司知识库里【现有哪些上传的文件/资料】。当用户问'知识库有什么文件/上传了哪些资料/有哪些文档'时调用，无入参，直接返回真实清单(勿凭空列举)")
def list_kb_files() -> str:
    from src.rag.kb_service import list_docs
    docs = list_docs()
    if not docs:
        return "知识库目前没有用户上传的文件。"
    kind = {"doc": "文档", "audio": "音频", "video": "视频"}
    lines = [f"- {d['name']}（{kind.get(d['kind'], d['kind'])}，约{d['chars']}字）" for d in docs]
    return f"知识库现有 {len(docs)} 份上传资料：\n" + "\n".join(lines)


@tool(description="当用户要求生成行业洞察/决策/分析报告时，必须先调用此工具以进入报告撰写模式，无入参。调用后再用联网搜索收集数据并撰写报告")
def generate_decision_report() -> str:
    return "已进入报告撰写模式：请先用联网搜索收集足够数据，再撰写结构化报告。"
