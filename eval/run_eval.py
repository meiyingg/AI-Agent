"""RAG 质量评测(RAGAS)。

在固定 demo 语料上跑黄金集(eval/dataset.jsonl),用 RAGAS 算四个指标:
  - faithfulness        答案是否被检索内容支撑(防幻觉)
  - answer_relevancy    答案是否切题
  - context_precision   检索回的内容相关性(对照标准答案)
  - context_recall      标准答案的信息有没有被检索覆盖

判分模型与 embedding 都指向**通义 qwen**(非 OpenAI)。

用法:
  python eval/run_eval.py            # 跑全部
  python eval/run_eval.py --limit 3  # 只跑前 3 条(调试/省钱)

前提:.env 里有 DASHSCOPE_API_KEY。脚本会**幂等导入** demo/ 文档(SHA-256 去重,不重复)。
"""
import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
try:                                   # Windows 控制台默认 cp1252/gbk,统一 utf-8 防中文路径 print 崩
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(_ROOT, ".env"))

# --- RAGAS 兼容垫片 ---
# ragas 0.4 仍硬 import 新版 langchain 已删的 Vertex 模块;注入空壳兜住(我们用 qwen 判分,不碰 Vertex)。
import types as _types  # noqa: E402
_vx = _types.ModuleType("langchain_community.chat_models.vertexai")
_vx.ChatVertexAI = object
sys.modules.setdefault("langchain_community.chat_models.vertexai", _vx)
try:
    import langchain_community.llms as _llms  # noqa: E402
    if not hasattr(_llms, "VertexAI"):
        _llms.VertexAI = object
except Exception:
    pass


def ingest_fixtures() -> None:
    """把 demo/ 的文档(非音视频)幂等导入知识库,保证黄金集问题有对应文件。"""
    from src.rag import kb_service
    from src.utils.files import sha256_of_file
    demo = os.path.join(_ROOT, "demo")
    exts = {".md", ".txt", ".pdf", ".docx", ".xlsx"}
    for fn in sorted(os.listdir(demo)):
        if fn.startswith("~$") or os.path.splitext(fn)[1].lower() not in exts:
            continue
        path = os.path.join(demo, fn)
        fh = sha256_of_file(path)
        if kb_service.find_doc_by_filehash(fh):
            continue
        kb_service.process_upload(path, fn, file_hash=fh)
        print(f"  + ingested fixture: {fn}")


def run_rag(kb, question: str):
    """跑一次高级 RAG,返回 (answer, contexts)。"""
    docs = kb.retriever().invoke(question)
    contexts = [d.page_content for d in docs]
    context_str = "\n\n".join(
        f"[Snippet {i}] source:{d.metadata.get('source', '')}\n{d.page_content}"
        for i, d in enumerate(docs, 1))
    answer = kb.chain.invoke({"input": question, "context": context_str})
    return str(answer).strip(), contexts


