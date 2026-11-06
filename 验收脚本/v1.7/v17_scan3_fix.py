# -*- coding: utf-8 -*-
import io, sys
W = u"--write" in sys.argv

HTML = [
    # (line_no, old, new, note)
    (179, u"my_ui.py:782-805 状态条", u"my_ui.py:782-803 状态条", u"status_html"),
    (179, u":691-748 <code>_step_card</code>", u":691-746 <code>_step_card</code>", u"step_card"),
    (179, u":640-689 <code>_approval_card</code>", u":640-689 <code>_approval_card</code> ＋它的两个渲染小工具 <code>_fence</code>/<code>_args_text</code>", u"approval_card"),
    (179, u":806-960 线程驱动与流式渲染", u":806-958 线程驱动与流式渲染", u"worker_stream"),
    (179, u":961-1006 <code>_bind_memory</code>", u":961-986 <code>_bind_memory</code>", u"bind_179"),
    (179, u":63-234 记忆编解码", u":63-232 记忆编解码", u"memcodec"),
    (182, u"<code>_status_html()</code>（<code>:782-805</code>）", u"<code>_status_html()</code>（<code>:782-803</code>）", u"182_status"),
    (194, u"<code>_bind_memory(sid)</code>（<code>:961-1006</code>）", u"<code>_bind_memory(sid)</code>（<code>:961-986</code>）", u"194_bind"),
    (347, u"（<code>:831-960</code>）", u"（<code>:831-958</code>）", u"347_stream"),
    (456, u":782-805", u":782-803", u"456_status"),
    (480, u"_bind_memory(sid)</code>（<code>my_ui.py:961-1006</code>）", u"_bind_memory(sid)</code>（<code>my_ui.py:961-986</code>）", u"480_bind"),
    (486, u"编解码 <code>:132-230</code>", u"编解码 <code>:132-232</code>", u"486_codec"),
]
MD = [
    (727, u":1162-1179", u":1162-1180", u"727_onload"),
    (824, u":1162-1179", u":1162-1180", u"824_onload"),
]

for path, edits in [(u"agent功能手册.html", HTML), (u"README.md", MD)]:
    lines = io.open(path, encoding="utf-8").read().split(u"\n")
    done = []
    for ln, old, new, note in edits:
        cur = lines[ln - 1]
        assert cur.count(old) == 1, u"%s 行%d 锚点「%s」命中 %d 次" % (path, ln, old[:40], cur.count(old))
        lines[ln - 1] = cur.replace(old, new)
        done.append(note)
    print(u"%s: %d 处 %s" % (path, len(done), u",".join(done)))
    if W:
        io.open(path, "w", encoding="utf-8").write(u"\n".join(lines))
