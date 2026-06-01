"""排查：看实际入库的文件(字数) + 最近会话的问答。"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from src.utils.config import abs_of

print("===== 已上传/入库的文件 =====")
try:
    from src.rag.kb_service import list_docs
    docs = list_docs()
    if not docs:
        print("  (空) 知识库里没有任何文件 —— 上传根本没成功入库")
    for d in docs:
        print(f"  {d['name']} | {d['kind']} | {d['chars']} 字 | {d['chunks']} 块")
except Exception as e:
    print("  读取失败:", e)

print("\n===== 最近会话 =====")
try:
    with open(abs_of("threads_json"), encoding="utf-8") as f:
        threads = sorted(json.load(f), key=lambda t: t.get("updated_at", 0), reverse=True)
    for t in threads[:6]:
        print(f"  {t['id']} | {t['title']}")
    if threads:
        tid = threads[0]["id"]
        print(f"\n===== 最近会话 [{tid}] 的问答 =====")
        from src.graph.supervisor import InvestmentAdvisor
        for m in InvestmentAdvisor().get_messages(tid):
            role = {"human": "你", "ai": "AI"}.get(getattr(m, "type", "?"), getattr(m, "type", "?"))
            content = (getattr(m, "content", "") or "").strip().replace("\n", " ")[:260]
            print(f"  [{role}] {content}")
except Exception as e:
    print("  读取失败:", e)
