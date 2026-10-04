from __future__ import annotations
import argparse, json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent.memory import load_index, search

p = argparse.ArgumentParser()
p.add_argument("query", nargs="*")
p.add_argument("--limit", type=int, default=10)
p.add_argument("--stats", action="store_true")
a = p.parse_args()

if a.stats:
    rows = load_index()
    print(json.dumps({"episodes": len(rows), "first": rows[0]["timestamp"] if rows else None, "last": rows[-1]["timestamp"] if rows else None}, indent=2))
if a.query:
    print(json.dumps(search(" ".join(a.query), a.limit), ensure_ascii=False, indent=2))
