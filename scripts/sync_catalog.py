"""Read public catalog, verify bytes, and keep a GitHub copy. Never execute models."""
import hashlib
import json
from pathlib import Path
import re
import urllib.request

ORIGIN = "https://uniware-laudos.luckybeech43.chatgpt.site"
LIMIT = 512 * 1024


def fetch(path, limit):
    req = urllib.request.Request(ORIGIN + path, headers={"User-Agent": "Uniware-Catalog-Mirror/1"})
    with urllib.request.urlopen(req, timeout=30) as response:
        if not response.url.startswith(ORIGIN + "/"):
            raise ValueError("Unexpected redirect")
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Response too large")
    return data


def main():
    catalog = json.loads(fetch("/api/catalog", 2 * 1024 * 1024))
    items = catalog.get("items", [])
    if not isinstance(items, list) or len(items) > 1000:
        raise ValueError("Invalid catalog")
    for item in items:
        key, filename = item["id"], item["filename"]
        if not re.fullmatch(r"[a-f0-9]{64}", key) or not filename or re.search(r'[\\/:*?"<>|\x00-\x1f]', filename) or filename.startswith('.') or filename.endswith('.'):
            raise ValueError("Invalid model identifier")
        folder = Path("modelos") / key
        target = folder / filename
        if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != item["sha256"]:
            data = fetch("/api/files/" + key, LIMIT)
            if hashlib.sha256(data).hexdigest() != item["sha256"] or len(data) != item["size"]:
                raise ValueError("Model integrity mismatch")
            folder.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        # Metadata lives in catalog.json; never overwrite an uploaded metadata.json.
    Path("catalog.json").write_text(json.dumps({"schemaVersion": 1, "items": items}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Catalog mirrored: {len(items)} model(s).")


if __name__ == "__main__":
    main()
