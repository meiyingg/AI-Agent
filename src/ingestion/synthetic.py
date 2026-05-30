"""合成会议纪要生成器 (仅用于演示功能一)。

造一批"看起来像真的"的内部会议纪要文件，灌进 data/samples，
供会议纪要 RAG 助手做演示。内容是随机拼的，仅供测试。
"""
import os
import random
from datetime import date, timedelta

NAMES = ["张伟", "李娜", "王芳", "陈强", "刘洋", "赵敏", "孙磊", "周婷", "吴昊", "郑爽"]
TOPIC_POOL = [
    ("马来西亚招商引资进展", "推进吉隆坡产业园签约"),
    ("浙江-马来跨境物流方案", "采用海运加保税仓模式"),
    ("AI 自动化办公系统上线", "本月底完成内测并试运行"),
    ("季度预算复盘", "压缩差旅预算 15%"),
    ("人才招聘计划", "新增 3 名数据工程师"),
    ("合作伙伴拓展", "与两家本地企业签署意向"),
]
TASK_POOL = ["完成产业园选址报告", "对接海关保税仓", "搭建数据采集管道",
             "输出季度财务分析", "发布招聘 JD", "起草合作备忘录"]
RISK_POOL = ["汇率波动影响成本", "本地审批周期偏长", "数据源稳定性不足", "关键人才储备不足"]


def _rand_date(span: int = 120) -> str:
    return (date(2025, 1, 1) + timedelta(days=random.randint(0, span))).isoformat()


def random_minute() -> str:
    title = random.choice(["周例会", "跨境投资项目推进会", "经营分析会", "AI 方案评审会"])
    attendees = "、".join(random.sample(NAMES, k=random.randint(3, 5)))
    t1, t2 = random.sample(TOPIC_POOL, k=2)
    owners = random.sample(NAMES, k=2)
    return f"""会议标题：马来西亚-浙江国际投资协会{title}
会议日期：{_rand_date()}
参会人员：{attendees}

一、会议议题：
1. {t1[0]}
2. {t2[0]}

二、讨论与决议：
- 关于「{t1[0]}」，会议决定：{t1[1]}。
- 关于「{t2[0]}」，会议决定：{t2[1]}。

三、行动项：
1. {random.choice(TASK_POOL)}，负责人：{owners[0]}，截止日期：{_rand_date(150)}。
2. {random.choice(TASK_POOL)}，负责人：{owners[1]}，截止日期：{_rand_date(150)}。

四、风险提示：{"；".join(random.sample(RISK_POOL, k=2))}。

五、预算：本次涉及预算 {random.choice(['20万', '50万', '120万', '300万'])}元。

六、下次会议时间：{_rand_date(160)}。
"""


def generate_files(n: int, out_dir: str) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for i in range(n):
        fp = os.path.join(out_dir, f"meeting_{i:06d}.txt")
        with open(fp, "w", encoding="utf-8") as f:
            f.write(random_minute())
        paths.append(fp)
    return paths
