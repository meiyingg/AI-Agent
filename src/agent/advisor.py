"""投资建议 Agent：汇总三方发现 -> 结构化投资建议 (带 Schema 校验 + 降级)。"""
import re
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.prompts import PromptTemplate
from src.schemas.investment import InvestmentAdvice
from src.models.factory import chat_model
from src.utils.robust import retry
from src.utils.logger import logger

_parser = PydanticOutputParser(pydantic_object=InvestmentAdvice)
_PROMPT = PromptTemplate(
    template=(
        "你是资深投资顾问。请基于以下三方调研，并参考企业长期档案，给出结构化投资建议。\n"
        "企业长期档案仅作个性化背景参考，不可凌驾于本次调研事实之上。\n"
        "只输出一个 JSON 对象，不要任何多余文字。\n\n"
        "{profile}"
        "企业问题：{query}\n\n"
        "三方调研发现：\n{notes}\n\n"
        "{format_instructions}\n"
    ),
    input_variables=["query", "notes", "profile"],
    partial_variables={"format_instructions": _parser.get_format_instructions()},
)
_chain = _PROMPT | chat_model | StrOutputParser()


def _clean_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
    s, e = raw.find("{"), raw.rfind("}")
    return raw[s:e + 1] if s != -1 and e != -1 else raw


@retry()
def _invoke(query: str, notes: str, profile: str) -> str:
    return _chain.invoke({"query": query, "notes": notes, "profile": profile})


def build_advice(state: dict) -> dict:
    notes = (
        f"【内部知识】{state.get('internal_notes', '') or '无'}\n"
        f"【行业调研】{state.get('research_notes', '') or '无'}\n"
        f"【量化分析】{state.get('analysis_notes', '') or '无'}"
    )
    query = state.get("query", "")
    # 注入长期记忆(全局企业档案), 个性化建议
    try:
        from src.memory.profile import profile_text
        prof = profile_text()
        profile = f"{prof}\n\n" if prof else ""
    except Exception as e:
        logger.warning(f"[advisor] 档案注入失败, 跳过: {e}")
        profile = ""
    for attempt in range(2):                     # Schema 校验失败重试一次
        try:
            raw = _invoke(query, notes, profile)
            return InvestmentAdvice.model_validate_json(_clean_json(raw)).model_dump()
        except Exception as e:
            logger.warning(f"[advisor] 第{attempt + 1}次结构化失败: {e}")
    # 降级：返回最小可用结构，不崩
    return InvestmentAdvice(
        summary="（结构化生成失败，已降级返回摘要）",
        decision="暂缓",
        rationale=[notes[:400]],
        confidence="低",
    ).model_dump()


def format_advice_md(a: dict) -> str:
    def block(title, items):
        if not items:
            return f"**{title}**：本期无\n"
        return f"**{title}**：\n" + "\n".join(f"- {x}" for x in items) + "\n"

    return (
        f"# 投资建议报告\n\n"
        f"**结论**：{a.get('decision', '')} ｜ **置信度**：{a.get('confidence', '')}\n\n"
        f"{a.get('summary', '')}\n\n"
        f"{block('依据', a.get('rationale'))}\n"
        f"{block('机会', a.get('opportunities'))}\n"
        f"{block('风险', a.get('risks'))}\n"
        f"{block('下一步行动', a.get('actions'))}\n"
        f"{block('参考来源', a.get('sources'))}"
    )
