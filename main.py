"""智能助手 - 命令行入口。

两大能力：
  ① 内部文档 RAG 助手 (检索用户上传的资料)
  ② 在线检索辅助决策助手 (外部、实时, Tavily)
一个 Agent 自动判断走哪边。

常用命令：
    python main.py ask "上次物流会议的决议是什么"        # 与 Agent 对话 (自动分流) [需 Key]
    python main.py report "东南亚新能源汽车市场趋势"      # 直接出行业洞察报告 [需 DashScope + Tavily]
    python main.py advise "我们电池厂该不该去马来西亚建厂"  # 多Agent投资顾问 [需 DashScope + Tavily]
    python server/main.py                              # 启动 Web 后端 (FastAPI :8000)
    # 前端网页: 另开终端 cd web 后 pnpm dev (Next.js :3000)
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def cmd_ask(args):
    from src.agent.react_agent import Assistant
    for chunk in Assistant().execute_stream(args.query):
        print(chunk, end="", flush=True)
    print()


def cmd_report(args):
    from src.reporting.report_service import ReportService
    print(ReportService().generate(args.topic))


def cmd_advise(args):
    """多 Agent 投资顾问 (Supervisor + 子Agent)。"""
    from src.graph.supervisor import InvestmentAdvisor
    for chunk in InvestmentAdvisor().execute_stream(args.query):
        print(chunk, end="", flush=True)
    print()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="AI Assistant CLI (RAG + online-search decisions)")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("ask", help="Chat with the Agent (auto-routing)")
    a.add_argument("query", type=str)
    a.set_defaults(func=cmd_ask)

    r = sub.add_parser("report", help="Generate an industry-insight report")
    r.add_argument("topic", type=str)
    r.set_defaults(func=cmd_report)

    ad = sub.add_parser("advise", help="Multi-agent investment advisor (Supervisor + sub-agents)")
    ad.add_argument("query", type=str)
    ad.set_defaults(func=cmd_advise)
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()
    args.func(args)
