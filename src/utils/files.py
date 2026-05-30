"""文件相关工具：MD5 指纹、文本读取、目录遍历。"""
import os
import hashlib
from src.utils.logger import logger


def md5_of_text(text: str) -> str:
    """计算字符串内容的 MD5，用于采集去重。"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def md5_of_file(filepath: str, chunk_size: int = 4096) -> str | None:
    """分块计算文件 MD5，避免大文件爆内存。"""
    if not os.path.isfile(filepath):
        logger.error(f"[md5] 不是文件: {filepath}")
        return None
    md5 = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(chunk_size):
                md5.update(chunk)
        return md5.hexdigest()
    except Exception as e:
        logger.error(f"[md5] 计算失败 {filepath}: {e}")
        return None


def read_text(filepath: str, encoding: str = "utf-8") -> str:
    """读取纯文本文件内容。"""
    with open(filepath, "r", encoding=encoding) as f:
        return f.read()


def list_files(directory: str, exts: tuple[str, ...]) -> list[str]:
    """列出目录下指定后缀的文件 (绝对路径)。"""
    if not os.path.isdir(directory):
        logger.warning(f"[list_files] 目录不存在: {directory}")
        return []
    return [
        os.path.join(directory, f)
        for f in sorted(os.listdir(directory))
        if f.lower().endswith(exts)
    ]
