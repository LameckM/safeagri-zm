"""Set a demo node online or offline from the terminal.

Run from the repository root:
  python -m backend.node_control node-01 offline
  python -m backend.node_control node-01 online
"""
import argparse
from datetime import datetime, timezone
from backend.app.db import init_db, get_conn

NODES = ("node-01", "node-02", "node-03", "node-04")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("node", choices=NODES)
    parser.add_argument("state", choices=("online", "offline"))
    args = parser.parse_args()
    init_db()
    online = int(args.state == "online")
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    with get_conn() as conn:
        conn.execute("INSERT INTO node_status (node_id, online, updated_at) VALUES (?, ?, ?) "
                     "ON CONFLICT(node_id) DO UPDATE SET online = excluded.online, updated_at = excluded.updated_at",
                     (args.node, online, now))
    print(f"{args.node} set to {args.state}.")
    if online:
        print("The automatic simulator will resume readings on its next cycle.")

if __name__ == "__main__":
    main()
