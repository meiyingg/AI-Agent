"""纯 Python 单元测试 (不依赖 LLM / 网络 / 向量库)。

验证：MD5 指纹、MD5 去重台账逻辑、合成生成、配置加载、Recall@k 指标函数。
运行：  python tests/test_pipeline.py     或   pytest tests/
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.files import md5_of_text
from src.ingestion.synthetic import random_minute, generate_files
from src.eval.evaluator import recall_at_k


def test_md5_deterministic():
    assert md5_of_text("同一段内容") == md5_of_text("同一段内容")
    assert md5_of_text("内容A") != md5_of_text("内容B")
    print("[OK] test_md5_deterministic")


def test_ledger_dedup_logic():
    with tempfile.TemporaryDirectory() as d:
        ledger = os.path.join(d, "md5.txt")

        def seen():
            if not os.path.exists(ledger):
                return set()
            with open(ledger, encoding="utf-8") as f:
                return {ln.strip() for ln in f if ln.strip()}

        def mark(h):
            with open(ledger, "a", encoding="utf-8") as f:
                f.write(h + "\n")

        h = md5_of_text("一份文档")
        assert h not in seen()
        mark(h)
        assert h in seen(), "标记后应已见过 -> 第二次会被跳过"
    print("[OK] test_ledger_dedup_logic")


def test_synthetic_meeting():
    text = random_minute()
    assert "会议标题" in text and "行动项" in text and "预算" in text
    print("[OK] test_synthetic_meeting")


def test_generate_files():
    with tempfile.TemporaryDirectory() as d:
        paths = generate_files(5, d)
        assert len(paths) == 5 and all(os.path.exists(p) for p in paths)
    print("[OK] test_generate_files")


def test_recall_at_k():
    # 两题：第一题前2命中, 第二题前k无命中
    retrieved = [
        ["无关片段", "包含海运加保税仓的片段"],   # 命中 "海运"
        ["完全无关", "也无关"],                    # 未命中 "差旅"
    ]
    expected = ["海运", "差旅"]
    assert recall_at_k(retrieved, expected, k=5) == 0.5
    assert recall_at_k(retrieved, expected, k=1) == 0.0   # 第一题命中在第2位, k=1 取不到
    assert recall_at_k([["有海运"]], ["海运"], k=5) == 1.0
    print("[OK] test_recall_at_k")


def test_config_loads():
    from src.utils.config import (rag_conf, rerank_conf, search_conf, eval_conf,
                                  agent_conf, multiagent_conf, robust_conf, abs_of)
    assert rag_conf["meeting_collection"] == "meetings"
    assert rag_conf["bm25_weight"] + rag_conf["vector_weight"] == 1.0
    assert rerank_conf["model"] == "gte-rerank"
    assert "max_results" in search_conf and "k" in eval_conf
    assert "system_prompt_path" in agent_conf
    assert multiagent_conf["max_rounds"] >= 1
    assert "retry_times" in robust_conf
    assert abs_of("chroma_dir").endswith("chroma")
    print("[OK] test_config_loads")


def test_robust_cache():
    from src.utils.robust import cached
    calls = {"n": 0}

    @cached
    def f(x):
        calls["n"] += 1
        return x * 2

    assert f(3) == 6 and f(3) == 6      # 第二次走缓存
    assert calls["n"] == 1, "相同入参应只真正执行一次"
    f(4)
    assert calls["n"] == 2
    print("[OK] test_robust_cache")


def test_robust_degrade():
    from src.utils.robust import degrade

    @degrade("兜底")
    def boom():
        raise RuntimeError("x")

    assert boom() == "兜底", "异常应被降级为默认值, 不抛出"
    print("[OK] test_robust_degrade")


def test_investment_schema_and_success():
    from src.schemas.investment import InvestmentAdvice
    from src.eval.task_eval import is_success
    a = InvestmentAdvice(summary="可行", decision="进入", rationale=["市场大"])
    assert is_success(a.model_dump()) is True
    assert is_success({"decision": "", "summary": ""}) is False
    print("[OK] test_investment_schema_and_success")


def test_analysis_tools_deterministic():
    from src.agent.analysis_tools import market_snapshot, ANALYSIS_TOOLS
    r1 = market_snapshot.invoke({"industry": "新能源", "region": "马来西亚"})
    r2 = market_snapshot.invoke({"industry": "新能源", "region": "马来西亚"})
    assert r1 == r2 and "模拟" in r1
    assert len(ANALYSIS_TOOLS) == 6
    print("[OK] test_analysis_tools_deterministic")


def run_all():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nALL PURE-PYTHON TESTS PASSED")


if __name__ == "__main__":
    run_all()
