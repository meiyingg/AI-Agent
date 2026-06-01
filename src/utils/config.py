"""加载 config/settings.yml，对外暴露配置。

可写设置(如记忆开关)走 data/store/settings_override.json 持久化，
避免改动带注释的 settings.yml；启动时把 override 叠加到对应 conf 上。
"""
import json
import os
import yaml
from src.utils.paths import get_abs_path

# 加载 .env (若安装了 python-dotenv)，便于读取 DASHSCOPE_API_KEY
try:
    from dotenv import load_dotenv
    load_dotenv(get_abs_path(".env"))
except ImportError:
    pass


def load_settings(config_path: str = None, encoding: str = "utf-8") -> dict:
    config_path = config_path or get_abs_path("config/settings.yml")
    with open(config_path, "r", encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


# 全局单例配置
settings: dict = load_settings()

# 常用快捷分组
model_conf: dict = settings["model"]
paths_conf: dict = settings["paths"]
rag_conf: dict = settings["rag"]
rerank_conf: dict = settings["rerank"]
search_conf: dict = settings["search"]
eval_conf: dict = settings["eval"]
agent_conf: dict = settings["agent"]
multiagent_conf: dict = settings["multiagent"]
robust_conf: dict = settings["robust"]
memory_conf: dict = settings.get("memory", {})
kb_conf: dict = settings.get("kb", {})


def abs_of(path_key: str) -> str:
    """传入 paths 下的 key，返回绝对路径。"""
    return get_abs_path(paths_conf[path_key])


# ---------- 可写设置 (override 持久化 + 运行时生效) ----------
_OVERRIDE_PATH = os.path.join(get_abs_path(paths_conf["store_dir"]), "settings_override.json")
# 允许前端编辑的设置段 -> 运行时 conf 对象
_WRITABLE = {"memory": memory_conf}


def _load_override() -> dict:
    try:
        with open(_OVERRIDE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# 启动时把已保存的 override 叠加到运行时 conf
for _sec, _patch in _load_override().items():
    if _sec in _WRITABLE and isinstance(_patch, dict):
        _WRITABLE[_sec].update(_patch)


def update_settings(section: str, patch: dict) -> dict:
    """更新可写设置：改运行时 conf(立即生效) + 写 override(持久化)。返回该段最新值。"""
    conf = _WRITABLE.get(section)
    if conf is None:
        raise ValueError(f"Non-writable settings section: {section}")
    conf.update(patch)
    ov = _load_override()
    ov.setdefault(section, {}).update(patch)
    os.makedirs(os.path.dirname(_OVERRIDE_PATH), exist_ok=True)
    with open(_OVERRIDE_PATH, "w", encoding="utf-8") as f:
        json.dump(ov, f, ensure_ascii=False, indent=2)
    return conf


if __name__ == "__main__":
    print("chat model:", model_conf["chat_model_name"])
    print("chroma dir:", abs_of("chroma_dir"))
