"""Supervisor 多 Agent 编排 (LangGraph StateGraph) + 短期记忆 + 实时进度事件。

流程：START -> triage -> (general | supervisor -> 子Agent... -> advisor) -> END
- triage：意图分诊；同时**重置本轮调研草稿**(visited/notes)，与跨会话的对话历史(messages)分离
- supervisor：判断下一步派谁 / 是否收尾 (LLM 路由 + 规则兜底 + 防死循环)
- 子Agent：写入各自 notes，回到 supervisor
- advisor：汇总出结构化建议
- 短期记忆：checkpointer 按 thread_id 持久化对话历史(messages)
- 实时进度：各节点执行中经 emit_event 推送 phase/route/tool 事件 (custom 流)，供前端"看见内部执行"
"""
import sqlite3
from typing import TypedDict, Annotated, Literal

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import Command
from langchain_core.messages import AIMessage

from src.models.factory import chat_model
from src.agent.subagents import run_research, run_knowledge, run_analysis
from src.agent.advisor import build_advice, format_advice_md
from src.utils.robust import retry
from src.utils.config import multiagent_conf, abs_of
from src.utils.logger import logger
from src.utils.stream import emit_event

_RESET = "__reset__"


def _visited_reducer(current, update):
    """visited 累加器：支持 _RESET 本轮清零(对话历史持久 vs 调研草稿每轮重置)。"""
    if update == _RESET:
        return []
    return (current or []) + (update or [])


class InvestState(TypedDict):
    messages: Annotated[list, add_messages]          # 跨会话持久 (短期记忆)
    query: str
    mode: str                                        # triage 结果: general / supervisor
    internal_notes: str
    research_notes: str
    analysis_notes: str
    visited: Annotated[list[str], _visited_reducer]  # 每轮重置 (本轮已调研的子Agent)
    recommendation: dict
    findings: dict                                   # 调研详情(给报告/PDF附录)


WORKERS = {"knowledge": "internal_notes", "research": "research_notes", "analysis": "analysis_notes"}
_LABEL = {"knowledge": "Internal Knowledge", "research": "Industry Research", "analysis": "Quant Analysis"}

_general_agent = None


def _phase(agent: str, label: str, status: str, **extra):
    emit_event({"type": "phase", "agent": agent, "label": label, "status": status, **extra})


@retry()
def _classify(query: str) -> str:
    """意图分诊：advisory(投资决策类) / general(其他)。"""
    resp = chat_model.invoke(
        "Classify which category the user input belongs to; reply with exactly one English word:\n"
        "- advisory: the user is seeking a clear investment [decision] for their own company "
        "(whether to invest / whether to build a plant / site selection / whether to expand / feasibility), "
        "which needs combined research + quant analysis + a conclusion.\n"
        "- general: everything else (greetings/small talk, looking up meeting minutes, checking industry news, "
        "introducing/explaining/analyzing something, summarizing key points). Note: 'introduce/understand/analyze "
        "something' is NOT an investment decision — it is general.\n"
        f"User input: {query}\nAnswer: "
    ).content.strip().lower()
    return resp


def triage_node(state: InvestState) -> Command[Literal["general", "supervisor"]]:
    """总入口：分诊意图，并重置本轮调研草稿(对话历史 messages 不动)。"""
    _phase("triage", "Intent Triage", "running")
    try:
        kind = _classify(state["query"])
    except Exception as e:
        logger.warning(f"[Triage] 分诊失败, 默认 general: {e}")
        kind = "general"
    goto = "supervisor" if "advis" in kind else "general"
    mode = "advisory" if goto == "supervisor" else "general"
    logger.info(f"[Triage] 意图={kind} -> {goto}")
    reason = (
        "Classified as 『Investment Decision』: the user is seeking a clear investment recommendation → "
        "launch multi-agent (Internal Knowledge / Industry Research / Quant Analysis → structured advice)"
        if mode == "advisory"
        else "Classified as 『General Q&A』: a lookup/understanding/consulting question, not an investment "
        "decision → answered directly by the general assistant (auto-selecting RAG or web search)"
    )
    _phase("triage", "Intent Triage", "done", mode=mode, detail=reason)
    reset = {
        "visited": _RESET,
        "internal_notes": "", "research_notes": "", "analysis_notes": "",
        "recommendation": {},
    }
    return Command(goto=goto, update={"mode": goto, **reset})


