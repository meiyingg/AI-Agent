"""量化分析 Agent 的 6 个【模拟】金融工具。

说明：当前无真实数据源，输出由入参确定性生成 (同输入同输出，可复现)，
仅用于跑通端到端闭环与演示。接真实数据时，只需替换各函数内部实现。
每个工具加了 @cached：同一参数重复调用直接命中 (健壮性/省成本演示)。
"""
import hashlib
from langchain_core.tools import tool
from src.utils.robust import cached


def _seed(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode("utf-8")).hexdigest(), 16)


@tool(description="Get a market snapshot (size/growth) for an industry in a region. Args: industry, region")
@cached
def market_snapshot(industry: str, region: str) -> str:
    s = _seed("market", industry, region)
    size = 50 + s % 950
    growth = 5 + s % 25
    return f"[Simulated] {region} {industry} market size ≈ RMB {size}00M, annual growth ≈ {growth}%."


@tool(description="Estimate the investment return for an amount in an industry/region. Args: industry, region, amount_million (investment, in millions)")
@cached
def estimate_roi(industry: str, region: str, amount_million: float) -> str:
    s = _seed("roi", industry, region, amount_million)
    roi = 8 + s % 22
    payback = round(100 / max(roi, 1) / 5, 1) + 1
    return f"[Simulated] Estimated annualized ROI ≈ {roi}%, payback period ≈ {payback} years."


@tool(description="Assess the investment risk for an industry in a region. Args: industry, region")
@cached
def risk_score(industry: str, region: str) -> str:
    s = _seed("risk", industry, region)
    score = 1 + s % 10
    factors = ["FX volatility", "policy uncertainty", "supply chain", "local approvals", "talent shortage", "intensifying competition"]
    picked = [factors[s % len(factors)], factors[(s // 7) % len(factors)]]
    return f"[Simulated] Risk score {score}/10. Main risks: {', '.join(set(picked))}."


@tool(description="Estimate the build/operating cost of a plan. Args: plan (plan description), scale (scale description)")
@cached
def cost_estimate(plan: str, scale: str) -> str:
    s = _seed("cost", plan, scale)
    capex = 20 + s % 480
    opex = 5 + s % 95
    return f"[Simulated] Initial capex ≈ RMB {capex}M, annual opex ≈ RMB {opex}M."


@tool(description="Compare two options and give a recommendation. Args: option_a, option_b")
@cached
def compare_options(option_a: str, option_b: str) -> str:
    s = _seed("cmp", option_a, option_b)
    pick = option_a if s % 2 == 0 else option_b
    return (f"[Simulated] After a multi-dimensional comparison (cost/risk/return/timeline), recommended: {pick}."
            f" Reason: higher overall score, with better-balanced long-term return and risk.")


@tool(description="Look up policy incentives (tax/subsidies, etc.) for an industry in a region. Args: region, industry")
@cached
def policy_incentive(region: str, industry: str) -> str:
    s = _seed("policy", region, industry)
    tax = s % 3
    options = ["import-tariff reduction", "corporate income-tax breaks", "land/factory subsidies", "local-assembly (CKD) tax exemption"]
    return f"[Simulated] {region} offers {industry}: {options[tax]}, {options[(tax + 1) % 4]}."


ANALYSIS_TOOLS = [market_snapshot, estimate_roi, risk_score,
                  cost_estimate, compare_options, policy_incentive]
