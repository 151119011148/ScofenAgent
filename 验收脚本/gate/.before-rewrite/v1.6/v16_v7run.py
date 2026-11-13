import sys

sys.path.insert(0, "/tmp")
from v16_cfg import NEWBTN, SESS, cfg

# V7 的四段链，改前改后跑同一份脚本，得到 before / after 对照。
# 零模型调用：只看侧栏选中态和 chatbot 内容，不提问。
steps = [
    {"name": "0-after-load", "read": 1},
    {"name": "1-click-jia", "el": SESS("V7基线-甲"), "wait": 2500, "read": 1},
    {"name": "2-click-new", "el": NEWBTN, "wait": 2500, "read": 1},
    {"name": "3-click-jia-again", "el": SESS("V7基线-甲"), "wait": 2800, "read": 1},
    {"name": "4-click-yi-control", "el": SESS("V7基线-乙"), "wait": 2800, "read": 1},
]
out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/v16_base.json"
with open(out, "w") as f:
    f.write(cfg("http://127.0.0.1:7861", steps, boot=9000))
print("wrote", out)
