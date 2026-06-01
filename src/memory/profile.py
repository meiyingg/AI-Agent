"""长期记忆：全局企业档案 (单一档案, 跨会话)。

设计取向 (对齐 Letta/MemGPT 等工业实践)：
- 这是一份**小而总相关的"核心档案"** —— 每次都直接注入提示词, 不走向量检索;
  档案小且总相关时, 直接注入比 RAG 更稳 (不会"该带的没检索到")。
- 与"会议纪要文档 RAG"是**两套独立的库**：
  本模块存"企业自身的事实"(读+写+更新, 动态)；RAG 存"知识文档"(只读, 检索)。
- 注入处：general(通用助手, 经 dynamic_prompt 中间件) + advisor(投资建议, 经 LCEL 模板)。

阶段 3a：手动可靠 —— 档案由 UI/API 读写, 模型只读注入。
阶段 3b：在此之上加"对话结束 LLM 自动提炼事实"(见 update_facts)。
"""
import json
import os
import re

from src.utils.config import abs_of, memory_conf
from src.utils.logger import logger

# 单一全局档案的字段
_DEFAULT = {
    "profile": "",       # 企业画像 (一句话: 行业/规模/主营/市场)
    "preferences": "",   # 偏好 (风险偏好/关注点/约束)
    "facts": [],         # 关键事实列表 (有上限, 防膨胀)
    "history": "",       # 历史结论摘要 (过往建议的浓缩)
}


def _path() -> str:
    return abs_of("profile_json")


def load_profile() -> dict:
    """读取全局档案; 不存在或损坏则返回空档案 (不崩)。"""
    try:
        with open(_path(), encoding="utf-8") as f:
            data = json.load(f)
        return {**_DEFAULT, **data}
    except FileNotFoundError:
        return dict(_DEFAULT)
    except Exception as e:
        logger.warning(f"[Profile] 读取失败, 用空档案: {e}")
        return dict(_DEFAULT)


def save_profile(data: dict) -> dict:
    """合并写入 (只接受已知字段); facts 截断到上限。返回写入后的完整档案。"""
    cur = load_profile()
    for k in _DEFAULT:
        if k in data and data[k] is not None:
            cur[k] = data[k]
    cap = memory_conf.get("profile_max_facts", 12)
    if isinstance(cur.get("facts"), list):
        # 去重保序 + 截断
        seen, uniq = set(), []
        for f in cur["facts"]:
            if f and f not in seen:
                seen.add(f)
                uniq.append(f)
        cur["facts"] = uniq[:cap]
    os.makedirs(os.path.dirname(_path()), exist_ok=True)
    with open(_path(), "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False, indent=2)
    logger.info(f"[Profile] 已更新全局档案 (facts={len(cur.get('facts', []))})")
    return cur


def add_facts(new_facts: list[str]) -> dict:
    """追加关键事实 (阶段 3b 自动抽取用); 去重 + 截断。"""
    cur = load_profile()
    cur["facts"] = (cur.get("facts") or []) + [f for f in new_facts if f]
    return save_profile(cur)


def profile_text() -> str:
    """渲染成可注入提示词的简短文本; 关闭注入或空档案则返回 ''。"""
    if not memory_conf.get("profile_inject", True):
        return ""
    p = load_profile()
    lines = []
    if p.get("profile"):
        lines.append(f"Company profile: {p['profile']}")
    if p.get("preferences"):
        lines.append(f"Preferences: {p['preferences']}")
    if p.get("facts"):
        lines.append("Key facts: " + "; ".join(p["facts"]))
    if p.get("history"):
        lines.append(f"Past conclusions: {p['history']}")
    if not lines:
        return ""
    return "[Company long-term profile (background reference, not a hard constraint)]\n" + "\n".join(lines)


# ============================================================
# 阶段 3b：对话结束自动提炼事实 (受 memory.auto_extract 开关控制)
# ============================================================

def _messages_to_text(messages, limit: int = 12) -> str:
    """把最近若干条消息转成'用户/助手'文本, 供提炼。兼容 LangChain 消息与 dict。"""
    out = []
    for m in (messages or [])[-limit:]:
        role = getattr(m, "type", None) or (m.get("role") if isinstance(m, dict) else "?")
        content = getattr(m, "content", None)
        if content is None and isinstance(m, dict):
            content = m.get("content", "")
        if content:
            tag = {"human": "User", "user": "User", "ai": "Assistant", "assistant": "Assistant"}.get(role, role)
            out.append(f"{tag}: {content}")
    return "\n".join(out)


def extract_facts(conversation: str) -> list[str]:
    """从对话中提炼值得长期记住的企业关键信息 (最多6条短句)。"""
    from src.models.factory import chat_model
    resp = chat_model.invoke(
        "You maintain a company's long-term profile. From the conversation below, distill the key company "
        "information worth remembering long-term: industry, main products, target markets, size, risk appetite, "
        "and important progress or decisions (e.g. approvals/site selection/production start/partnerships/financing).\n"
        "Rules: one objective, specific sentence each; it may be important progress (need not be a permanent "
        "attribute); reply NONE only if the conversation has no company-related info at all.\n"
        "Output one item per line, with no numbering, explanation, or pleasantries.\n\n"
        f"Conversation:\n{conversation}\n\nKey company info: "
    ).content.strip()
    if not resp or resp.upper().startswith("NONE"):
        return []
    facts = []
    for ln in resp.splitlines():
        ln = re.sub(r"^[\-\*•\d\.\)、\s]+", "", ln).strip()   # 去掉行首项目符号/编号
        if ln and ln.upper() != "NONE":
            facts.append(ln)
    return facts[:6]


def auto_update_from_messages(messages) -> dict | None:
    """阶段3b 入口：开关开启时, 从对话提炼事实并并入全局档案; 否则 no-op。"""
    if not memory_conf.get("auto_extract", False):
        return None
    convo = _messages_to_text(messages)
    if not convo:
        return None
    facts = extract_facts(convo)
    if facts:
        logger.info(f"[Profile] 自动提炼 {len(facts)} 条事实并入档案")
        return add_facts(facts)
    return None
