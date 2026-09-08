"""Durable public dialogue events, independent of screen capture and scoring."""
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class ReplayRecorder:
    def __init__(self, path: Path, case_id: str):
        self.path = path
        self.case_id = case_id
        self.started = time.perf_counter()
        self.sequence = 0
        # A restarted dialogue is a new attempt, not a continuation of the old
        # transcript. Keep its previous recording intact beside the new one.
        if path.exists():
            path.rename(path.with_name(f"replay.attempt-{uuid4().hex}.jsonl"))

    def append(self, state: dict, transcript: list, *, result: dict | None = None):
        event = {
            "version": 1, "sequence": self.sequence, "case_id": self.case_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "elapsed_ms": round((time.perf_counter() - self.started) * 1000),
            "phase": state["phase"], "messages": transcript,
            "hw_view": state.get("hw_view", []),
            "hw_view_active_ids": state.get("used_fact_ids", []),
            "turns": state.get("alan_turn", 0),
        }
        if result is not None:
            event.update(quality=result["quality"], judge=result["judgement"], stop_reason=result["stop_reason"])
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self.sequence += 1


def read_events(path: Path) -> list[dict]:
    events = []
    if not path.is_file():
        return events
    # A concurrent reader may see an unfinished last append. Never invent it.
    # Split bytes first: a concurrent append can end halfway through UTF-8.
    lines = path.read_bytes().splitlines(keepends=True)
    for line in lines:
        if not line.endswith(b"\n"):
            break
        event = json.loads(line)
        if not isinstance(event, dict) or event.get("version") != 1 or event.get("sequence") != len(events):
            raise ValueError("Replay event sequence is invalid")
        if (event.get("phase") not in {"alan", "worker", "judge", "complete"}
                or not isinstance(event.get("messages"), list)
                or not all(isinstance(m, dict) and isinstance(m.get("text"), str)
                           and isinstance(m.get("role"), str) for m in event["messages"])
                or not isinstance(event.get("elapsed_ms"), (int, float))
                or not math.isfinite(event["elapsed_ms"])
                or event["elapsed_ms"] < (events[-1]["elapsed_ms"] if events else 0)):
            raise ValueError("Replay event content is invalid")
        if event["phase"] == "complete" and (not isinstance(event.get("quality"), dict) or not isinstance(event.get("judge"), dict)):
            raise ValueError("Replay final result is invalid")
        events.append(event)
    return events


def recover_completion(events: list[dict], result: dict | None) -> list[dict]:
    """Read-only recovery of a missing final event, never invented dialogue timing.

    Original logs remain untouched. Exports carry the recovered flag and the
    saved result's completion time. Missing/damaged whole logs are not rebuilt.
    """
    if not events or events[-1]["phase"] == "complete" or not result or result.get("status") != "complete":
        return events
    if events[-1]["messages"] != result.get("transcript"):
        return events
    if not isinstance(result.get("quality"), dict) or not isinstance(result.get("judgement"), dict):
        return events
    final = {**events[-1], "sequence": len(events), "phase": "complete",
             "quality": result["quality"], "judge": result["judgement"],
             "stop_reason": result.get("stop_reason"), "recovered": True,
             "timestamp": result.get("completed_at") or events[-1]["timestamp"],
             "elapsed_ms": max(events[-1]["elapsed_ms"], result.get("elapsed_ms") or 0)}
    return [*events, final]
