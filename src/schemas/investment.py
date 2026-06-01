"""投资建议的结构化输出模型 (Pydantic)。

投资建议 Agent 必须产出符合此 schema 的结构，便于校验、展示与下游消费。
"""
from pydantic import BaseModel, Field


class InvestmentAdvice(BaseModel):
    summary: str = Field(default="", description="One-sentence core conclusion")
    decision: str = Field(default="Hold", description="Investment decision: Enter / Hold / Avoid")
    analysis: str = Field(
        default="",
        description="Detailed analysis (>=300 words, must concretely draw on the company profile/"
                    "preferences/key facts, may use markdown sections, and use a markdown table "
                    "for option comparison where appropriate)",
    )
    metrics: dict = Field(
        default_factory=dict,
        description="Key quantitative metrics (key-value pairs, e.g. {'Annualized ROI':'~15%',"
                    "'Payback period':'2.3 yrs','Risk score':'Medium','Investment':'$300M'})",
    )
    rationale: list[str] = Field(default_factory=list, description="Main rationale (4-6 points, with data where possible)")
    opportunities: list[str] = Field(default_factory=list, description="Opportunities (4-6 points)")
    risks: list[str] = Field(default_factory=list, description="Risks (4-6 points)")
    actions: list[str] = Field(default_factory=list, description="Next-step action recommendations (4-6 points)")
    confidence: str = Field(default="Medium", description="Confidence: High / Medium / Low")
    sources: list[str] = Field(default_factory=list, description="Cited sources (links or internal minutes)")
