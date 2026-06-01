"""投资建议 Agent：汇总三方发现 -> 结构化投资建议 (带 Schema 校验 + 降级)。"""
import json
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
        "You are a senior investment advisor. Based on the three-way research below and **tightly combined "
        "with the company's long-term profile**, give a detailed, actionable, structured investment recommendation.\n"
        "Requirements:\n"
        "1. analysis: write an in-depth analysis of >=300 words that **must concretely cite the profile/"
        "preferences/key facts in the company profile** (e.g. 'your company focuses on sodium-ion battery storage, "
        "has a conservative risk appetite, and already holds the Kedah plant permit'), and argue 'whether to do it, "
        "why, and how'; where appropriate, use a markdown table to compare options/dimensions (e.g. cost/risk/return "
        "across different sites or plans).\n"
        "2. metrics: fill in key quantitative metric key-value pairs (e.g. annualized ROI / payback period / "
        "risk score / investment amount / policy incentives); quantify whenever data is available.\n"
        "3. rationale / opportunities / risks / next-step actions: give 4-6 concrete, executable points each (with data where possible).\n"
        "4. sources MUST **copy verbatim** every source link (URL) that appears in the three-way research — omit none, fabricate none.\n"
        "5. The company profile is for personalization but must not override this round's research facts.\n"
        "Output only a single JSON object, with no extra text.\n\n"
        "{profile}"
        "Company question: {query}\n\n"
        "Three-way research findings:\n{notes}\n\n"
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


def _parse_advice(raw: str) -> dict:
    """容错解析模型返回的 JSON 并校验为 InvestmentAdvice。

    关键：LLM 常把多行 markdown/表格直接塞进 analysis 等字段，产生【字符串内裸控制字符
    (裸换行/制表符)】——这对严格 JSON 非法(Pydantic model_validate_json 会拒)。
    用 json.loads(strict=False) 容忍这些控制字符，再做 dict 校验；并顺手去掉结尾多余逗号。
    """
    cleaned = re.sub(r",(\s*[}\]])", r"\1", _clean_json(raw))   # 去尾逗号
    data = json.loads(cleaned, strict=False)                    # strict=False: 容忍串内裸换行
    return InvestmentAdvice.model_validate(data).model_dump()


@retry()
def _invoke(query: str, notes: str, profile: str) -> str:
    return _chain.invoke({"query": query, "notes": notes, "profile": profile})


def build_advice(state: dict) -> dict:
    notes = (
        f"【Internal Knowledge】{state.get('internal_notes', '') or 'none'}\n"
        f"【Industry Research】{state.get('research_notes', '') or 'none'}\n"
        f"【Quant Analysis】{state.get('analysis_notes', '') or 'none'}"
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
            advice = _parse_advice(raw)
            return _augment_sources(advice, notes)     # 兜底并入所有调研来源
        except Exception as e:
            logger.warning(f"[advisor] 第{attempt + 1}次结构化失败: {e}")
    # 降级：返回最小可用结构，不崩
    return InvestmentAdvice(
        summary="(Structured generation failed; degraded to a summary.)",
        decision="Hold",
        rationale=[notes[:400]],
        confidence="Low",
    ).model_dump()


def format_advice_md(a: dict) -> str:
    def block(title, items):
        if not items:
            return f"**{title}**: none this round\n"
        return f"**{title}**:\n" + "\n".join(f"- {x}" for x in items) + "\n"

    analysis = f"## Detailed Analysis\n\n{a.get('analysis')}\n\n" if a.get("analysis") else ""
    metrics = a.get("metrics") or {}
    metrics_md = ""
    if isinstance(metrics, dict) and metrics:
        rows = "\n".join(f"| {k} | {v} |" for k, v in metrics.items())
        metrics_md = f"## Key Metrics\n\n| Metric | Value |\n|---|---|\n{rows}\n\n"
    return (
        f"# Investment Recommendation Report\n\n"
        f"**Decision**: {a.get('decision', '')} ｜ **Confidence**: {a.get('confidence', '')}\n\n"
        f"{a.get('summary', '')}\n\n"
        f"{metrics_md}"
        f"{analysis}"
        f"{block('Rationale', a.get('rationale'))}\n"
        f"{block('Opportunities', a.get('opportunities'))}\n"
        f"{block('Risks', a.get('risks'))}\n"
        f"{block('Next Steps', a.get('actions'))}\n"
        f"{block('Sources', a.get('sources'))}"
    )
