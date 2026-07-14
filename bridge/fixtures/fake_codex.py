#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time


if sys.argv[1:] == ["--version"]:
    print("codex-cli 0.144.1")
    raise SystemExit(0)

prompt = sys.stdin.read()
record = os.environ.get("FAKE_CODEX_RECORD")
if record:
    with open(record, "w", encoding="utf-8") as handle:
        json.dump({"argv": sys.argv[1:], "stdin": prompt}, handle)

mode = os.environ.get("FAKE_CODEX_MODE", "ok")
print(json.dumps({"type": "thread.started", "thread_id": "fake-thread"}), flush=True)
print(json.dumps({"type": "turn.started"}), flush=True)

if mode == "child":
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(999)"])
    child_file = os.environ.get("FAKE_CODEX_CHILD_PID")
    if child_file:
        with open(child_file, "w", encoding="ascii") as handle:
            handle.write(str(child.pid))
    time.sleep(999)
elif mode == "auth":
    print("Not authenticated. Run codex login. token=secret", file=sys.stderr)
    raise SystemExit(1)
elif mode == "resume-fail" and "resume" in sys.argv:
    print("thread cannot be resumed", file=sys.stderr)
    raise SystemExit(1)
else:
    print(
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": f"received:{prompt}",
                },
            }
        ),
        flush=True,
    )
    print(
        json.dumps({"type": "turn.completed", "usage": {"output_tokens": 3}}),
        flush=True,
    )
