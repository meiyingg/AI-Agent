"""量化分析 Agent 的 6 个【模拟】金融工具。

说明：当前无真实数据源，输出由入参确定性生成 (同输入同输出，可复现)，
仅用于跑通端到端闭环与演示。接真实数据时，只需替换各函数内部实现。
每个工具加了 @cached：同一参数重复调用直接命中 (健壮性/省成本演示)。
"""
import hashlib
from langchain_core.tools import tool
from src.utils.robust import cached


def _seed(*parts) -> int:
    return int(hashlib.md5("|".join(map(str, parts)).encode("utf-8")).hexdigest(), 16)


@tool(description="获取某行业在某地区的市场概况(规模/增速)。入参 industry, region")
@cached
def market_snapshot(industry: str, region: str) -> str:
    s = _seed("market", industry, region)
    size = 50 + s % 950
    growth = 5 + s % 25
    return f"[模拟] {region}{industry}市场规模约 {size} 亿元，年增速约 {growth}%。"


@tool(description="预估某行业某地区某投资额的投资回报。入参 industry, region, amount_million(投资额,百万)")
@cached
def estimate_roi(industry: str, region: str, amount_million: float) -> str:
    s = _seed("roi", industry, region, amount_million)
    roi = 8 + s % 22
    payback = round(100 / max(roi, 1) / 5, 1) + 1
    return f"[模拟] 预估年化 ROI 约 {roi}%，回本周期约 {payback} 年。"


@tool(description="评估某行业某地区的投资风险。入参 industry, region")
@cached
def risk_score(industry: str, region: str) -> str:
    s = _seed("risk", industry, region)
    score = 1 + s % 10
    factors = ["汇率波动", "政策不确定", "供应链", "本地审批", "人才短缺", "竞争加剧"]
    picked = [factors[s % len(factors)], factors[(s // 7) % len(factors)]]
    return f"[模拟] 风险评分 {score}/10，主要风险：{', '.join(set(picked))}。"


@tool(description="估算某方案的建设/运营成本。入参 plan(方案描述), scale(规模描述)")
@cached
def cost_estimate(plan: str, scale: str) -> str:
    s = _seed("cost", plan, scale)
    capex = 20 + s % 480
    opex = 5 + s % 95
    return f"[模拟] 初始投入约 {capex} 百万元，年运营成本约 {opex} 百万元。"


@tool(description="对比两个方案的优劣并给出推荐。入参 option_a, option_b")
@cached
def compare_options(option_a: str, option_b: str) -> str:
    s = _seed("cmp", option_a, option_b)
    pick = option_a if s % 2 == 0 else option_b
    return (f"[模拟] 多维对比(成本/风险/回报/周期)后，推荐：{pick}。"
            f" 理由：综合得分更高，长期回报与风险更均衡。")


@tool(description="查询某地区某行业的政策红利(税收/补贴等)。入参 region, industry")
@cached
def policy_incentive(region: str, industry: str) -> str:
    s = _seed("policy", region, industry)
    tax = s % 3
    options = ["进口关税减免", "企业所得税优惠", "土地/厂房补贴", "本地组装(CKD)税收豁免"]
    return f"[模拟] {region}对{industry}提供：{options[tax]}、{options[(tax + 1) % 4]}。"


ANALYSIS_TOOLS = [market_snapshot, estimate_roi, risk_score,
                  cost_estimate, compare_options, policy_incentive]
