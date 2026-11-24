"""Verify the shipped files listed in the archive manifest."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
entries = json.loads((root / "archive_sha256.json").read_text(encoding="utf-8"))
for name, expected in entries.items():
    if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
        raise SystemExit(f"File checksum mismatch: {name}")
print(f"Verified {len(entries)} archived files.")