def general_node(state: InvestState) -> dict:
    """简单问答：单 Agent 流式作答(打字机) + 工具事件，带上对话历史(短期记忆)。"""
    global _general_agent
    from src.agent.react_agent import Assistant
    if _general_agent is None:
        _general_agent = Assistant()
    _phase("general", "Assistant", "running")
    answer = ""
    ntok = nreason = 0
    for ev in _general_agent.stream_run(state["messages"]):
        kind = ev[0]
        if kind == "reasoning":
            nreason += 1
            emit_event({"type": "reasoning", "agent": "general", "delta": ev[1]})
        elif kind == "token":
            ntok += 1
            emit_event({"type": "token", "content": ev[1]})
        elif kind == "tool":
            logger.info(f"[general] 调用工具 {ev[1]} 入参={ev[2]}")
            emit_event({"type": "tool", "agent": "general", "tool": ev[1], "args": ev[2]})
        elif kind == "result":
            emit_event({"type": "tool_result", "agent": "general", "tool": ev[1], "preview": ev[2]})
        elif kind == "final":
            answer = ev[1]
    logger.info(f"[general] 思考链块={nreason}, 答案 token={ntok}")
    answer = answer or "(No answer.)"
    _phase("general", "Assistant", "done")
    return {"messages": [AIMessage(content=answer)]}


@retry()
def _select_experts(query: str) -> list[str]:
    """Supervisor 一次性选出本次要【并行】调用的专家。

    默认 research+analysis；仅当问题明确涉及内部纪要/会员经验时才加 knowledge。
    """
    resp = chat_model.invoke(
        "Investment-decision question. Choose which experts to call in [parallel].\n"
        "By default use only research (industry research / web) + analysis (quant analysis);\n"
        "add knowledge (internal minutes) ONLY when the question clearly involves "
        "[chamber internal minutes / member experience / existing resolutions].\n"
        f"Question: {query}\nReply with English keys (comma-separated): "
    ).content.strip().lower()
    picked = [w for w in WORKERS if w in resp]
    for w in ("research", "analysis"):       # 至少 research + analysis
        if w not in picked:
            picked.append(w)
    return picked


def supervisor_node(state: InvestState) -> Command:
    """一次性决策并【并行】派发专家 → 汇到 advisor (不再串行循环, 大幅提速)。"""
    try:
        experts = _select_experts(state["query"])
    except Exception as e:
        logger.warning(f"[Supervisor] 选专家失败, 默认 research+analysis: {e}")
        experts = ["research", "analysis"]
    labels = ", ".join(_LABEL[w] for w in experts)
    logger.info(f"[Supervisor] 并行派发 -> {experts}")
    emit_event({"type": "route", "to": "parallel", "label": f"Parallel dispatch → {labels}"})
    return Command(goto=experts)


def _worker(name: str, runner):
    label = _LABEL[name]

    def node(state: InvestState) -> dict:
        _phase(name, label, "running")
        notes = runner(state["query"])           # 子Agent内部会经 emit_event 推送 reasoning/tool
        _phase(name, label, "done", detail=notes)  # 该专家结论(供前端展开)
        return {WORKERS[name]: notes}              # 并行: 各写各的 notes, 无需回 supervisor

    node.__name__ = f"{name}_node"
    return node


knowledge_node = _worker("knowledge", run_knowledge)
research_node = _worker("research", run_research)
analysis_node = _worker("analysis", run_analysis)


def advisor_node(state: InvestState) -> dict:
    _phase("advisor", "Synthesize Advice", "running")
    advice = build_advice(state)
    _phase("advisor", "Synthesize Advice", "done")
    findings = {
        "research": state.get("research_notes", ""),
        "analysis": state.get("analysis_notes", ""),
        "internal": state.get("internal_notes", ""),
    }
    return {"recommendation": advice, "findings": findings,
            "messages": [AIMessage(content=format_advice_md(advice))]}


def _make_checkpointer():
    """短期记忆：优先 SqliteSaver(持久, 跨重启); 失败降级 MemorySaver(进程内)。"""
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        path = abs_of("memory_db")
        conn = sqlite3.connect(path, check_same_thread=False)
        cp = SqliteSaver(conn)
        cp.setup()
        logger.info(f"[Memory] 短期记忆 SqliteSaver -> {path}")
        return cp
    except Exception as e:
        from langgraph.checkpoint.memory import MemorySaver
        logger.warning(f"[Memory] SqliteSaver 不可用, 降级 MemorySaver: {e}")
        return MemorySaver()


