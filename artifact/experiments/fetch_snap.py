"""Fetch the four original SNAP archives and record checksums."""
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import urllib.request

names = [
    "CollegeMsg.txt.gz",
    "email-Eu-core-temporal.txt.gz",
    "soc-sign-bitcoinotc.csv.gz",
    "soc-sign-bitcoinalpha.csv.gz",
]


def fetch(name):
    path = Path("data", name)
    url = "https://snap.stanford.edu/data/" + name
    if not path.exists():
        req = urllib.request.Request(url, headers={"User-Agent": "research-replication/1.0"})
        with urllib.request.urlopen(req, timeout=45) as source:
            content = source.read()
        gzip.decompress(content)
        path.write_bytes(content)
    raw = path.read_bytes()
    return {"name": name, "url": url, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "records": len(gzip.decompress(raw).splitlines())}


if __name__ == "__main__":
    Path("data").mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        manifest = list(pool.map(fetch, names))
    text = json.dumps(manifest, indent=2)
    Path("data/manifest.json").write_text(text + "\n", encoding="utf-8")
    print(text)
