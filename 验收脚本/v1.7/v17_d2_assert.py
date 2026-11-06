"""D2 定性的离线断言：故意闭环写进注释，行为一字没变。

跑法（不需要模型，零网络、零写盘）：
    cd ~/Desktop/study/ai学习/smolagents
    ./.venv/bin/python ../验收脚本/v1.7/v17_d2_assert.py

三组断言：
  1) AST 等价——当前 my_coding_agent.py 与 .rollback/v1.7 那份归档去掉注释后必须完全同形，
     这就是「不改行为」的机器证明（docstring 也进 AST，所以工具描述若被改过一样会红）。
  2) 注释在场——拒绝名单那一段里必须有「故意的」和那句闭环理由。
  3) 行为边界——staging 目录读写两侧都进不去，唯一入口是 write_file 内部那次拼接。
"""

import ast
import pathlib
import sys

AIROOT = pathlib.Path(__file__).resolve().parents[1].parent   # ai学习/
sys.path.insert(0, str(AIROOT / "smolagents"))
import my_coding_agent as CA  # noqa: E402

SRC = AIROOT / "smolagents" / "my_coding_agent.py"
ARCHIVE = AIROOT / ".rollback" / "v1.7" / "my_coding_agent.py"

fails = []


def ck(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("" if cond else f"  <- {detail}"))
    if not cond:
        fails.append(name)


text = SRC.read_text(encoding="utf-8")
ck("0a 归档在位（没有归档这条等价就没法证）", ARCHIVE.is_file(), str(ARCHIVE))
old = ARCHIVE.read_text(encoding="utf-8") if ARCHIVE.is_file() else ""
ck("1a 去掉注释后 AST 与 v1.7 归档完全同形（＝行为零改动）",
   ast.dump(ast.parse(text)) == ast.dump(ast.parse(old)),
   "两个 AST 不一致，说明动到了代码或工具描述")
ck("1b 模块 docstring 一字未改（工具 docstring 由 1a 的整树比对兜住）",
   ast.parse(text).body[0].value.value == ast.parse(old).body[0].value.value)
ck("1c DENY_NAMES 集合本身没变（只加了它上面的注释）",
   CA.DENY_NAMES == {".env", ".git", ".venv", "node_modules", "__pycache__", ".agent-staging"},
   CA.DENY_NAMES)
ck("1d SKIP_DIRS 集合本身没变",
   CA.SKIP_DIRS == {".git", ".venv", "node_modules", "__pycache__", ".agent-staging", ".pytest_cache"},
   CA.SKIP_DIRS)

deny_block = text[text.index("# 目录名里出现这些就拒绝"):text.index("MAX_LINES")]
ck("2a 理由写在拒绝名单的正上方（不是写在别处）",
   deny_block.index(".agent-staging 在这个名单里是**故意的**") < deny_block.index("DENY_NAMES"),
   "注释与名单被分开了")
ck("2b 写明「唯一出口是你自己在终端执行的 cp」", "唯一出口是你自己在终端执行的 cp" in deny_block)
ck("2c 写明这是闭环、并且不许再打开", "自我确认的闭环" in deny_block and "放开读等于" in deny_block)
ck("2d 注释里带了定性日期，便于日后判断这条是新账还是老账", "2026-10-30" in deny_block)

for name, rel in [("3a 读 staging 里的副本被拒", ".agent-staging/xxx.py"),
                  ("3b 读 staging 目录本身被拒", ".agent-staging"),
                  ("3c 连『往 staging 写』也一并被拒（入口只有内部那次拼接）", ".agent-staging/new.py"),
                  ("3d 越界路径仍然先被 ROOT 收敛挡掉", "../outside/x.py")]:
    try:
        CA.guarded(rel, must_exist=(not rel.endswith(".py")))
        ck(name, False, "居然放行了")
    except (PermissionError, FileNotFoundError) as e:
        ck(name + f"（{type(e).__name__}）", isinstance(e, PermissionError), f"{type(e).__name__}: {e}")

real = pathlib.Path(CA.ROOT) / "smolagents" / "my_coding_agent.py"
ck("3e 名单外的正常路径照样读得通（边界不是把门全关）", CA.guarded(str(real)).is_file())
staged = CA.STAGING / "smolagents" / "my_coding_agent.py"
try:
    CA.guarded(str(staged), must_exist=False)
    ck("3f write_file 的落点 agent 自己 guarded 不进来（闭环确实焊死）", False, "居然放行了")
except PermissionError:
    ck("3f write_file 的落点 agent 自己 guarded 不进来（闭环确实焊死）", True)

print("\nFAILS: " + ("无" if not fails else ", ".join(fails)))
sys.exit(1 if fails else 0)
