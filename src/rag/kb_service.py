"""知识库上传摄取：文档抽取 / 音视频转写 → 文本 → 入 RAG(Chroma+BM25) + 注册表。

- 文档(txt/md/pdf/docx)：抽取文本(同步, 快)
- 音视频(mp3/wav/m4a/mp4…)：ffmpeg 转 16k 单声道 → 分段 → DashScope ASR 转写(慢, 走后台任务)
- 入库：复用共享的 MeetingKB.store(同一个 Chroma 集合) + 保存文本到 kb_dir(供 BM25) + MD5 去重
- 检索器缓存失效：入库/删除后置 kb._retriever=None, 下次检索自动重建(含新文档)
"""
import glob
import json
import os
import re
import subprocess
import tempfile
import time

from src.utils.config import abs_of, kb_conf
from src.utils.files import md5_of_text, read_text
from src.utils.logger import logger

DOC_EXT = {".txt", ".md", ".pdf", ".docx"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm"}


def kind_of(name: str) -> str | None:
    ext = os.path.splitext(name)[1].lower()
    if ext in DOC_EXT:
        return "doc"
    if ext in AUDIO_EXT:
        return "audio"
    if ext in VIDEO_EXT:
        return "video"
    return None


def _kb_dir() -> str:
    return abs_of("kb_dir")


def _registry_path() -> str:
    return os.path.join(_kb_dir(), "registry.json")


def _load_registry() -> dict:
    try:
        with open(_registry_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_registry(reg: dict) -> None:
    os.makedirs(_kb_dir(), exist_ok=True)
    with open(_registry_path(), "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)


def _shared_kb():
    """共享 MeetingKB 单例(与内部知识 Agent 同一实例, 入库后它即可检索)。"""
    from src.agent.tools import _meeting_kb
    return _meeting_kb()


def _safe_stem(name: str) -> str:
    stem = os.path.splitext(os.path.basename(name))[0]
    stem = re.sub(r"[^\w一-鿿.-]", "_", stem)[:40]
    return stem or "doc"


# ---------------- 文本抽取 ----------------

def extract_text(path: str, ext: str) -> str:
    if ext in (".txt", ".md"):
        return read_text(path)
    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(path)
        return "\n".join((pg.extract_text() or "") for pg in reader.pages)
    if ext == ".docx":
        import docx
        d = docx.Document(path)
        return "\n".join(p.text for p in d.paragraphs)
    return ""


# ---------------- 音视频转写 (ffmpeg + DashScope ASR) ----------------

def _ffmpeg(args: list[str]) -> None:
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args],
                   check=True, capture_output=True)


def transcribe(src_path: str) -> str:
    """音视频 → 16k 单声道 wav → 分段 → DashScope ASR → 文本。"""
    from dashscope.audio.asr import Recognition
    model = kb_conf.get("asr_model", "paraformer-realtime-v2")
    seg = int(kb_conf.get("asr_segment_seconds", 60))
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, "audio.wav")
        _ffmpeg(["-i", src_path, "-vn", "-ar", "16000", "-ac", "1", wav])   # 视频自动抽音轨
        _ffmpeg(["-i", wav, "-f", "segment", "-segment_time", str(seg),
                 "-ar", "16000", "-ac", "1", os.path.join(td, "seg_%04d.wav")])
        segs = sorted(glob.glob(os.path.join(td, "seg_*.wav"))) or [wav]
        texts: list[str] = []
        for s in segs:
            try:
                rec = Recognition(model=model, format="wav", sample_rate=16000, callback=None)
                r = rec.call(s)
                if getattr(r, "status_code", None) != 200:
                    logger.warning(f"[KB] ASR 段失败 status={getattr(r, 'status_code', None)}")
                    continue
                sents = r.get_sentence() or []
                if isinstance(sents, dict):
                    sents = [sents]
                for it in sents:
                    t = it.get("text") if isinstance(it, dict) else None
                    if t:
                        texts.append(t)
            except Exception as e:
                logger.warning(f"[KB] ASR 段异常: {e}")
        return "\n".join(texts).strip()


# ---------------- 入库 / 列表 / 删除 ----------------

def ingest_text(text: str, name: str, kind: str) -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("未提取到文本内容")
    doc_id = md5_of_text(text)
    kb = _shared_kb()
    chunks = kb.store.add_document(text, doc_id=doc_id, metadata={"source": name, "kind": kind})
    os.makedirs(_kb_dir(), exist_ok=True)
    text_file = f"{_safe_stem(name)}__{doc_id[:8]}.txt"
    with open(os.path.join(_kb_dir(), text_file), "w", encoding="utf-8") as f:
        f.write(text)                       # 持久 + 供 BM25(load_chunks 会扫 kb_dir)
    kb._mark(doc_id)                         # MD5 台账
    kb._retriever = None                     # 失效检索器缓存
    reg = _load_registry()
    reg[doc_id] = {"id": doc_id, "name": name, "kind": kind, "chars": len(text),
                   "chunks": chunks, "added_at": time.time(), "text_file": text_file}
    _save_registry(reg)
    logger.info(f"[KB] 入库 {name} ({kind}) -> {chunks} 分块")
    return reg[doc_id]


def process_upload(raw_path: str, name: str) -> dict:
    """根据类型抽取/转写 → 入库。返回该文档的注册信息。"""
    ext = os.path.splitext(name)[1].lower()
    kind = kind_of(name)
    if kind == "doc":
        text = extract_text(raw_path, ext)
    elif kind in ("audio", "video"):
        text = transcribe(raw_path)
    else:
        raise ValueError(f"不支持的文件类型: {ext}")
    return ingest_text(text, name, kind)


def list_docs() -> list[dict]:
    return sorted(_load_registry().values(), key=lambda d: d.get("added_at", 0), reverse=True)


def delete_doc(doc_id: str) -> bool:
    kb = _shared_kb()
    kb.store.delete_document(doc_id)
    reg = _load_registry()
    info = reg.pop(doc_id, None)
    if info and info.get("text_file"):
        tp = os.path.join(_kb_dir(), info["text_file"])
        if os.path.exists(tp):
            os.remove(tp)
    _save_registry(reg)
    # 从 MD5 台账移除(允许日后重新上传)
    try:
        if os.path.exists(kb.ledger_path):
            kept = [ln for ln in read_text(kb.ledger_path).splitlines() if ln.strip() and ln.strip() != doc_id]
            with open(kb.ledger_path, "w", encoding="utf-8") as f:
                f.write("\n".join(kept) + ("\n" if kept else ""))
    except Exception as e:
        logger.warning(f"[KB] 台账清理失败: {e}")
    kb._retriever = None
    logger.info(f"[KB] 已删除文档 {doc_id}")
    return True
