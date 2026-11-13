# -*- coding: utf-8 -*-
"""v1.7 第③步：把实跑库里的东西摊开看（只读）。

用法：python v17_dump.py [db路径]
"""
import json
import sqlite3
import sys

db = sys.argv[1] if len(sys.argv) > 1 else "/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.7/run/v17-live-hist.sqlite3"
c = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
print("DB:", db)
print("sessions:", c.execute("select id, title from sessions order by id").fetchall())
print("msgs:", c.execute("select session_id, count(*) from messages group by session_id order by session_id").fetchall())
for sid, payload in c.execute("select session_id, payload from memory order by session_id"):
    d = json.loads(payload)
    waits = [r.get("wait") for r in d["steps"] if r.get("_t") == "ActionStep"]
    dur = [r.get("timing", {}).get("duration") for r in d["steps"] if r.get("_t") == "ActionStep"]
    # 口径写死：payload 是 TEXT，len() 数的是**字符**；UTF-8 字节数是另一个数。
    # （之前这里印的 label 是 bytes=，实际给的是字符数——迭代记录 §4 那两行因此混过单位。）
    raw = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
    print("mem sid=%s fmt=%s steps=%d wait=%s duration=%s chars=%d utf8=%dB"
          % (sid, d["fmt"], len(d["steps"]), waits, dur, len(raw.decode("utf-8")), len(raw)))
print("cards containing 审批:",
      c.execute("select session_id, count(*) from messages where content like '%审批%' group by session_id").fetchall())
