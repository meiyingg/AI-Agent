"""通义千问 / DashScope 国内端点真实价目表 + 成本计算。

价格来源：阿里云百炼官方账单(2026-06 用户核对)。单位：元 / 每百万 token，(输入, 输出)。
注：DashScope SDK 默认连国内端点(dashscope.aliyuncs.com)；若切换到国际端点
需设 DASHSCOPE_API_BASE=https://dashscope-intl.aliyuncs.com/api/v1 并更新此价表。
"""

# 元 / 1,000,000 tokens —— (input, output)，DashScope 国内端点（华北2 北京）
PRICING = {
    "qwen-max": (2.4, 9.6),              # input ¥0.0024/千tokens, output ¥0.0096/千tokens
    "qwq-plus": (1.6, 4.0),              # input ¥0.0016/千tokens, output ¥0.004/千tokens
    "text-embedding-v4": (0.5, 0.0),     # input ¥0.0005/千tokens, output 不计费
}


def price_of(model: str):
    """取某模型 (输入价, 输出价) 元/百万 token;带版本后缀(qwen-max-2025xx)归一到基名。"""
    if model in PRICING:
        return PRICING[model]
    for name, p in PRICING.items():        # 前缀匹配,兼容快照版本号
        if model.startswith(name):
            return p
    return (None, None)


def cost_yuan(model: str, in_tokens: int, out_tokens: int):
    """按真实价表算这次调用花了多少钱(元);无价表返回 None(不猜)。"""
    pi, po = price_of(model)
    if pi is None:
        return None
    return (in_tokens * pi + out_tokens * (po or 0.0)) / 1_000_000
