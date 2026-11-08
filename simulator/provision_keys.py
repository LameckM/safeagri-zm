"""Issue credentials for all configured sensor nodes and save them locally.

Run this on a trusted computer. Keys are shown once and stored in node_keys.json.
Running it again rotates the keys and immediately invalidates the old keys.
"""
import json
import os
from pathlib import Path
import httpx

API_BASE = os.getenv("SAFEAGRI_API_URL", "http://localhost:8000").rstrip("/")
KEYS_PATH = Path(os.getenv("SAFEAGRI_NODE_KEYS_FILE", Path(__file__).parent / "node_keys.json"))


def main():
    with httpx.Client(base_url=API_BASE, timeout=10) as client:
        client.get("/health").raise_for_status()
        fields = client.get("/fields")
        fields.raise_for_status()
        keys = {}
        for field in fields.json():
            response = client.post(f"/fields/{field['id']}/node-key")
            if response.status_code != 200:
                raise SystemExit(f"Could not issue a key for {field['node_id']}: {response.status_code} {response.text}")
            keys[response.json()["node_id"]] = response.json()["node_key"]
    KEYS_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(KEYS_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(keys, handle, indent=2)
    os.chmod(KEYS_PATH, 0o600)
    print(f"Issued {len(keys)} sensor keys. Saved locally to {KEYS_PATH}")


if __name__ == "__main__":
    main()
