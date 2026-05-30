"""统一的工程绝对路径工具。"""
import os


def get_project_root() -> str:
    """返回工程根目录 (meeting-insight-agent/)。"""
    current_file = os.path.abspath(__file__)          # .../src/utils/paths.py
    utils_dir = os.path.dirname(current_file)         # .../src/utils
    src_dir = os.path.dirname(utils_dir)              # .../src
    return os.path.dirname(src_dir)                   # .../meeting-insight-agent


def get_abs_path(relative_path: str) -> str:
    """相对路径 -> 基于工程根目录的绝对路径。"""
    return os.path.join(get_project_root(), relative_path)


def ensure_dir(path: str) -> str:
    """确保 path 所在目录存在，返回原 path。"""
    directory = path if os.path.splitext(path)[1] == "" else os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    return path


if __name__ == "__main__":
    print(get_project_root())
