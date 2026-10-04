from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.llm import chat, extract_json
from agent.memory import recent, save_episode
from agent.tools import TOOLS

ROOT = Path(__file__).resolve().parents[1]


def cfg() -> dict[str, Any]:
    return json.loads((ROOT / "config" / "agent.json").read_text(encoding="utf-8"))


def clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n] + "\n...[trimmed]"


def valid_action(obj: dict[str, Any]) -> dict[str, Any]:
    out = {
        "type": obj.get("type"),
        "tool": obj.get("tool"),
        "arguments": obj.get("arguments") if isinstance(obj.get("arguments"), dict) else {},
        "working_note": str(obj.get("working_note", ""))[:1000],
        "result": str(obj.get("result", ""))[:7000],
        "facts_to_store": obj.get("facts_to_store") if isinstance(obj.get("facts_to_store"), list) else [],
        "lessons_to_store": obj.get("lessons_to_store") if isinstance(obj.get("lessons_to_store"), list) else [],
        "open_loops": obj.get("open_loops") if isinstance(obj.get("open_loops"), list) else [],
        "sources": obj.get("sources") if isinstance(obj.get("sources"), list) else [],
        "tags": obj.get("tags") if isinstance(obj.get("tags"), list) else [],
        "importance": obj.get("importance", 0),
    }
    return out


def memory_context() -> str:
    data = []
    for x in recent(6):
        data.append({
            "timestamp": x.get("timestamp"),
            "title": x.get("title"),
            "summary": clip(str(x.get("summary", "")), 900),
            "facts": x.get("facts", [])[:5],
            "open_loops": x.get("open_loops", [])[:5],
            "sources": x.get("sources", [])[:4],
            "importance": x.get("importance", 0),
        })
    return json.dumps(data, ensure_ascii=False)


def fit(messages: list[dict[str, str]], budget: int = 25000) -> list[dict[str, str]]:
    if not messages:
        return []
    first = messages[:2]
    rest = messages[2:]
    picked = first + rest[-9:]
    used = 0
    out = []
    for i, m in enumerate(picked):
        room = max(800, budget - used)
        text = m["content"][:room]
        out.append({"role": m["role"], "content": text})
        used += len(text)
        if used >= budget:
            break
    return out


def run() -> None:
    c = cfg()
    started = time.time()
    deadline = started + int(c["agent"]["runtime_minutes"]) * 60
    mission = (ROOT / "config" / "tasks.md").read_text(encoding="utf-8")
    system = (ROOT / "system_prompt.md").read_text(encoding="utf-8")
    repo = os.environ.get("GITHUB_REPOSITORY", "unknown")
    now = datetime.now(timezone.utc).isoformat()

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"UTC: {now}\nRepository: {repo}\n\nMISSION:\n{mission}\n\nRECENT MEMORY:\n{memory_context()}\n\nBegin by querying memory_search for the mission, then research only what is new or unresolved."},
    ]
    trace: list[dict[str, Any]] = []
    final: dict[str, Any] | None = None
    last_tool = None

    for step in range(1, int(c["agent"]["max_steps"]) + 1):
        if time.time() >= deadline:
            break
        raw = chat(fit(messages), int(c["agent"]["max_output_tokens"]), float(c["agent"]["temperature"]))
        try:
            obj = valid_action(extract_json(raw))
        except Exception as exc:
            trace.append({"step": step, "tool": None, "ok": False, "working_note": "JSON recovery requested", "response": raw[:1800]})
            messages.append({"role": "assistant", "content": raw[:3000]})
            messages.append({"role": "user", "content": f"Your response was not valid JSON ({type(exc).__name__}). Return exactly one JSON object following the contract. No markdown."})
            continue

        if obj["type"] == "final":
            final = obj
            trace.append({"step": step, "tool": None, "ok": True, "working_note": obj["working_note"], "response": obj["result"]})
            break

        tool = str(obj.get("tool") or "")
        if tool == last_tool and tool not in {"web_get", "memory_search"}:
            # Repeated identical tool calls are usually accidental loops.
            messages.append({"role": "user", "content": "Avoid repeating the same tool/query. Either change the query/source or synthesize the evidence you already have."})
        last_tool = tool
        fn = TOOLS.get(tool)
        args = obj["arguments"]
        if fn is None:
            result, ok = f"Unknown tool: {tool}", False
        else:
            try:
                result = fn(args)
                ok = True
            except Exception as exc:
                result, ok = f"TOOL ERROR {type(exc).__name__}: {exc}", False
        result = clip(str(result), int(c["agent"]["max_tool_chars"]))
        trace.append({"step": step, "tool": tool, "arguments": args, "ok": ok, "working_note": obj["working_note"], "response": result})
        messages.append({"role": "assistant", "content": json.dumps(obj, ensure_ascii=False)})
        messages.append({"role": "user", "content": f"TOOL RESULT ({tool}, success={ok}):\n{result}\n\nContinue the mission. Verify important claims, avoid duplicates, and finish with a durable result when enough evidence exists."})

    if final is None:
        final = {
            "type": "final", "tool": None, "arguments": {},
            "working_note": "Execution budget ended; persisted the partial trace so the next run can continue.",
            "result": "The run ended at its time/step budget. The persisted trace contains the research already performed.",
            "facts_to_store": [],
            "lessons_to_store": ["Continue from the latest persisted trace and open loops."],
            "open_loops": ["Resume the unfinished research task from the latest run."],
            "sources": [], "tags": ["partial-run"], "importance": 4,
        }

    episode = save_episode(mission, final, trace)
    print(json.dumps({"id": episode["id"], "steps": len(trace), "result": episode["summary"][:1200]}, ensure_ascii=False))


if __name__ == "__main__":
    run()
