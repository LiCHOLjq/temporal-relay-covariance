"""Materialize the exact SNAP archives from their source URLs or a local download cache."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-dir", type=Path, help="Read the original .gz files from this directory")
    parser.add_argument("--check", action="store_true", help="Verify the input files already in place")
    args = parser.parse_args()
    for row in json.loads((ROOT / "snap_sources.json").read_text(encoding="utf-8")):
        target = ROOT / row["path"]
        if args.check or target.exists():
            content = target.read_bytes()
        elif args.from_dir:
            content = (args.from_dir / target.name).read_bytes()
        else:
            request = Request(row["url"], headers={"User-Agent": "graph-research-replication/1.0"})
            with urlopen(request, timeout=90) as response:
                content = response.read()
        digest = hashlib.sha256(content).hexdigest()
        if digest != row["sha256"] or len(content) != row["compressed_bytes"]:
            raise ValueError(f"Compressed file differs from the experimental input: {target.name}")
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        print(f"{digest}  {row['path']}")


if __name__ == "__main__":
    main()
