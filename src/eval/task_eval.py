"""多 Agent 端到端任务评测。

对几条企业投资问题跑完整 Supervisor 流程，判定"任务成功"：
  跑完闭环 + 产出通过 Schema 校验 + 关键字段非空。
输出任务成功率。需要 LLM (DashScope / Tavily)。

注意：模拟数据下，成功率主要反映**流程鲁棒性**，非业务准确率。
"""
from src.schemas.investment import InvestmentAdvice
from src.utils.logger import logger

TASKS = [
    "我们一家电池厂该不该去马来西亚建厂？",
    "公司想拓展东南亚跨境电商物流，有什么建议？",
    "考虑在吉隆坡设新能源汽车组装厂，可行吗？",
    "是否应该加大对马来半导体封测的投资？",
    "我们要不要在浙江-马来之间建保税仓？",
]


def is_success(recommendation: dict) -> bool:
    """任务成功判定：能通过 Schema 校验且关键字段非空。"""
    try:
        a = InvestmentAdvice.model_validate(recommendation)
    except Exception:
        return False
    return bool(a.decision) and bool(a.summary) and (
        len(a.rationale) > 0 or len(a.risks) > 0 or len(a.opportunities) > 0
    )


def evaluate(tasks: list[str] = None) -> dict:
    from src.graph.supervisor import InvestmentAdvisor
    tasks = tasks or TASKS
    advisor = InvestmentAdvisor()

    ok = 0
    for q in tasks:
        try:
            final = advisor.app.invoke(advisor._input(q), config=advisor._cfg)
            rec = final.get("recommendation", {})
            success = is_success(rec)
        except Exception as e:
            logger.error(f"[task_eval] 任务异常: {q} -> {e}")
            success = False
        ok += int(success)
        print(f"  [{'OK ' if success else 'FAIL'}] {q}")

    n = len(tasks)
    rate = ok / n if n else 0.0
    print(f"\n========= 端到端任务评测 =========")
    print(f"任务数: {n}，成功: {ok}，成功率: {rate * 100:.0f}%")
    print("================================\n")
    return {"n": n, "success": ok, "rate": rate}


if __name__ == "__main__":
    evaluate()
