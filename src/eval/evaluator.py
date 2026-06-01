"""检索效果轻量评测：Recall@k。

对一个小问答集，比较两种检索：
- baseline : 纯向量检索
- advanced : 混合检索(BM25+向量) + 重排
判定命中：检索回的前 k 个片段里，是否有片段包含该问题的"应出现关键词"(expected)。
输出 "baseline X% -> advanced Y%"，给简历提供真实可复现的数字。

纯指标函数 (recall_at_k) 不依赖 LLM，可单测；evaluate() 需要向量库/嵌入。
"""
import json
from src.utils.config import eval_conf, abs_of
from src.utils.logger import logger


def hit(docs, expected: str, k: int) -> bool:
    """前 k 个片段中是否有片段包含 expected 关键词。"""
    return any(expected in d.page_content for d in docs[:k])


def recall_at_k(retrieved_per_query: list[list], expected_list: list[str], k: int) -> float:
    """纯函数：给定每题检索结果(可为字符串列表)与期望关键词，算 Recall@k。"""
    if not expected_list:
        return 0.0
    hits = 0
    for docs, expected in zip(retrieved_per_query, expected_list):
        texts = [d if isinstance(d, str) else d.page_content for d in docs]
        if any(expected in t for t in texts[:k]):
            hits += 1
    return hits / len(expected_list)


def _load_qa(path: str) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def evaluate(k: int = None) -> dict:
    """跑评测 (需要嵌入/向量库)。会先确保会议纪要已入库。"""
    from src.rag.meeting_kb import MeetingKB
    from src.rag.retriever import AdvancedRetriever, vector_only_retriever

    k = k or eval_conf.get("k", 5)
    kb = MeetingKB()
    kb.ingest()                                   # 确保语料已入库
    chunks = kb.load_chunks()

    baseline = vector_only_retriever(kb.store, k)
    advanced = AdvancedRetriever(kb.store, chunks)

    qa = _load_qa(abs_of("eval_qa"))
    base_hits = adv_hits = 0
    for item in qa:
        q, exp = item["query"], item["expected"]
        if hit(baseline.invoke(q), exp, k):
            base_hits += 1
        if hit(advanced.invoke(q), exp, k):
            adv_hits += 1

    n = len(qa)
    result = {
        "n": n,
        "k": k,
        "baseline_recall": base_hits / n if n else 0.0,
        "advanced_recall": adv_hits / n if n else 0.0,
        "advanced_mode": advanced.mode,
    }
    _print(result)
    return result


def _print(r: dict):
    print("\n========= Retrieval Eval (Recall@%d) =========" % r["k"])
    print(f"QA samples: {r['n']}")
    print(f"baseline (vector-only) : {r['baseline_recall'] * 100:.1f}%")
    print(f"advanced ({r['advanced_mode']}): {r['advanced_recall'] * 100:.1f}%")
    print("==============================================\n")


if __name__ == "__main__":
    evaluate()
