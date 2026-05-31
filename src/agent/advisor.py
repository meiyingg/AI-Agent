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
        "你是资深投资顾问。请基于以下三方调研，并【紧密结合企业长期档案】，给出详尽、可落地的结构化投资建议。\n"
        "要求：\n"
        "1. analysis：写一段 ≥300 字的深入分析，**必须具体引用企业档案里的画像/偏好/关键事实**"
        "(例如'贵司主营钠离子电池储能、风险偏好保守、已获吉打州建厂批文')，据此论证'该不该做、为什么、怎么做'；"
        "适当处用 markdown 表格做方案/维度对比（如不同选址或方案的成本/风险/回报对比）。\n"
        "2. metrics：填写关键量化指标键值对(如 年化ROI/回本周期/风险评分/投资额/政策红利)，有数据就量化。\n"
        "3. 依据/机会/风险/下一步行动 每部分给出 4-6 条具体、可执行的内容（尽量带数据）。\n"
        "4. sources 必须**逐条照抄**三方调研中出现的所有来源链接(URL)，不要遗漏、不要编造。\n"
        "5. 企业档案用于个性化，但不可凌驾于本次调研事实之上。\n"
        "只输出一个 JSON 对象，不要任何多余文字。\n\n"
        "{profile}"
        "企业问题：{query}\n\n"
        "三方调研发现：\n{notes}\n\n"
        "{format_instructions}\n"
    ),
    input_variables=["query", "notes", "profile"],
    partial_variables={"format_instructions": _parser.get_format_instructions()},
)


def _augment_sources(advice: dict, notes: str) -> dict:
    """兜底：把调研笔记里出现的所有 URL 并入 sources(去重, 不覆盖已有)。"""
    existing = advice.get("sources") or []
    urls = re.findall(r"https?://[^\s)\]）】\"'，,、]+", notes)
    extra = []
    for u in urls:
        if not any(u in s for s in existing) and u not in extra:
            extra.append(u)
    advice["sources"] = existing + extra
    return advice
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
            advice = InvestmentAdvice.model_validate_json(_clean_json(raw)).model_dump()
            return _augment_sources(advice, notes)     # 兜底并入所有调研来源
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

    analysis = f"## 详细分析\n\n{a.get('analysis')}\n\n" if a.get("analysis") else ""
    metrics = a.get("metrics") or {}
    metrics_md = ""
    if isinstance(metrics, dict) and metrics:
        rows = "\n".join(f"| {k} | {v} |" for k, v in metrics.items())
        metrics_md = f"## 关键指标\n\n| 指标 | 数值 |\n|---|---|\n{rows}\n\n"
    return (
        f"# 投资建议报告\n\n"
        f"**结论**：{a.get('decision', '')} ｜ **置信度**：{a.get('confidence', '')}\n\n"
        f"{a.get('summary', '')}\n\n"
        f"{metrics_md}"
        f"{analysis}"
        f"{block('依据', a.get('rationale'))}\n"
        f"{block('机会', a.get('opportunities'))}\n"
        f"{block('风险', a.get('risks'))}\n"
        f"{block('下一步行动', a.get('actions'))}\n"
        f"{block('参考来源', a.get('sources'))}"
    )
