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


WORKERS = {"knowledge": "internal_notes", "research": "research_notes", "analysis": "analysis_notes"}
_LABEL = {"knowledge": "内部知识", "research": "行业调研", "analysis": "量化分析"}

_general_agent = None


def _phase(agent: str, label: str, status: str, **extra):
    emit_event({"type": "phase", "agent": agent, "label": label, "status": status, **extra})


@retry()
def _classify(query: str) -> str:
    """意图分诊：advisory(投资决策类) / general(其他)。"""
    resp = chat_model.invoke(
        "判断用户输入属于哪类，只回一个英文词：\n"
        "- advisory：用户在为自己企业求一个明确的投资【决策】"
        "(要不要投/该不该建厂/选址/是否扩产/可行性)，需要综合调研+量化分析+给结论。\n"
        "- general：其他所有(问候闲聊、查会议纪要、查行业资讯、"
        "介绍/科普/分析某事物、要点总结)。注意：'介绍/了解/分析某事物'不是投资决策，属于 general。\n"
        f"用户输入：{query}\n答："
    ).content.strip().lower()
    return resp


def triage_node(state: InvestState) -> Command[Literal["general", "supervisor"]]:
    """总入口：分诊意图，并重置本轮调研草稿(对话历史 messages 不动)。"""
    _phase("triage", "意图分诊", "running")
    try:
        kind = _classify(state["query"])
    except Exception as e:
        logger.warning(f"[Triage] 分诊失败, 默认 general: {e}")
        kind = "general"
    goto = "supervisor" if "advis" in kind else "general"
    mode = "advisory" if goto == "supervisor" else "general"
    logger.info(f"[Triage] 意图={kind} -> {goto}")
    reason = (
        "判定为『投资决策』：用户在为企业求明确投资建议 → 启动多Agent(内部知识/行业调研/量化分析 → 结构化建议)"
        if mode == "advisory"
        else "判定为『一般问答』：查询/了解/咨询类，非投资决策 → 交通用助手(自动选 RAG 或联网)直接作答"
    )
    _phase("triage", "意图分诊", "done", mode=mode, detail=reason)
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
    _phase("general", "通用助手作答", "running")
    answer = ""
    ntok = nreason = 0
    for ev in _general_agent.stream_run(state["messages"]):
        kind = ev[0]
        if kind == "reasoning":
            nreason += 1
            emit_event({"type": "reasoning", "agent": "通用助手", "delta": ev[1]})
        elif kind == "token":
            ntok += 1
            emit_event({"type": "token", "content": ev[1]})
        elif kind == "tool":
            logger.info(f"[general] 调用工具 {ev[1]} 入参={ev[2]}")
            emit_event({"type": "tool", "agent": "通用助手", "tool": ev[1], "args": ev[2]})
        elif kind == "result":
            emit_event({"type": "tool_result", "agent": "通用助手", "tool": ev[1], "preview": ev[2]})
        elif kind == "final":
            answer = ev[1]
    logger.info(f"[general] 思考链块={nreason}, 答案 token={ntok}")
    answer = answer or "（未获得回答）"
    _phase("general", "通用助手作答", "done")
    return {"messages": [AIMessage(content=answer)]}


@retry()
def _llm_route(query: str, options: list[str]) -> str:
    desc = "knowledge=内部知识, research=行业调研, analysis=量化分析, advisor=出建议"
    resp = chat_model.invoke(
        f"企业问题：{query}\n候选下一步：{options}（{desc}）。\n"
        f"只回一个英文词，从 {options} 中选当前最该做的一步："
    ).content.strip().lower()
    return resp


def supervisor_node(state: InvestState) -> Command[Literal["knowledge", "research", "analysis", "advisor"]]:
    visited = state.get("visited", [])
    remaining = [w for w in WORKERS if w not in visited]
    max_rounds = multiagent_conf.get("max_rounds", 6)
    min_workers = multiagent_conf.get("min_workers", 2)

    # 没有可调的子Agent了 / 达上限 -> 出建议
    if not remaining or len(visited) >= max_rounds:
        logger.info(f"[Supervisor] 调研完毕 -> advisor (已访问:{visited})")
        emit_event({"type": "route", "to": "advisor", "label": "调研充分 → 生成投资建议"})
        return Command(goto="advisor")

    # 调研不足 min_workers 时，禁止过早出 advisor，只在子Agent里选
    allow_advisor = len(visited) >= min_workers
    options = remaining + (["advisor"] if allow_advisor else [])

    try:
        resp = _llm_route(state["query"], options)
        nxt = next((w for w in options if w in resp), remaining[0])
    except Exception as e:
        logger.warning(f"[Supervisor] 路由失败, 规则兜底: {e}")
        nxt = remaining[0]

    logger.info(f"[Supervisor] 路由 -> {nxt} (已访问:{visited})")
    if nxt == "advisor":
        emit_event({"type": "route", "to": "advisor", "label": "调研充分 → 生成投资建议"})
    else:
        emit_event({"type": "route", "to": nxt, "label": f"Supervisor 派单 → {_LABEL[nxt]}"})
    return Command(goto=nxt)


def _worker(name: str, runner):
    label = _LABEL[name]

    def node(state: InvestState) -> Command[Literal["supervisor"]]:
        _phase(name, label, "running")
        notes = runner(state["query"])           # 子Agent内部会经 emit_event 推送 tool 事件
        _phase(name, label, "done", detail=notes)  # 把该专家的结论带上(供前端展开查看)
        return Command(goto="supervisor", update={WORKERS[name]: notes, "visited": [name]})

    node.__name__ = f"{name}_node"
    return node


knowledge_node = _worker("knowledge", run_knowledge)
research_node = _worker("research", run_research)
analysis_node = _worker("analysis", run_analysis)


def advisor_node(state: InvestState) -> dict:
    _phase("advisor", "汇总投资建议", "running")
    advice = build_advice(state)
    _phase("advisor", "汇总投资建议", "done")
    return {"recommendation": advice, "messages": [AIMessage(content=format_advice_md(advice))]}


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
                               "report": update.get("recommendation")}
        yield {"type": "done"}

    def execute_stream(self, query: str, thread_id: str = None):
        """字符串流 (CLI 兼容)：基于 execute_events 适配关键里程碑。"""
        for ev in self.execute_events(query, thread_id):
            t = ev.get("type")
            if t == "phase" and ev.get("status") == "done":
                if ev["agent"] == "triage":
                    yield "🧭 投资决策\n" if ev.get("mode") == "advisory" else "💬 一般问答\n"
                elif ev["agent"] in WORKERS:
                    yield f"【{ev['label']}】完成\n"
            elif t == "tool":
                yield f"  ↳ {ev['agent']} 调用 {ev['tool']}\n"
            elif t in ("message", "final"):
                yield ev["content"] + "\n"


if __name__ == "__main__":
    advisor = InvestmentAdvisor()
    for c in advisor.execute_stream("我们商会一家电池厂该不该去马来西亚建厂？"):
        print(c, end="", flush=True)
