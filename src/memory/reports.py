"""投资报告记录：每次生成投资建议时落盘，供"决策记录"页回看。"""
import json
import os
import time
import uuid

from src.utils.config import abs_of
from src.utils.logger import logger


def _path() -> str:
    return abs_of("reports_json")


def _load() -> dict:
    try:
        with open(_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(_path()), exist_ok=True)
    with open(_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_report(thread_id: str, question: str, report: dict, findings: dict) -> dict:
    rid = uuid.uuid4().hex[:10]
    rec = {
        "id": rid,
        "thread_id": thread_id,
        "question": question,
        "decision": report.get("decision", ""),
        "confidence": report.get("confidence", ""),
        "report": report,
        "findings": findings or {},
        "created_at": time.time(),
    }
    data = _load()
    data[rid] = rec
    _save(data)
    logger.info(f"[Reports] 已记录决策 {rid} ({rec['decision']})")
    return rec


def list_reports() -> list[dict]:
    """列表(轻量字段, 不带完整 report)，按时间倒序。"""
    items = sorted(_load().values(), key=lambda r: r.get("created_at", 0), reverse=True)
    return [
        {k: r.get(k) for k in ("id", "thread_id", "question", "decision", "confidence", "created_at")}
        for r in items
    ]


def get_report(rid: str) -> dict | None:
    return _load().get(rid)


def delete_report(rid: str) -> bool:
    data = _load()
    if rid in data:
        data.pop(rid)
        _save(data)
        return True
    return False
