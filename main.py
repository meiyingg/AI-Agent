"""智能助手 - 命令行入口。

两大能力：
  ① 会议纪要 RAG 助手 (内部、静态)
  ② 在线检索辅助决策助手 (外部、实时, Tavily)
一个 Agent 自动判断走哪边。

常用命令：
    python main.py gen-meetings -n 20     # 生成示例会议纪要 (演示用)
    python main.py ingest-meetings        # 会议纪要入库 (MD5 去重 + 向量化) [需 DashScope Key]
    python main.py ask "上次物流会议的决议是什么"      # 与 Agent 对话 (自动分流) [需 Key]
    python main.py ask "东南亚新能源车最新政策，并出一份决策报告"
    python main.py report "东南亚新能源汽车市场趋势"   # 直接出行业洞察报告 [需 DashScope + Tavily]
    python main.py evaluate               # 检索评测 Recall@k: 基线 vs 混合+重排 [需 DashScope]
    python main.py advise "我们电池厂该不该去马来西亚建厂"  # 多Agent投资顾问 [需 DashScope + Tavily]
    python server/main.py                 # 启动 Web 后端 (FastAPI :8000)
    # 前端网页: 另开终端 cd web 后 pnpm dev (Next.js :3000)

提示：gen-meetings 纯本地无需 Key；其余涉及模型/联网需配置 .env。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def cmd_gen_meetings(args):
    from src.ingestion.synthetic import generate_files
    from src.utils.config import abs_of
    out = args.out or abs_of("meetings_dir")
    paths = generate_files(args.count, out)
    print(f"[gen-meetings] Generated {len(paths)} sample meeting minutes -> {out}")


def cmd_ingest_meetings(args):
    from src.rag.meeting_kb import MeetingKB
    print("[ingest-meetings]", MeetingKB().ingest())


def cmd_ask(args):
    from src.agent.react_agent import Assistant
    for chunk in Assistant().execute_stream(args.query):
        print(chunk, end="", flush=True)
    print()


def cmd_report(args):
    from src.reporting.report_service import ReportService
    print(ReportService().generate(args.topic))


def cmd_evaluate(args):
    from src.eval.evaluator import evaluate
    evaluate(k=args.k)


def cmd_advise(args):
    """多 Agent 投资顾问 (Supervisor + 4 子Agent)。"""
    from src.graph.supervisor import InvestmentAdvisor
    for chunk in InvestmentAdvisor().execute_stream(args.query):
        print(chunk, end="", flush=True)
    print()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="AI Assistant CLI (meeting RAG + online-search decisions)")
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("gen-meetings", help="Generate sample meeting minutes")
    g.add_argument("-n", "--count", type=int, default=20)
    g.add_argument("--out", default="")
    g.set_defaults(func=cmd_gen_meetings)

    sub.add_parser("ingest-meetings", help="Index meeting minutes (MD5 dedup + embedding)").set_defaults(func=cmd_ingest_meetings)

    a = sub.add_parser("ask", help="Chat with the Agent (auto-routing)")
    a.add_argument("query", type=str)
    a.set_defaults(func=cmd_ask)

    r = sub.add_parser("report", help="Generate an industry-insight report")
    r.add_argument("topic", type=str)
    r.set_defaults(func=cmd_report)

    ev = sub.add_parser("evaluate", help="Retrieval eval Recall@k (baseline vs hybrid+rerank)")
    ev.add_argument("-k", type=int, default=None)
    ev.set_defaults(func=cmd_evaluate)

    ad = sub.add_parser("advise", help="Multi-agent investment advisor (Supervisor + sub-agents)")
    ad.add_argument("query", type=str)
    ad.set_defaults(func=cmd_advise)
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()
    args.func(args)