def build_graph(checkpointer=None):
    g = StateGraph(InvestState)
    g.add_node("triage", triage_node)
    g.add_node("general", general_node)
    g.add_node("supervisor", supervisor_node)
    g.add_node("knowledge", knowledge_node)
    g.add_node("research", research_node)
    g.add_node("analysis", analysis_node)
    g.add_node("advisor", advisor_node)
    g.add_edge(START, "triage")
    g.add_edge("general", END)
    g.add_edge("knowledge", "advisor")  # 并行专家 → advisor 汇合(join)
    g.add_edge("research", "advisor")
    g.add_edge("analysis", "advisor")
    g.add_edge("advisor", END)
    return g.compile(checkpointer=checkpointer)


class InvestmentAdvisor:
    """对外门面：分诊 + 多Agent + 短期记忆(按 thread_id 续上会话)。"""

    def __init__(self, checkpointer=None):
        self.checkpointer = checkpointer if checkpointer is not None else _make_checkpointer()
        self.app = build_graph(self.checkpointer)
        self._limit = multiagent_conf.get("recursion_limit", 25)

    def _config(self, thread_id: str = None) -> dict:
        return {"recursion_limit": self._limit,
                "configurable": {"thread_id": thread_id or "default"}}

    def _input(self, query: str) -> dict:
        return {"query": query, "messages": [{"role": "user", "content": query}]}

    def run(self, query: str, thread_id: str = None) -> str:
        final = self.app.invoke(self._input(query), config=self._config(thread_id))
        return final["messages"][-1].content

    def get_messages(self, thread_id: str = None) -> list:
        """取某会话的完整历史 (供前端展示 / 自动提炼)。"""
        st = self.app.get_state(self._config(thread_id))
        return st.values.get("messages", []) if st else []

    def maybe_learn(self, thread_id: str = None):
        """阶段3b：对话结束自动提炼事实更新全局档案 (受 auto_extract 开关控制)。"""
        try:
            from src.memory.profile import auto_update_from_messages
            return auto_update_from_messages(self.get_messages(thread_id))
        except Exception as e:
            logger.warning(f"[Memory] 自动提炼失败, 跳过: {e}")
            return None

    def execute_events(self, query: str, thread_id: str = None):
        """结构化事件流 (供前端/SSE)。

        custom 通道：phase / route / tool (实时进度)；
        updates 通道：general 的 message、advisor 的 final。
        """
        cfg = self._config(thread_id)
        for mode, chunk in self.app.stream(
            self._input(query), stream_mode=["updates", "custom"], config=cfg
        ):
            if mode == "custom":
                yield chunk                       # phase/route/tool: 已是规范事件
            elif mode == "updates":
                for node, update in chunk.items():
                    if not update:
                        continue
                    if node == "general" and update.get("messages"):
                        yield {"type": "message", "role": "assistant",
                               "content": update["messages"][-1].content}
                    elif node == "advisor" and update.get("messages"):
                        yield {"type": "final", "content": update["messages"][-1].content,
                               "report": update.get("recommendation"),
                               "findings": update.get("findings")}
        yield {"type": "done"}

    def execute_stream(self, query: str, thread_id: str = None):
        """字符串流 (CLI 兼容)：基于 execute_events 适配关键里程碑。"""
        for ev in self.execute_events(query, thread_id):
            t = ev.get("type")
            if t == "phase" and ev.get("status") == "done":
                if ev["agent"] == "triage":
                    yield "🧭 Investment Decision\n" if ev.get("mode") == "advisory" else "💬 General Q&A\n"
                elif ev["agent"] in WORKERS:
                    yield f"【{ev['label']}】done\n"
            elif t == "tool":
                yield f"  ↳ {ev['agent']} called {ev['tool']}\n"
            elif t in ("message", "final"):
                yield ev["content"] + "\n"


if __name__ == "__main__":
    advisor = InvestmentAdvisor()
    for c in advisor.execute_stream("我们商会一家电池厂该不该去马来西亚建厂？"):
        print(c, end="", flush=True)
