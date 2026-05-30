"""会话注册表：记录历史会话(id/标题/时间)，供前端列出与切换。

与短期记忆分工：checkpointer(memory.sqlite) 存每个会话的完整消息；
本注册表只存"有哪些会话 + 标题 + 更新时间"的轻量索引。
"""
import json
import os
import time

from src.utils.config import abs_of
from src.utils.logger import logger


def _path() -> str:
    return abs_of("threads_json")


def list_threads() -> list[dict]:
    """按更新时间倒序返回会话列表。"""
    try:
        with open(_path(), encoding="utf-8") as f:
            data = json.load(f)
        return sorted(data, key=lambda t: t.get("updated_at", 0), reverse=True)
    except FileNotFoundError:
        return []
    except Exception as e:
        logger.warning(f"[Threads] 读取失败: {e}")
        return []


def touch_thread(thread_id: str, message: str) -> dict:
    """新建或更新会话。新会话用首条消息作标题。"""
    items = {t["id"]: t for t in list_threads()}
    now = time.time()
    if thread_id in items:
        items[thread_id]["updated_at"] = now
    else:
        title = (message or "新对话").strip().replace("\n", " ")
        if len(title) > 24:
            title = title[:24] + "…"
        items[thread_id] = {"id": thread_id, "title": title, "created_at": now, "updated_at": now}
    os.makedirs(os.path.dirname(_path()), exist_ok=True)
    with open(_path(), "w", encoding="utf-8") as f:
        json.dump(list(items.values()), f, ensure_ascii=False, indent=2)
    return items[thread_id]