def write_html_report(df, metrics, path) -> None:
    """把 RAGAS 结果渲染成一个带颜色的自包含 HTML 报告(双击即可在浏览器看)。"""
    import html as _html

    def color(v):
        try:
            v = float(v)
        except Exception:
            return "#9ca3af"
        return "#16a34a" if v >= 0.8 else "#f59e0b" if v >= 0.5 else "#dc2626"

    cards = ""
    for m in metrics:
        if m in df:
            avg = float(df[m].mean())
            cards += (f'<div class="card"><div class="lbl">{m.replace("_", " ")}</div>'
                      f'<div class="val" style="color:{color(avg)}">{avg:.3f}</div></div>')

    rows = ""
    for i, r in df.reset_index(drop=True).iterrows():
        q = _html.escape(str(r.get("user_input", "")))
        a = _html.escape(str(r.get("response", ""))[:220])
        cells = ""
        for m in metrics:
            v = r.get(m, "")
            try:
                vs = f"{float(v):.2f}"
            except Exception:
                vs = str(v)
            cells += f'<td style="text-align:center;font-weight:600;color:{color(v)}">{vs}</td>'
        rows += f'<tr><td>{i + 1}</td><td>{q}</td><td class="ans">{a}…</td>{cells}</tr>'

    hdr = "".join(f"<th>{m.replace('_', ' ')}</th>" for m in metrics)
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>RAG Eval Report</title><style>
body{{font-family:Segoe UI,system-ui,sans-serif;margin:24px;color:#1f2937;background:#fafafa}}
h1{{font-size:20px;margin:0 0 4px}} .sub{{color:#6b7280;font-size:13px;margin-bottom:16px}}
.cards{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}}
.card{{border:1px solid #e5e7eb;border-radius:10px;padding:12px 18px;background:#fff;min-width:150px}}
.lbl{{font-size:12px;color:#6b7280}} .val{{font-size:30px;font-weight:700;line-height:1.1}}
table{{border-collapse:collapse;width:100%;background:#fff;font-size:13px}}
th,td{{border:1px solid #e5e7eb;padding:8px;vertical-align:top}} th{{background:#f3f4f6;text-align:left}}
td.ans{{color:#6b7280;max-width:340px}}
</style></head><body>
<h1>🍽️ RAG Evaluation Report</h1>
<div class="sub">RAGAS metrics · judge = qwen · scale 0–1, higher is better · {len(df)} questions</div>
<div class="cards">{cards}</div>
<table><thead><tr><th>#</th><th>Question</th><th>Answer (system)</th>{hdr}</tr></thead>
<tbody>{rows}</tbody></table>
<p class="sub">🟢 ≥ 0.80 good &nbsp;·&nbsp; 🟡 0.50–0.80 ok &nbsp;·&nbsp; 🔴 &lt; 0.50 weak</p>
</body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只评前 N 条(调试用)")
    args = ap.parse_args()

    print("[eval] ingesting demo fixtures (idempotent)...")
    ingest_fixtures()

    golden = []
    with open(os.path.join(_ROOT, "eval", "dataset.jsonl"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                golden.append(json.loads(line))
    if args.limit:
        golden = golden[: args.limit]
    print(f"[eval] {len(golden)} golden questions")

    from src.agent.tools import _meeting_kb
    kb = _meeting_kb()
    samples = []
    for i, g in enumerate(golden, 1):
        ans, ctxs = run_rag(kb, g["question"])
        samples.append({
            "user_input": g["question"],
            "response": ans,
            "retrieved_contexts": ctxs,
            "reference": g["ground_truth"],
        })
        print(f"  [{i}/{len(golden)}] {g['question'][:48]}…")

    # ---- RAGAS 评测(judge = qwen, embedding = DashScope) ----
    from ragas import EvaluationDataset, evaluate
    from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from src.models.factory import chat_model, embed_model

    dataset = EvaluationDataset.from_list(samples)
    judge = LangchainLLMWrapper(chat_model)
    emb = LangchainEmbeddingsWrapper(embed_model)

    print("[eval] scoring with RAGAS (qwen judge) — this makes many LLM calls…")
    result = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=judge,
        embeddings=emb,
    )

    metric_cols = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    df = result.to_pandas()
    print("\n===== RAG eval scorecard (0-1, higher = better) =====")
    for m in metric_cols:
        if m in df:
            print(f"  {m:<20} {df[m].mean():.3f}")

    present = [m for m in metric_cols if m in df]
    csv_out = os.path.join(_ROOT, "eval", "last_result.csv")
    html_out = os.path.join(_ROOT, "eval", "report.html")
    json_out = os.path.join(_ROOT, "eval", "last_result.json")
    df.to_csv(csv_out, index=False, encoding="utf-8-sig")
    write_html_report(df, present, html_out)

    # JSON —— 供前端 Eval 页读取
    import time as _time
    payload = {
        "ts": _time.strftime("%Y-%m-%d %H:%M:%S"),
        "n": int(len(df)),
        "summary": {m: (None if df[m].mean() != df[m].mean() else round(float(df[m].mean()), 4)) for m in present},
        "items": [
            {
                "question": str(r.get("user_input", "")),
                "answer": str(r.get("response", ""))[:600],
                "reference": str(r.get("reference", ""))[:600],
                **{m: (None if r.get(m) != r.get(m) else round(float(r[m]), 3)) for m in present},
            }
            for _, r in df.reset_index(drop=True).iterrows()
        ],
    }
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\nCSV   ->  {csv_out}")
    print(f"HTML  ->  {html_out}   (double-click to open the visual report)")
    print(f"JSON  ->  {json_out}   (read by the in-app Eval page)")


if __name__ == "__main__":
    main()
