import importlib, inspect

def chk(mod, names=()):
    try:
        m = importlib.import_module(mod)
        got = [n for n in names if hasattr(m, n)]
        print(f"[OK] {mod} -> {got}")
    except Exception as e:
        print(f"[NO] {mod}: {e}")

chk("langgraph.checkpoint.memory", ["MemorySaver", "InMemorySaver"])
chk("langgraph.checkpoint.sqlite", ["SqliteSaver"])
chk("langgraph.checkpoint.sqlite.aio", ["AsyncSqliteSaver"])

import langchain, langgraph
print("langchain", getattr(langchain, "__version__", "?"))
print("langgraph", getattr(langgraph, "__version__", "?"))

try:
    from langchain.agents import create_agent
    print("create_agent params:", list(inspect.signature(create_agent).parameters))
except Exception as e:
    print("create_agent NO:", e)
