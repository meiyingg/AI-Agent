"""投资建议的结构化输出模型 (Pydantic)。

投资建议 Agent 必须产出符合此 schema 的结构，便于校验、展示与下游消费。
"""
from pydantic import BaseModel, Field


class InvestmentAdvice(BaseModel):
    summary: str = Field(default="", description="一句话核心结论")
    decision: str = Field(default="暂缓", description="投资建议：进入 / 暂缓 / 不建议")
    analysis: str = Field(
        default="",
        description="详细分析(≥300字, 必须具体结合企业画像/偏好/关键事实展开, "
                    "可用 markdown 分段, 适当处可用 markdown 表格做方案对比)",
    )
    metrics: dict = Field(
        default_factory=dict,
        description="关键量化指标(键值对, 如 {'年化ROI':'约15%','回本周期':'2.3年','风险评分':'中','投资额':'2亿元'})",
    )
    rationale: list[str] = Field(default_factory=list, description="主要依据(4-6条, 尽量带数据)")
    opportunities: list[str] = Field(default_factory=list, description="机会点(4-6条)")
    risks: list[str] = Field(default_factory=list, description="风险点(4-6条)")
    actions: list[str] = Field(default_factory=list, description="下一步行动建议(4-6条)")
    confidence: str = Field(default="中", description="置信度：高 / 中 / 低")
    sources: list[str] = Field(default_factory=list, description="引用来源(链接或内部纪要)")
