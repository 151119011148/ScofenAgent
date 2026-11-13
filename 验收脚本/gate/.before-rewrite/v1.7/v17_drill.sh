#!/bin/bash
# v1.7 ⑤ 双向回滚演练（重跑，因为第 7 步修了一行过时注释，归档也跟着刷新）
set -u
ROOT=/Users/gaoying/Desktop/study/ai学习
cd "$ROOT/smolagents" || exit 1
PY=./.venv/bin/python

echo "=== 方向 1：退回 v1.6 ==="
cp "$ROOT/.rollback/v1.6/my_ui.py" "$ROOT/.rollback/v1.6/my_coding_agent.py" "$ROOT/smolagents/"
cmp "$ROOT/.rollback/v1.6/my_ui.py" "$ROOT/smolagents/my_ui.py" && echo "PASS cmp 归档 == 现场（v1.6）"
wc -l my_ui.py
$PY -c "
import pathlib,re
t=pathlib.Path('my_ui.py').read_text(encoding='utf-8')
print('PASS MEM_FMT' if 'MEM_FMT = \"v1\"' in t else 'FAIL MEM_FMT')
print('PASS 无 _session_steps' if '_session_steps' not in t else 'FAIL 残留 _session_steps')
print('PASS 无 MEM_FMT_READ' if 'MEM_FMT_READ' not in t else 'FAIL 残留 MEM_FMT_READ')
print('PASS 无 wait 编码' if '\"wait\"' not in t else 'FAIL 残留 wait 编码')
"
$PY /tmp/v16_test.py > /tmp/v17_drill_backward.out 2>&1
echo "v1.6 离线套件：PASS $(grep -c '^PASS' /tmp/v17_drill_backward.out) / FAIL $(grep -c '^FAIL' /tmp/v17_drill_backward.out) / exit=$?"
tail -1 /tmp/v17_drill_backward.out

echo "=== 方向 2：回到 v1.7 ==="
cp "$ROOT/.rollback/v1.7/my_ui.py" "$ROOT/.rollback/v1.7/my_coding_agent.py" "$ROOT/smolagents/"
cmp "$ROOT/.rollback/v1.7/my_ui.py" "$ROOT/smolagents/my_ui.py" && echo "PASS cmp 归档 == 现场（v1.7）"
wc -l my_ui.py
$PY -c "
import pathlib
t=pathlib.Path('my_ui.py').read_text(encoding='utf-8')
for k,tag in [('MEM_FMT = \"v2\"','fmt v2'),('MEM_FMT_READ','兼容读'),('_session_steps','只读出口'),
              ('row[\"wait\"]','编码写 wait'),('step._opsui_wait = float','解码挂回'),
              ('encode_memory 单独认它','第 7 步那句注释修正')]:
    print(('PASS ' if k in t else 'FAIL ')+tag)
print('PASS _bind_memory 没被接到点击上' if '_bind_memory(int(sid)' not in t else 'FAIL _bind_memory')
"
$PY /tmp/v17_test.py > /tmp/v17_drill_forward.out 2>&1
echo "v1.7 离线套件：PASS $(grep -c '^PASS' /tmp/v17_drill_forward.out) / FAIL $(grep -c '^FAIL' /tmp/v17_drill_forward.out)"
tail -1 /tmp/v17_drill_forward.out
cmp "$ROOT/.rollback/v1.7/my_ui.py" "$ROOT/smolagents/my_ui.py" && echo "PASS 收尾：现场 == .rollback/v1.7"
