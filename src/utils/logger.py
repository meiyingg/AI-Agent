"""统一日志：同时输出到控制台和按日期分文件的日志文件。"""
import logging
import os
from datetime import datetime
from src.utils.paths import get_abs_path

LOG_ROOT = get_abs_path("logs")
os.makedirs(LOG_ROOT, exist_ok=True)

LOG_FORMAT = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
)


def get_logger(name: str = "mia", console_level: int = logging.INFO,
               file_level: int = logging.DEBUG) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    if logger.handlers:                 # 避免重复添加 handler
        return logger

    console = logging.StreamHandler()
    console.setLevel(console_level)
    console.setFormatter(LOG_FORMAT)
    logger.addHandler(console)

    log_file = os.path.join(LOG_ROOT, f"{name}_{datetime.now().strftime('%Y%m%d')}.log")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(file_level)
    file_handler.setFormatter(LOG_FORMAT)
    logger.addHandler(file_handler)
    return logger


logger = get_logger()


if __name__ == "__main__":
    logger.info("info 日志")
    logger.warning("warning 日志")
    logger.error("error 日志")
