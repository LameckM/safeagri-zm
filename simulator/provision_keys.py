"""Issue a key for every field and save them for the simulator.

Usage:
  SAFEAGRI_EMAIL=you@example.com python provision_keys.py

The password is read from SAFEAGRI_PASSWORD or prompted for. Running this again
rotates every key: the old ones stop working immediately. Keys are shown by the
API only once, so they are written to node_keys.json (readable by you only).
Put the same key into each real device's firmware as the X-Node-Key header.
"""
import getpass
import json
import os
import sys
from pathlib import Path

import httpx

API_BASE = os.getenv("SAFEAGRI_API_URL", "http://localhost:8000").rstrip("/")
KEYS_PATH = Path(os.getenv("SAFEAGRI_NODE_KEYS_FILE", Path(__file__).parent / "node_keys.json"))


def main():
    email = os.getenv("SAFEAGRI_EMAIL") or input("Farmer email: ").strip()
    password = os.getenv("SAFEAGRI_PASSWORD") or getpass.getpass("Password: ")
    with httpx.Client(base_url=API_BASE, timeout=10) as client:
        login = client.post("/auth/login", json={"email": email, "password": password})
        if login.status_code != 200:
            sys.exit(f"Login failed: {login.status_code} {login.text}")
        client.headers["Authorization"] = "Bearer " + login.json()["access_token"]
        keys = {}
        for field in client.get("/fields").json():
            issued = client.post(f"/fields/{field['id']}/node-key")
            if issued.status_code != 200:
                sys.exit(f"Could not issue a key for {field['node_id']}: {issued.status_code} {issued.text}")
            keys[issued.json()["node_id"]] = issued.json()["node_key"]
    fd = os.open(KEYS_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(keys, handle, indent=2)
    os.chmod(KEYS_PATH, 0o600)
    print(f"Issued {len(keys)} node keys ({', '.join(keys)}). Saved to {KEYS_PATH}")


if __name__ == "__main__":
    main()
