"""Code Interpreter:让 Agent 自己写 Python 并真的执行(像 ChatGPT 高级数据分析 / Gemini)。

通用而非定制:任意数学/统计/数据处理/财务建模,都交给模型写代码跑,不再写死领域函数。

安全(面试可讲的点):
- 在**独立子进程**里执行 —— 崩溃/死循环不拖垮主服务;
- **超时**自动杀进程(默认 20s);
- 子进程环境**剔除一切疑似密钥的变量**,避免被执行代码读到 API key / DB 连接串;
- 工作目录限制在**临时目录**,跑完即删。
真正上生产再换 Pyodide/Deno (langchain-sandbox) 或 E2B/Riza 这类强隔离沙箱即可。
"""
import os
import sys
import subprocess
import tempfile
from langchain_core.tools import tool

_TIMEOUT = int(os.getenv("CODE_INTERPRETER_TIMEOUT", "20"))
_SECRET_HINTS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "DATABASE_URL",
                 "DSN", "DASHSCOPE", "TAVILY", "LANGSMITH", "LANGCHAIN", "R2_", "AWS_", "OPENAI")


def _safe_env() -> dict:
    """复制环境但剔除任何疑似密钥/凭证的变量,避免被执行代码读到。"""
    base = {k: v for k, v in os.environ.items()
            if not any(h in k.upper() for h in _SECRET_HINTS)}
    base.setdefault("PYTHONIOENCODING", "utf-8")
    return base


@tool(description="Execute Python code and return whatever it prints. Use this for any real computation: math, "
                  "statistics, financial modelling, data wrangling, comparisons, simulations. Write a COMPLETE "
                  "self-contained snippet and print() the results you want to see. numpy and pandas are available. "
                  "Each call runs in a fresh process (no variables persist between calls). Arg: code (Python source).")
def run_python(code: str) -> str:
    if os.getenv("CODE_INTERPRETER_DISABLED") == "1":
        return "[disabled] The code interpreter is turned off in this environment."
    if not code or not code.strip():
        return "No code provided."
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "snippet.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        try:
            proc = subprocess.run(
                [sys.executable, path],
                cwd=tmp,                       # 限制工作目录在临时目录
                env=_safe_env(),               # 脱敏环境
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                timeout=_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return f"[timeout] Code did not finish within {_TIMEOUT}s and was killed. Simplify or avoid long loops."
        except Exception as e:                 # 兜底:子进程起不来也别崩主流程
            return f"[error] Could not run code: {e}"

    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        tail = "\n".join(err.splitlines()[-15:])          # 只回错误尾部,省上下文
        return f"[error] exit {proc.returncode}\n{tail}" + (f"\n[stdout]\n{out}" if out else "")
    if not out:
        return "[ok] Code ran with no output. Remember to print() the result you want to see."
    return out[:4000]                                     # 截断,避免塞爆上下文
