"""健壮性装饰器：缓存 / 重试(指数退避) / 降级。

- cached  : 同入参直接命中，省时省钱 (用在确定性/可重复的工具上)
- retry   : 瞬时失败(网络/限流)自动重试 (用在 LLM/IO 调用上)
- degrade : 失败不崩溃，返回兜底值 (用在子Agent 节点上, 单点失败不拖垮整图)
"""
import time
import json
import hashlib
import functools
from src.utils.config import robust_conf
from src.utils.logger import logger


def _key(args, kwargs) -> str:
    raw = json.dumps([args, kwargs], default=str, ensure_ascii=False, sort_keys=True)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def cached(fn):
    """进程内简单缓存 (按入参哈希)。可用 robust.cache_enabled 关闭。"""
    store: dict = {}

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if not robust_conf.get("cache_enabled", True):
            return fn(*args, **kwargs)
        k = _key(args, kwargs)
        if k in store:
            logger.debug(f"[cache] 命中 {fn.__name__}")
            return store[k]
        result = fn(*args, **kwargs)
        store[k] = result
        return result

    wrapper._cache = store           # 便于测试查看
    return wrapper


def retry(times: int = None, delay: float = None):
    """失败重试 + 指数退避。"""
    times = times or robust_conf.get("retry_times", 3)
    delay = delay or robust_conf.get("retry_delay", 1.0)

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last = None
            for i in range(times):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    last = e
                    logger.warning(f"[retry] {fn.__name__} 第{i + 1}/{times}次失败: {e}")
                    if i < times - 1:
                        time.sleep(delay * (2 ** i))
            raise last
        return wrapper
    return deco


def degrade(default):
    """失败兜底：异常时返回 default，不向上抛 (保证整图不崩)。"""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                logger.error(f"[degrade] {fn.__name__} 失败已降级: {e}")
                return default
        return wrapper
    return deco
