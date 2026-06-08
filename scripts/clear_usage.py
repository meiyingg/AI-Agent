"""清空 usage_log 和 tool_log 表(旧价格数据)。运行: python -m scripts.clear_usage"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.db import ready
from sqlalchemy import text

eng = ready()
with eng.begin() as c:
    r1 = c.execute(text("DELETE FROM usage_log"))
    r2 = c.execute(text("DELETE FROM tool_log"))
    print(f"Deleted {r1.rowcount} rows from usage_log")
    print(f"Deleted {r2.rowcount} rows from tool_log")
    print("Done. 历史用量数据已清空，新的调用将使用正确的国内价格。")
