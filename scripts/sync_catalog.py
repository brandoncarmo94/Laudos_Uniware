"""Read public catalog, verify bytes, and keep a GitHub copy. Never execute models."""
import hashlib
import json
from pathlib import Path
import re
import urllib.request
import shutil
import time

ORIGIN = "https://uniware-laudos.luckybeech43.chatgpt.site"
LIMIT = 512 * 1024


def archive(source, key):
    root = Path.cwd().resolve()
    target = root / "modelos" / "_historico" / key / str(time.time_ns()) / source.name
    if source.is_symlink() or not source.resolve().is_relative_to(root) or not target.resolve().is_relative_to(root):
        raise ValueError("Unsafe archive path")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))


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
    active = {item["id"] for item in items}
    if any(not re.fullmatch(r"[a-f0-9]{64}", key) for key in active):
        raise ValueError("Invalid catalog identifier")
    if Path("modelos").exists():
        for folder in Path("modelos").iterdir():
            if re.fullmatch(r"[a-f0-9]{64}", folder.name) and folder.is_dir() and folder.name not in active:
                archive(folder, folder.name)
    for item in items:
        key, filename = item["id"], item["filename"]
        if not re.fullmatch(r"[a-f0-9]{64}", key) or not filename or re.search(r'[\\/:*?"<>|\x00-\x1f]', filename) or filename.startswith('.') or filename.endswith('.'):
            raise ValueError("Invalid model identifier")
        folder = Path("modelos") / key
        target = folder / filename
        if folder.exists():
            for previous in folder.iterdir():
                if previous.is_file() and previous.name != filename:
                    archive(previous, key)
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
