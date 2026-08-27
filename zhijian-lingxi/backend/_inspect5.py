# 临时排查：最新一次执行的详细步骤
import json
import sqlite3
import config

conn = sqlite3.connect(str(config.DB_PATH))
conn.row_factory = sqlite3.Row

tasks = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 1").fetchall()
if not tasks:
    print("无任务"); raise SystemExit
t = tasks[0]
execs = conn.execute(
    "SELECT * FROM executions WHERE task_id=? ORDER BY start_time DESC", (t["id"],)
).fetchall()
print(f"task {t['id'][:8]} {t['name']} | 执行次数: {len(execs)}")
for e in execs[:3]:
    print(f"  exec {e['id'][:8]} status={e['status']} start={e['start_time']}")
if not execs:
    raise SystemExit
e = execs[0]
print(f"\n=== 最近执行 {e['id'][:8]} ({e['start_time']}) ===")
for l in conn.execute(
    "SELECT step_id, action_type, target_element, status, page_url, healing_actions, error_info "
    "FROM step_logs WHERE execution_id=? ORDER BY step_id", (e["id"],)
).fetchall():
    print(f"step{l['step_id']}: {l['action_type']} status={l['status']}")
    print(f"   target={l['target_element']}")
    print(f"   page_url={l['page_url']}")
    if l["healing_actions"]:
        print(f"   heal={str(l['healing_actions'])[:200]}")
    if l["error_info"]:
        print(f"   err={str(l['error_info'])[:200]}")
