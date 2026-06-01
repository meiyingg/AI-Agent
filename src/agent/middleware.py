"""Agent 中间件：
1. monitor_tool         —— 包裹每次工具调用 (日志 + 报告模式信号)
2. log_before_model     —— 每次调用模型前记日志
3. report_prompt_switch —— 动态切换系统提示词 (普通问答 <-> 报告撰写)

报告模式切换原理 (tool-as-signal)：
用户要出报告 -> Agent 调用 generate_decision_report ->
monitor_tool 检测到该工具 -> 置 runtime.context['report']=True ->
下一次模型调用时 report_prompt_switch 改用报告撰写提示词。
"""
from datetime import date
from typing import Callable
from langchain.agents import AgentState
from langchain.agents.middleware import wrap_tool_call, before_model, dynamic_prompt, ModelRequest
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command
from src.utils.logger import logger
from src.utils.paths import get_abs_path
from src.utils.files import read_text
from src.utils.config import agent_conf


def _system_prompt() -> str:
    return read_text(get_abs_path(agent_conf["system_prompt_path"]))


def _report_prompt() -> str:
    return read_text(get_abs_path(agent_conf["report_prompt_path"]))


@wrap_tool_call
def monitor_tool(
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    name = request.tool_call["name"]
    logger.info(f"[tool monitor] 执行工具: {name} | 参数: {request.tool_call['args']}")
    try:
        result = handler(request)
        logger.info(f"[tool monitor] 工具 {name} 调用成功")
        if name == "generate_decision_report":
            request.runtime.context["report"] = True
            logger.info("[middleware] 已切换到报告撰写模式")
        return result
    except Exception as e:
        logger.error(f"[tool monitor] 工具 {name} 调用失败: {e}")
        raise


@before_model
def log_before_model(state: AgentState, runtime: Runtime):
    logger.info(f"[before_model] 即将调用模型，当前消息数: {len(state['messages'])}")
    return None


def _with_today(prompt: str) -> str:
    """在提示词最前面注入当前日期，解决模型'不知道今天几号'导致只搜旧年份的问题。"""
    today = date.today().isoformat()
    header = (
        f"[Current date] Today is {today}.\n"
        f"For any question about 'latest / recent / current status', retrieve based on this date; do not hard-code "
        f"stale years; when needed, prioritize content from the last year, especially the last 30 days.\n\n"
    )
    return header + prompt


@dynamic_prompt
def report_prompt_switch(request: ModelRequest) -> str:
    base = _report_prompt() if request.runtime.context.get("report", False) else _system_prompt()
    prompt = _with_today(base)
    # 注入长期记忆(全局企业档案), 每次模型调用都取最新, 手改后立即生效
    try:
        from src.memory.profile import profile_text
        prof = profile_text()
        if prof:
            prompt = f"{prompt}\n\n{prof}"
    except Exception as e:
        logger.warning(f"[Profile] 注入失败, 跳过: {e}")
    return prompt
