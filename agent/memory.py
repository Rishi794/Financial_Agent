from __future__ import annotations

import gzip
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MEMORY = ROOT / "memory"
INDEX_DIR = MEMORY / "index"
EPISODES = MEMORY / "episodes"
REPORTS = MEMORY / "reports"
CACHE = MEMORY / "cache"

for d in (EPISODES, REPORTS, CACHE, INDEX_DIR):
    d.mkdir(parents=True, exist_ok=True)


def _week(dt: datetime) -> str:
    return f"{dt.isocalendar().year}-W{dt.isocalendar().week:02d}"


def _clean_text(x: Any, limit: int) -> str:
    return str(x or "").replace("\x00", "")[:limit]


def load_index() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(INDEX_DIR.glob("*.ndjson")):
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict) and obj.get("id"):
                            rows.append(obj)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue
    return rows


def _fts_query(q: str) -> str:
    tokens = [t for t in re.findall(r"[A-Za-z0-9_]+", q.lower()) if len(t) > 1]
    return " OR ".join(f'"{t}"' for t in tokens[:24])


def search(query: str, limit: int = 12) -> list[dict[str, Any]]:
    rows = load_index()
    if not rows:
        return []
    db = sqlite3.connect(":memory:")
    db.execute("CREATE VIRTUAL TABLE mem USING fts5(id UNINDEXED, title, summary, facts, lessons, tags, open_loops, sources)")
    for r in rows:
        db.execute(
            "INSERT INTO mem VALUES (?,?,?,?,?,?,?,?)",
            (
                r["id"], r.get("title", ""), r.get("summary", ""),
                " ".join(r.get("facts", [])), " ".join(r.get("lessons", [])),
                " ".join(r.get("tags", [])), " ".join(r.get("open_loops", [])),
                " ".join(s.get("title", "") + " " + s.get("url", "") for s in r.get("sources", [])),
            ),
        )
    db.commit()
    tokens = _fts_query(query)
    if tokens:
        hits = db.execute("SELECT id, bm25(mem) FROM mem WHERE mem MATCH ? ORDER BY bm25(mem) LIMIT ?", (tokens, max(limit * 4, 20))).fetchall()
    else:
        hits = [(r["id"], 0.0) for r in rows[-max(limit, 10):]]
    by_id = {r["id"]: r for r in rows}
    now = datetime.now(timezone.utc)
    out: list[dict[str, Any]] = []
    for rid, bm in hits:
        r = dict(by_id.get(rid, {}))
        if not r:
            continue
        try:
            ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
            age_days = max(0.0, (now - ts).total_seconds() / 86400)
        except Exception:
            age_days = 3650.0
        recency = 1 / (1 + age_days / 14)
        importance = min(10, max(0, float(r.get("importance", 0)))) / 10
        lexical = -float(bm)
        r["retrieval_score"] = round(lexical + 0.9 * recency + 0.7 * importance, 4)
        out.append(r)
    out.sort(key=lambda x: x["retrieval_score"], reverse=True)
    db.close()
    return out[:limit]


def recent(limit: int = 5) -> list[dict[str, Any]]:
    rows = load_index()
    return rows[-limit:]


def recent_episodes(days: int = 7) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    out: list[dict[str, Any]] = []
    for path in sorted(EPISODES.glob("*.ndjson.gz")):
        try:
            with gzip.open(path, "rt", encoding="utf-8") as f:
                for line in f:
                    try:
                        r = json.loads(line)
                        ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
                        if (now - ts).total_seconds() <= days * 86400:
                            out.append(r)
                    except Exception:
                        continue
        except OSError:
            continue
    out.sort(key=lambda x: x.get("timestamp", ""))
    return out


def _append_gzip(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "at", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")


def save_episode(task: str, final_obj: dict[str, Any], trace: list[dict[str, Any]]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    week = _week(now)
    episode_id = str(uuid.uuid4())
    sources = []
    seen = set()
    for s in final_obj.get("sources", []) if isinstance(final_obj.get("sources"), list) else []:
        if not isinstance(s, dict):
            continue
        url = _clean_text(s.get("url"), 1000)
        if not url or url in seen:
            continue
        seen.add(url)
        sources.append({"url": url, "title": _clean_text(s.get("title"), 500), "published": _clean_text(s.get("published"), 80)})
        if len(sources) >= 20:
            break

    facts = [_clean_text(x, 1200) for x in final_obj.get("facts_to_store", [])][:20]
    lessons = [_clean_text(x, 1200) for x in final_obj.get("lessons_to_store", [])][:12]
    loops = [_clean_text(x, 1200) for x in final_obj.get("open_loops", [])][:12]
    tags = [_clean_text(x, 100) for x in final_obj.get("tags", [])][:20]
    result = _clean_text(final_obj.get("result"), 7000)
    title = _clean_text(result.split("\n", 1)[0] or "research run", 140)
    importance = min(10, max(0, int(final_obj.get("importance", 0))))

    episode = {
        "id": episode_id,
        "timestamp": now.isoformat().replace("+00:00", "Z"),
        "title": title,
        "task": _clean_text(task, 3000),
        "summary": result,
        "facts": facts,
        "lessons": lessons,
        "open_loops": loops,
        "sources": sources,
        "tags": tags,
        "importance": importance,
    }
    _append_gzip(EPISODES / f"{week}.ndjson.gz", episode)

    # Compact searchable memory. This is the retrieval corpus; full tool traces stay elsewhere.
    index_path = INDEX_DIR / f"{now.year}.ndjson"
    with index_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(episode, ensure_ascii=False, separators=(",", ":")) + "\n")

    trace_record = {
        "id": episode_id,
        "timestamp": episode["timestamp"],
        "task": episode["task"],
        "steps": trace,
        "result": result,
    }
    _append_gzip(REPORTS / f"{week}.ndjson.gz", trace_record)
    return episode


def cache_source(kind: str, key: str, payload: Any) -> None:
    now = datetime.now(timezone.utc)
    _append_gzip(CACHE / f"{_week(now)}.ndjson.gz", {"timestamp": now.isoformat(), "kind": kind, "key": key, "payload": payload})
