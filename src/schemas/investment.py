"""投资建议的结构化输出模型 (Pydantic)。

投资建议 Agent 必须产出符合此 schema 的结构，便于校验、展示与下游消费。
"""
from pydantic import BaseModel, Field


class InvestmentAdvice(BaseModel):
    summary: str = Field(default="", description="一句话核心结论")
    decision: str = Field(default="暂缓", description="投资建议：进入 / 暂缓 / 不建议")
    rationale: list[str] = Field(default_factory=list, description="主要依据")
    opportunities: list[str] = Field(default_factory=list, description="机会点")
    risks: list[str] = Field(default_factory=list, description="风险点")
    actions: list[str] = Field(default_factory=list, description="下一步行动建议")
    confidence: str = Field(default="中", description="置信度：高 / 中 / 低")
    sources: list[str] = Field(default_factory=list, description="引用来源(链接或内部纪要)")
