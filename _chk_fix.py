"""验证防脑补 + 列文件工具。"""
import sys, io, os, tempfile
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from src.rag.kb_service import process_upload, delete_doc
from src.agent.react_agent import Assistant

td = tempfile.mkdtemp()
p = os.path.join(td, "我的小草稿.txt")
with open(p, "w", encoding="utf-8") as f:
    f.write("买花。")                       # 和你的草稿一样, 内容极少
doc = process_upload(p, "我的小草稿.txt")
print(">>> 已上传:", doc["name"], doc["chars"], "字")

a = Assistant()
q1 = "知识库里现在有哪些上传的文件？"
print("\nQ1:", q1)
print("A1:", a.execute(messages=[{"role": "user", "content": q1}])[:280])

q2 = "“我的小草稿.txt”这个文件里写了什么？"
print("\nQ2:", q2)
print("A2:", a.execute(messages=[{"role": "user", "content": q2}])[:280])

delete_doc(doc["id"])
print("\n>>> 已清理测试文件")
