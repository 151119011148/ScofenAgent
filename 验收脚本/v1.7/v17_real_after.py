# -*- coding: utf-8 -*-
"""v1.7 第③/④步：真实库的前后对照（只读）。

判据两条：
  1) 上线前那 7 行 memory 的 sha1 **逐行不变**（V9 只在写新会话时生效，不回头改旧账）；
  2) 新增那行的 fmt=v2、ActionStep 带着 wait 这一格。
"""
import hashlib
import json
import sqlite3
import sys

DB = "/Users/gaoying/Desktop/study/ai学习/smolagents/.agent-history.sqlite3"
before = json.loads(open("/Users/gaoying/Desktop/study/ai学习/验收脚本/v1.7/run/v17_real_before.json").read())
c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
now = {}
for sid, p in c.execute("select session_id, payload from memory order by session_id"):
    raw = p.encode() if isinstance(p, str) else bytes(p)
    d = json.loads(raw)
    waits = [r.get("wait") for r in d["steps"] if r.get("_t") == "ActionStep"]
    now[str(sid)] = {"len": len(raw), "sha1": hashlib.sha1(raw).hexdigest(), "fmt": d["fmt"], "waits": waits}

print("sessions:", c.execute("select count(*) from sessions").fetchone()[0],
      "messages:", c.execute("select count(*) from messages").fetchone()[0],
      "memory:", len(now), "| before:", before["sessions"], before["messages"], before["memory"] and len(before["memory"]))
changed = [sid for sid in before["memory"] if sid in now and now[sid]["sha1"] != before["memory"][sid]["sha1"]]
gone = [sid for sid in before["memory"] if sid not in now]
added = [sid for sid in now if sid not in before["memory"]]
print("OLD ROWS CHANGED:", changed or "无（7 行逐字节没动）")
print("OLD ROWS GONE   :", gone or "无")
for sid in added:
    print("ADDED sid=%s fmt=%s waits=%s bytes=%d sha1=%s"
          % (sid, now[sid]["fmt"], now[sid]["waits"], now[sid]["len"], now[sid]["sha1"]))
print("titles:", c.execute("select id,title from sessions order by id desc limit 3").fetchall())
sys.exit(1 if (changed or gone) else 0)
