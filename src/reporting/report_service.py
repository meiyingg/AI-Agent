"""行业洞察报告服务 (功能二的批处理出口)。

给定主题：用 LangChain 官方 Tavily 工具实时联网检索 -> LLM 按报告模板撰写 -> 落地 Markdown。
与 Agent 的报告模式共用同一套报告提示词。资讯实时检索、不落库。
"""
import os
from datetime import date
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from src.models.factory import chat_model
from src.utils.config import agent_conf, search_conf, abs_of
from src.utils.paths import get_abs_path
from src.utils.files import read_text
from src.utils.logger import logger


def _format_tavily(result) -> str:
    """把 TavilySearch 的返回整理成喂给 LLM 的资料文本。"""
    if isinstance(result, dict):
        items = result.get("results", [])
        lines = []
        if result.get("answer"):
            lines.append(f"概要: {result['answer']}")
        for r in items:
            lines.append(f"- {r.get('title','')}\n  {r.get('content','')}\n  来源: {r.get('url','')}")
        return "\n".join(lines) if lines else str(result)
    return str(result)


class ReportService:
    def __init__(self):
        from langchain_tavily import TavilySearch
        self.tavily = TavilySearch(max_results=search_conf.get("max_results", 5))
        self.report_prompt = read_text(get_abs_path(agent_conf["report_prompt_path"]))

    def generate(self, topic: str, save: bool = True) -> str:
        material = _format_tavily(self.tavily.invoke({"query": topic}))
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.report_prompt),
            ("user", "报告主题：{topic}\n生成日期：{today}\n\n在线检索到的资料如下：\n{material}"),
        ])
        chain = prompt | chat_model | StrOutputParser()
        report = chain.invoke({"topic": topic, "today": date.today().isoformat(), "material": material})

        if save:
            out_dir = abs_of("reports_dir")
            os.makedirs(out_dir, exist_ok=True)
            safe = "".join(c for c in topic if c.isalnum() or c in " _-")[:30].strip().replace(" ", "_")
            fp = os.path.join(out_dir, f"report_{date.today().isoformat()}_{safe}.md")
            with open(fp, "w", encoding="utf-8") as f:
                f.write(report)
            logger.info(f"[Report] 已保存: {fp}")
        return report


if __name__ == "__main__":
    print(ReportService().generate("东南亚新能源汽车市场最新趋势"))
