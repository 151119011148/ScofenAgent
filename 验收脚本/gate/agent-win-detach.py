import os, subprocess, sys

delay = sys.argv[2] if len(sys.argv) > 2 else "2"
null = open(os.devnull, "r")
log = open("/Users/gaoying/Desktop/study/ai学习/验收脚本/gate/run/agent-win-close.log", "w")
if os.fork() == 0:
    os.setsid()
    subprocess.Popen(
        ["/bin/bash", "-c",
         "sleep %s; /usr/bin/osascript /Users/gaoying/Desktop/study/ai学习/验收脚本/gate/run/agent-win-close.sh.scpt \"$1\"" % delay,
         "_", sys.argv[1]],
        stdin=null, stdout=log, stderr=log, close_fds=True)
    os._exit(0)
