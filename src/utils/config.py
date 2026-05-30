"""加载 config/settings.yml，对外暴露只读配置。"""
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


def abs_of(path_key: str) -> str:
    """传入 paths 下的 key，返回绝对路径。"""
    return get_abs_path(paths_conf[path_key])


if __name__ == "__main__":
    print("chat model:", model_conf["chat_model_name"])
    print("chroma dir:", abs_of("chroma_dir"))
