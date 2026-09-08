#!/usr/bin/env python3
"""Local live monitor for Alan dialogue runs."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from ctypes import wintypes
from io import BufferedIOBase
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4


HERE = Path(__file__).resolve().parent
REPO = HERE.parent
EXPERIMENT = REPO / "runtime"
RUNS = REPO / "runs"
MAX_RECORDING_BYTES = 4 * 1024 * 1024 * 1024
MAX_CLIPBOARD_BYTES = 4 * 1024 * 1024
RECORDING_EXTENSIONS = {
    "video/mp4": "mp4",
    "video/webm": "webm",
}
if str(EXPERIMENT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT))

from quality_scoring import QUALITY_SCORING_VERSION, build_quality_metrics
from replay_events import read_events, recover_completion
from runner_defaults import (
    JUDGE_MODEL,
    JUDGE_REASONING,
    MODEL,
    MODEL_TRANSPORT,
    REASONING,
    RUNNER_VERSION,
    WORKER_MODEL,
    WORKER_REASONING,
)


CURRENT_RUNNER_ROUTE = {
    "runner_version": RUNNER_VERSION,
    "quality_scoring_version": QUALITY_SCORING_VERSION,
    "model": MODEL,
    "reasoning_effort": REASONING,
    "model_transport": MODEL_TRANSPORT,
    "worker_model": WORKER_MODEL,
    "worker_reasoning_effort": WORKER_REASONING,
    "worker_transport": MODEL_TRANSPORT,
    "judge_model": JUDGE_MODEL,
    "judge_reasoning_effort": JUDGE_REASONING,
    "judge_transport": MODEL_TRANSPORT,
}


def current_local_alan() -> dict[str, str | None]:
    """Describe the local Alan prompt selected for the next runner launch."""
    source = REPO / "prompts/alan.txt"
    if not source.is_file():
        return {
            "alan_source_type": "local_override",
            "alan_source": str(source),
            "alan_version": "v0.2.0",
            "alan_version_date": None,
            "alan_version_source": "Local prompt missing",
            "alan_prompt_sha256": None,
        }
    modified = datetime.fromtimestamp(source.stat().st_mtime, tz=timezone.utc).isoformat()
    return {
        "alan_source_type": "local_override",
        "alan_source": str(source),
        "alan_version": "v0.2.0",
        "alan_version_date": modified,
        "alan_version_source": "Local prompt",
        "alan_prompt_sha256": hashlib.sha256(source.read_bytes()).hexdigest().upper(),
    }


def tagged_prompt_versions() -> dict[str, dict[str, str]]:
    """Map released prompt hashes to their local Git tag and tag date."""
    try:
        tags = subprocess.run(
            ["git", "tag", "--list", "v*"],
            cwd=REPO,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        return {}
    versions: dict[str, dict[str, str]] = {}
    for tag in tags:
        tag = tag.strip()
        if not tag:
            continue
        try:
            prompt = subprocess.run(
                ["git", "show", f"{tag}:alan_compiled.txt"],
                cwd=REPO,
                check=True,
                capture_output=True,
            ).stdout
            tag_date = subprocess.run(
                [
                    "git",
                    "for-each-ref",
                    "--format=%(creatordate:iso-strict)",
                    f"refs/tags/{tag}",
                ],
                cwd=REPO,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            continue
        versions[hashlib.sha256(prompt).hexdigest().upper()] = {
            "alan_version": tag,
            "alan_version_date": tag_date,
            "alan_version_source": "tagged release",
        }
    return versions


TAGGED_PROMPT_VERSIONS = {}


def alan_version_for(manifest: dict) -> dict[str, str | None]:
    prompt_hash = str(manifest.get("alan_prompt_sha256") or "").upper()
    if manifest.get("alan_source_type"):
        return {
            "alan_source_type": manifest.get("alan_source_type"),
            "alan_source": manifest.get("alan_source"),
            "alan_version": manifest.get("alan_version"),
            "alan_version_date": manifest.get("alan_version_date"),
            "alan_version_source": manifest.get("alan_version_source"),
            "alan_git_ref": manifest.get("alan_git_ref"),
            "alan_git_commit": manifest.get("alan_git_commit"),
            "alan_prompt_sha256": prompt_hash or None,
        }
    if prompt_hash in TAGGED_PROMPT_VERSIONS:
        return {
            **TAGGED_PROMPT_VERSIONS[prompt_hash],
            "alan_source_type": "hash_match_only",
            "alan_source": None,
            "alan_prompt_sha256": prompt_hash,
        }
    return {
        "alan_source_type": "historical_local_snapshot",
        "alan_source": None,
        "alan_version": "v0.2.0",
        "alan_version_date": manifest.get("started_at"),
        "alan_version_source": "Local run snapshot",
        "alan_prompt_sha256": prompt_hash or None,
    }


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return default


def read_json_from_bytes(value: bytes):
    try:
        return json.loads(value.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def read_text(path: Path) -> str | None:
    try:
        value = path.read_text(encoding="utf-8").strip()
        return value or None
    except (OSError, UnicodeDecodeError):
        return None


def case_bank(run_dir: Path | None = None) -> dict:
    payload_path = REPO / "work/cases.json"
    if run_dir is not None:
        manifest = read_json(run_dir / "run_manifest.json", {}) or {}
        snapshot = manifest.get("cases_snapshot")
        if snapshot:
            candidate = Path(str(snapshot))
            payload_path = candidate if candidate.is_absolute() else run_dir / candidate
    payload = read_json(payload_path, {}) or {}
    return {case["Case"]: case for case in payload.get("cases", []) if isinstance(case, dict) and case.get("Case")}


def pilot_case(case_id: str, run_dir: Path | None = None) -> dict:
    return case_bank(run_dir).get(case_id, {})


def worker_layout_views(run_dir: Path, manifest: dict) -> list[list[dict]]:
    """Measure all frozen patient fact states before live case changes begin.

    These views are used only for layout. They never select the displayed facts
    or enter a model request. References and assessment metadata stay excluded.
    """
    from runner import CaseFilter
    snapshot = manifest.get("cases_snapshot")
    if not snapshot:
        return []
    path = Path(str(snapshot))
    if not path.is_absolute():
        path = run_dir / path
    payload = read_json(path, {}) or {}
    selected = set(manifest.get("case_ids") or [])
    views = []
    for case in payload.get("cases", []):
        if selected and case.get("Case") not in selected:
            continue
        if case.get("domain") not in ("Eye", "ENT", "Skin"):
            continue
        bank = CaseFilter(case)
        views.append(safe_hw_view(bank.visible_facts()))
        if bank.stretch:
            bank.state = "updated"
            views.append(safe_hw_view(bank.visible_facts()))
        if (case.get("extra_test") or {}).get("facts_after_injection"):
            bank.apply_injected_state()
            views.append(safe_hw_view(bank.visible_facts()))
    return views


def iso_timestamp(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_ctime, tz=timezone.utc).isoformat()


def latest_file_update(paths) -> str | None:
    timestamps = []
    for path in paths:
        try:
            timestamps.append(path.stat().st_mtime)
        except OSError:
            continue
    return datetime.fromtimestamp(max(timestamps), timezone.utc).isoformat() if timestamps else None


def model_failure_reason(case_dir: Path, fallback):
    """Prefer the model's structured failure over incidental stderr warnings."""
    if not fallback:
        return fallback
    logs = sorted(case_dir.rglob("events_attempt_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in logs:
        for line in reversed(read_text(path).splitlines()):
            try:
                event = json.loads(line)
            except (ValueError, TypeError):
                continue
            if event.get("type") not in {"error", "turn.failed"}:
                continue
            message = event.get("message") or (event.get("error") or {}).get("message")
            if message:
                return str(message)[:1500]
    return fallback


def activity_for_case(case_dir: Path) -> tuple[str, str | None]:
    audit_dir = case_dir / "separate_audit"
    if audit_dir.exists() and not (audit_dir / "review.json").exists():
        return "Judge checking", iso_timestamp(audit_dir)
    pending: list[tuple[Path, str]] = []
    for turn_dir in case_dir.glob("turn_*"):
        if not (turn_dir / "last.txt").exists():
            pending.append((turn_dir, "Alan thinking"))
    for attempt_dir in [*case_dir.glob("worker_after_*/attempt_*"),
                        *case_dir.glob("worker_after_*/selection")]:
        if not (attempt_dir / "last.txt").exists():
            pending.append((attempt_dir, "HW replying"))
    judge_dir = case_dir / "judge"
    if judge_dir.exists() and not (judge_dir / "last.txt").exists():
        pending.append((judge_dir, "Judge checking"))
    if pending:
        path, label = max(pending, key=lambda item: item[0].stat().st_ctime)
        return label, iso_timestamp(path)
    return "Preparing next reply", iso_timestamp(case_dir)


def safe_run_dir(name: str | None) -> Path | None:
    if not RUNS.exists():
        return None
    if name:
        candidate = (RUNS / Path(name).name).resolve()
        if candidate.parent == RUNS.resolve() and candidate.is_dir():
            return candidate
        return None
    candidates = [item for item in RUNS.iterdir() if item.is_dir()]
    return max(candidates, key=lambda item: item.stat().st_mtime, default=None)


def write_json_atomic(path: Path, value: dict) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def html_clipboard_payload(fragment: str) -> bytes:
    prefix = "<html><body><!--StartFragment-->"
    suffix = "<!--EndFragment--></body></html>"
    document = f"{prefix}{fragment}{suffix}".encode("utf-8")
    template = (
        "Version:0.9\r\n"
        "StartHTML:{start_html:010d}\r\n"
        "EndHTML:{end_html:010d}\r\n"
        "StartFragment:{start_fragment:010d}\r\n"
        "EndFragment:{end_fragment:010d}\r\n"
    )
    placeholder = template.format(
        start_html=0,
        end_html=0,
        start_fragment=0,
        end_fragment=0,
    ).encode("ascii")
    start_html = len(placeholder)
    start_fragment = start_html + len(prefix.encode("utf-8"))
    end_fragment = start_fragment + len(fragment.encode("utf-8"))
    end_html = start_html + len(document)
    header = template.format(
        start_html=start_html,
        end_html=end_html,
        start_fragment=start_fragment,
        end_fragment=end_fragment,
    ).encode("ascii")
    return header + document + b"\0"


def write_windows_clipboard(plain_text: str, rich_html: str, rich_rtf: str) -> None:
    if sys.platform != "win32":
        raise OSError("Native Outlook copy is only available on Windows")

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle_type = wintypes.HANDLE

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterClipboardFormatW.restype = wintypes.UINT
    user32.SetClipboardData.argtypes = [wintypes.UINT, handle_type]
    user32.SetClipboardData.restype = handle_type
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = handle_type
    kernel32.GlobalLock.argtypes = [handle_type]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [handle_type]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalFree.argtypes = [handle_type]
    kernel32.GlobalFree.restype = handle_type

    html_format = user32.RegisterClipboardFormatW("HTML Format")
    rtf_format = user32.RegisterClipboardFormatW("Rich Text Format")
    if not html_format or not rtf_format:
        raise OSError("Outlook clipboard formats could not be registered")

    try:
        rtf_payload = rich_rtf.encode("ascii") + b"\0"
    except UnicodeEncodeError as exc:
        raise OSError("Outlook rich-text payload is not ASCII-safe") from exc

    formats = (
        (13, (plain_text + "\0").encode("utf-16-le")),  # CF_UNICODETEXT
        (html_format, html_clipboard_payload(rich_html)),
        (rtf_format, rtf_payload),
    )

    opened = False
    for _ in range(10):
        if user32.OpenClipboard(None):
            opened = True
            break
        time.sleep(0.02)
    if not opened:
        raise OSError("Windows clipboard is busy")

    try:
        if not user32.EmptyClipboard():
            raise OSError("Windows clipboard could not be cleared")
        for clipboard_format, payload in formats:
            handle = kernel32.GlobalAlloc(0x0002, len(payload))  # GMEM_MOVEABLE
            if not handle:
                raise OSError("Clipboard memory could not be allocated")
            pointer = kernel32.GlobalLock(handle)
            if not pointer:
                kernel32.GlobalFree(handle)
                raise OSError("Clipboard memory could not be locked")
            try:
                ctypes.memmove(pointer, payload, len(payload))
            finally:
                kernel32.GlobalUnlock(handle)
            if not user32.SetClipboardData(clipboard_format, handle):
                kernel32.GlobalFree(handle)
                raise OSError("Clipboard format could not be written")
    finally:
        user32.CloseClipboard()


def save_recording(
    run_name: str | None,
    content_type: str,
    content_length: int,
    source: BufferedIOBase,
) -> dict:
    """Stream one browser recording into its exact run directory."""
    run_dir = safe_run_dir(run_name)
    if not run_name or run_dir is None or run_dir.name != run_name:
        raise ValueError("Run not found")
    if not (run_dir / "run_manifest.json").is_file():
        raise ValueError("Run manifest not found")
    media_type = content_type.partition(";")[0].strip().lower()
    extension = RECORDING_EXTENSIONS.get(media_type)
    if extension is None:
        raise ValueError("Recording must be MP4 or WebM")
    if content_length <= 0:
        raise ValueError("Recording is empty")
    if content_length > MAX_RECORDING_BYTES:
        raise OverflowError("Recording exceeds the 4 GiB limit")

    existing = [run_dir / "recording.mp4", run_dir / "recording.webm"]
    if any(path.exists() for path in existing):
        raise FileExistsError("This run already has a recording")

    target = run_dir / f"recording.{extension}"
    partial = run_dir / f".recording.{uuid4().hex}.part"
    remaining = content_length
    try:
        with partial.open("xb") as handle:
            while remaining:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise EOFError("Recording upload ended early")
                handle.write(chunk)
                remaining -= len(chunk)
        partial.replace(target)
    except Exception:
        partial.unlink(missing_ok=True)
        raise

    seekable = extension != "mp4" or normalise_mp4_for_seeking(target)
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    saved_bytes = target.stat().st_size

    saved_at = datetime.now(timezone.utc).isoformat()
    metadata = {
        "filename": target.name,
        "relative_path": (Path("runs") / run_dir.name / target.name).as_posix(),
        "content_type": media_type,
        "bytes": saved_bytes,
        "sha256": digest.hexdigest().upper(),
        "seekable": seekable,
        "saved_at": saved_at,
    }
    write_json_atomic(run_dir / "recording.json", metadata)
    return metadata


def normalise_mp4_for_seeking(target: Path) -> bool:
    """Losslessly rebuild a browser MP4 with a conventional seek index."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return False
    indexed = target.with_name(f".{target.stem}.{uuid4().hex}.indexed.mp4")
    try:
        completed = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-v",
                "error",
                "-i",
                str(target),
                "-map",
                "0",
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                "-f",
                "mp4",
                str(indexed),
            ],
            capture_output=True,
            check=False,
            timeout=120,
        )
        if completed.returncode != 0 or not indexed.is_file() or indexed.stat().st_size == 0:
            return False
        indexed.replace(target)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        indexed.unlink(missing_ok=True)


def saved_recording(run_name: str | None) -> tuple[Path, str] | None:
    """Resolve the recording saved for one exact run without exposing run paths."""
    run_dir = safe_run_dir(run_name)
    if not run_name or run_dir is None or run_dir.name != run_name:
        return None
    metadata = read_json(run_dir / "recording.json")
    if not isinstance(metadata, dict):
        return None
    filename = Path(str(metadata.get("filename") or "")).name
    allowed = {"recording.mp4": "video/mp4", "recording.webm": "video/webm"}
    media_type = allowed.get(filename)
    if media_type is None:
        return None
    target = (run_dir / filename).resolve()
    if target.parent != run_dir.resolve() or not target.is_file():
        return None
    return target, media_type


def run_names() -> list[dict]:
    if not RUNS.exists():
        return []
    items = sorted(
        (item for item in RUNS.iterdir() if item.is_dir()),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    runs = []
    for item in items:
        manifest = read_json(item / "run_manifest.json", {}) or {}
        ids = manifest.get("case_ids")
        count = len(set(ids)) if isinstance(ids, list) else manifest.get("case_count_per_arm")
        runs.append({
            "name": item.name,
            "case_count": count,
            "started_at": manifest.get("started_at"),
            "modified": datetime.fromtimestamp(
                item.stat().st_mtime, tz=timezone.utc
            ).isoformat(),
        })
    return runs


def domain_for(case_id: str) -> str:
    if case_id.startswith("EYE-"):
        return "Eye"
    if case_id.startswith("ENT-"):
        return "ENT"
    if case_id.startswith("DER-"):
        return "Skin"
    return "Unknown"


def parse_worker_output(raw: str | None) -> dict:
    if not raw:
        return {"reply": None, "used_fact_ids": []}
    try:
        value = json.loads(raw)
        if isinstance(value, dict):
            return {
                "reply": value.get("reply") or raw,
                "used_fact_ids": value.get("used_fact_ids") or [],
            }
    except json.JSONDecodeError:
        pass
    return {"reply": raw, "used_fact_ids": []}


IMMEDIATE_HW_FIELDS = {
    "Age",
    "Sex",
    "Symptoms",
    "Duration",
    "History",
    "First Line for Alan",
    "Local resources / access",
}


def safe_fact_ids(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item.strip()]


def safe_hw_view(value) -> list[dict[str, str]]:
    """Return the complete saved non-gold view exposed to the health worker."""
    if not isinstance(value, list):
        return []
    blocked = {
        "case", "family code", "diagnosis", "management", "urgency",
        "primary design emphasis", "type", "topic", "target field(s)",
        "start (hidden)", "change when", "updated (hidden)", "expected handling",
    }
    safe: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        field = str(item.get("field") or "").strip()
        fact = str(item.get("value") or "").strip()
        if field and fact and field.lower() not in blocked:
            visible = {
                "field": field,
                "value": fact,
                "availability": (
                    "known_now" if field in IMMEDIATE_HW_FIELDS else "ask_or_check"
                ),
            }
            fact_id = str(item.get("id") or item.get("fact_id") or "").strip()
            if fact_id:
                visible["id"] = fact_id
            safe.append(visible)
    return safe


JUDGE_EVIDENCE_FIELDS = (
    "alan_primary_diagnosis",
    "diagnosis_correct",
    "assessment_kind", "assessment_objective_met", "screening_objective_met", "screening_reason",
    "alan_evidence_difference", "alan_evidence_reason", "deployable_pass",
    "serious_unsafe_advice",
    "observed_urgency_window",
    "urgency_difference",
    "urgency_reason",
    "urgency_correct",
    "management_difference",
    "management_reason",
    "management_adequate",
    "lmic_failure",
    "worker_protocol_difference",
    "worker_protocol_failure",
    "run_valid",
    "marker_appropriate",
    "marker_repetition_appropriate",
    "judge_reason",
)

USAGE_EVIDENCE_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)


def safe_judge_view(value) -> dict | None:
    """Return the saved structured verdict without any hidden model trace."""
    if not isinstance(value, dict):
        return None
    return {
        key: value.get(key)
        for key in JUDGE_EVIDENCE_FIELDS
        if key in value
    }


def safe_usage_view(value) -> dict[str, int | float]:
    if not isinstance(value, dict):
        return {}
    return {
        key: number
        for key in USAGE_EVIDENCE_FIELDS
        if isinstance((number := value.get(key)), (int, float))
        and not isinstance(number, bool)
    }


def case_evidence(run_dir: Path, case_id: str | None) -> dict | None:
    """Build a compact, safe view of the evidence saved for one completed case."""
    if not case_id:
        return None
    result_path = next(
        (
            path
            for path in (run_dir / "results").glob("*/*.json")
            if path.stem == case_id
        ),
        None,
    )
    result = read_json(result_path) if result_path else None
    if not isinstance(result, dict) or str(result.get("case_id") or result_path.stem) != case_id:
        return None

    transcript = []
    for item in result.get("transcript") or []:
        if not isinstance(item, dict):
            continue
        transcript.append({
            key: item.get(key)
            for key in ("role", "text", "opening", "turn", "after_alan_turn")
            if item.get(key) is not None
        })

    release_checks = []
    for entry in result.get("authorised_release_log") or []:
        if not isinstance(entry, dict):
            continue
        released = []
        for fact in entry.get("released") or []:
            if not isinstance(fact, dict):
                continue
            released.append({
                key: fact.get(key)
                for key in ("fact_id", "field", "value")
                if fact.get(key) is not None
            })
        legacy_checks = []
        for decision in entry.get("checker_results") or []:
            if not isinstance(decision, dict):
                continue
            legacy_checks.append({
                key: decision.get(key)
                for key in ("surface_attempt", "verdict", "reason")
                if decision.get(key) is not None
            })
        release_checks.append({
            "alan_turn": entry.get("alan_turn"),
            "released": released,
            "worker_reply": entry.get("worker_reply"),
            "worker_reply_words": entry.get("worker_reply_words"),
            "worker_style_warnings": [
                str(value) for value in (entry.get("worker_style_warnings") or [])
            ],
            "legacy_checks": legacy_checks,
        })

    calls = []

    def add_calls(stage: str, key: str, model_key: str, reasoning_key: str) -> None:
        raw_calls = result.get(key)
        if isinstance(raw_calls, dict):
            raw_calls = [raw_calls]
        for call in raw_calls or []:
            if not isinstance(call, dict):
                continue
            safe_call = {
                "stage": stage,
                "model": result.get(model_key),
                "reasoning_effort": result.get(reasoning_key),
                "usage": safe_usage_view(call.get("usage")),
            }
            for field in (
                "turn",
                "after_alan_turn",
                "surface_attempt",
                "attempts",
                "duration_ms",
            ):
                value = call.get(field)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    safe_call[field] = value
            calls.append(safe_call)

    add_calls("Alan", "model_calls", "model", "reasoning_effort")
    add_calls("HW", "worker_calls", "worker_model", "worker_reasoning_effort")
    add_calls("Legacy HW check", "checker_calls", "checker_model", "checker_reasoning_effort")
    add_calls("Judge", "judge_call", "judge_model", "judge_reasoning_effort")

    recording = read_json(run_dir / "recording.json")
    safe_recording = None
    if isinstance(recording, dict):
        safe_recording = {
            key: recording.get(key)
            for key in ("filename", "content_type", "bytes", "sha256", "saved_at")
            if recording.get(key) is not None
        }

    return {
        "run": run_dir.name,
        "case_id": case_id,
        "arm": result.get("arm") or (result_path.parent.name if result_path else None),
        "transcript": transcript,
        "release_checks": release_checks,
        "judge": safe_judge_view(result.get("judgement")),
        "calls": calls,
        "recording": safe_recording,
        "private_reasoning_available": False,
        "private_reasoning_note": (
            "Private chain-of-thought is not recorded or shown. The saved evidence "
            "includes the judge's structured verdict, short reason and usage metadata."
        ),
    }


def partial_case(case_dir: Path, failure: str | None, run_dir: Path) -> dict:
    case_id = case_dir.name
    source_case = pilot_case(case_id, run_dir)
    messages: list[dict] = []
    used_fact_ids: set[str] = set()
    if source_case.get("First Line for Alan"):
        messages.append({
            "role": "health_worker",
            "text": source_case["First Line for Alan"],
            "opening": True,
        })
    retries: list[dict] = []
    for turn_dir in sorted(case_dir.glob("turn_*")):
        match = re.fullmatch(r"turn_(\d+)", turn_dir.name)
        if not match:
            continue
        turn = int(match.group(1))
        alan = read_text(turn_dir / "last.txt")
        if alan:
            messages.append({"role": "alan", "text": alan, "turn": turn})
        worker_dir = case_dir / f"worker_after_{turn:02d}"
        attempts = sorted(
            worker_dir.glob("attempt_*"),
            key=lambda p: int(p.name.split("_")[-1]),
        ) if worker_dir.exists() else []
        parsed_attempts = []
        for attempt in attempts:
            parsed = parse_worker_output(read_text(attempt / "last.txt"))
            if parsed["reply"]:
                parsed_attempts.append({
                    "attempt": int(attempt.name.split("_")[-1]),
                    **parsed,
                })
        # A worker attempt is accepted only when the runner has started Alan's next turn.
        # This prevents a rejected over-polished or invented reply flashing as real dialogue.
        next_turn_started = (case_dir / f"turn_{turn + 1:02d}").exists()
        if parsed_attempts and next_turn_started:
            accepted = parsed_attempts[-1]
            used_fact_ids.update(safe_fact_ids(accepted.get("used_fact_ids")))
            messages.append({
                "role": "health_worker",
                "text": accepted["reply"],
                "after_alan_turn": turn,
                "provisional": True,
            })
            if len(parsed_attempts) > 1:
                retries.extend(
                    {"after_alan_turn": turn, **attempt}
                    for attempt in parsed_attempts[:-1]
                )
    if (source_case.get("extra_test", {}).get("contract") == "extra50-dialogue-v2"
            or any(case_dir.glob("worker_after_*/composition.json"))):
        # Accepted events contain driver challenges and composed observation replies.
        # Raw selector JSON is a choice record, not the words spoken to Alan.
        events = read_events(case_dir / "replay.jsonl")
        if events and isinstance(events[-1].get("messages"), list):
            messages = events[-1]["messages"]
    judge = parse_worker_output(read_text(case_dir / "judge" / "last.txt"))["reply"]
    activity, active_since = activity_for_case(case_dir)
    live_state = read_json(case_dir / "live_state.json", {}) or {}
    hw_view = safe_hw_view(live_state.get("hw_view"))
    if not hw_view and source_case.get("First Line for Alan"):
        hw_view = safe_hw_view([
            {"field": "First Line for Alan", "value": str(source_case["First Line for Alan"])}
        ])
    active_fact_ids = safe_fact_ids(live_state.get("used_fact_ids"))
    used_fact_ids.update(active_fact_ids)
    return {
        "case_id": case_id,
        "domain": domain_for(case_id),
        "status": "failed" if failure else "running",
        "messages": messages,
        "retries": retries,
        "judge": read_json(case_dir / "judge" / "last.txt") if judge else None,
        "failure": model_failure_reason(case_dir, failure),
        "hw_view": hw_view,
        "hw_view_active_ids": active_fact_ids,
        "hw_view_used_ids": sorted(used_fact_ids.intersection(str(f["id"]) for f in hw_view if f.get("id"))),
        "hw_view_phase": live_state.get("phase") or "alan",
        "hw_view_turn": live_state.get("alan_turn"),
        "hw_view_reason": live_state.get("view_mode"),
        "turns": max((m.get("turn", 0) for m in messages), default=0),
        "activity": "Runner stopped" if failure else activity,
        "active_since": None if failure else active_since,
        "started_at": iso_timestamp(case_dir),
        "stop_reason": None,
        "modified": latest_file_update([case_dir, *case_dir.rglob("*")]),
    }


def complete_case(result_path: Path, run_dir: Path, bank: dict | None = None) -> dict | None:
    result = read_json(result_path)
    if not isinstance(result, dict):
        return None
    call_duration_ms = sum(
        float(call.get("duration_ms") or 0)
        for call in (result.get("model_calls") or []) + (result.get("worker_calls") or [])
        if isinstance(call, dict)
    )
    if isinstance(result.get("judge_call"), dict):
        call_duration_ms += float(result["judge_call"].get("duration_ms") or 0)
    duration_ms = float(result.get("elapsed_ms") or call_duration_ms)
    case_id = str(result.get("case_id") or result_path.stem)
    source_case = bank.get(case_id, {}) if bank is not None else pilot_case(case_id, run_dir)
    messages = []
    for item in result.get("transcript") or []:
        if not isinstance(item, dict):
            continue
        messages.append({
            key: item.get(key)
            for key in ("role", "text", "opening", "turn", "after_alan_turn", "scripted_challenge", "model_reply", "appended_pressure")
            if item.get(key) is not None
        })
    retries = []
    case_dir = result_path.parents[2] / "calls" / result_path.parent.name / case_id
    for worker_dir in sorted(case_dir.glob("worker_after_*")):
        attempts = sorted(
            worker_dir.glob("attempt_*"),
            key=lambda p: int(p.name.split("_")[-1]),
        )
        if len(attempts) <= 1:
            continue
        turn = int(worker_dir.name.split("_")[-1])
        for attempt in attempts[:-1]:
            parsed = parse_worker_output(read_text(attempt / "last.txt"))
            if parsed["reply"]:
                retries.append({
                    "after_alan_turn": turn,
                    "attempt": int(attempt.name.split("_")[-1]),
                    **parsed,
                })
    judgement = result.get("judgement")
    safe_judge = safe_judge_view(judgement)
    quality = result.get("quality")
    # A completed run is an immutable evaluation receipt. Recompute only legacy
    # results that never saved a score; do not silently apply today's rubric to
    # historical runs.
    if not isinstance(quality, dict) and isinstance(judgement, dict):
        quality = build_quality_metrics(
            source_case,
            str(result.get("arm") or result_path.parent.name),
            list(result.get("transcript") or []),
            judgement,
        )
    visible_log = result.get("worker_visible_fact_log") or []
    legacy_offer_log = result.get("offered_fact_log") or []
    fact_log = visible_log or legacy_offer_log
    last_view = fact_log[-1] if fact_log and isinstance(fact_log[-1], dict) else {}
    displayed_view = next(
        (
            item
            for item in reversed(fact_log)
            if isinstance(item, dict)
            and safe_hw_view(item.get("visible_facts") or item.get("offered"))
        ),
        last_view,
    )
    hw_view = safe_hw_view(result.get("final_hw_view")) or safe_hw_view(displayed_view.get("visible_facts") or displayed_view.get("offered"))
    if not hw_view and source_case.get("First Line for Alan"):
        hw_view = safe_hw_view([
            {"field": "First Line for Alan", "value": str(source_case["First Line for Alan"])}
        ])
    displayed_fact_ids = {
        str(fact["id"])
        for fact in hw_view
        if fact.get("id")
    }
    cumulative_active_ids: list[str] = []
    seen_active_ids: set[str] = set()
    for entry in fact_log:
        if not isinstance(entry, dict):
            continue
        for fact_id in safe_fact_ids(entry.get("used_fact_ids")):
            if fact_id in displayed_fact_ids and fact_id not in seen_active_ids:
                seen_active_ids.add(fact_id)
                cumulative_active_ids.append(fact_id)
    return {
        "case_id": case_id,
        "domain": result.get("domain") or domain_for(case_id),
        "diagnosis": source_case.get("Diagnosis"),
        "status": "complete",
        "messages": messages,
        "retries": retries,
        "judge": safe_judge,
        "quality": quality,
        "failure": None,
        "hw_view": hw_view,
        "hw_view_active_ids": cumulative_active_ids,
        "hw_view_phase": "complete",
        "hw_view_turn": displayed_view.get("alan_turn"),
        "hw_view_reason": displayed_view.get("view_mode") or displayed_view.get("response_reason"),
        "turns": result.get("turns"),
        "duration_ms": round(duration_ms),
        "activity": "Complete",
        "active_since": None,
        "started_at": result.get("started_at") or iso_timestamp(case_dir),
        "stop_reason": result.get("stop_reason"),
        "modified": result.get("completed_at") or latest_file_update([result_path]),
    }


def next_configuration_view() -> dict | None:
    try:
        from release_config import load_config, display_config
        return display_config(load_config())
    except (OSError, KeyError, TypeError, ValueError):
        return None


def build_state(run_dir: Path | None) -> dict:
    if run_dir is None:
        return {"run": None, "runs": run_names(), "cases": [], "error": "No runs found"}

    manifest = read_json(run_dir / "run_manifest.json", {}) or {}
    failures_raw = read_json(run_dir / "failures.json", []) or []
    failures = {
        str(item.get("case_id")): str(item.get("error"))
        for item in failures_raw
        if isinstance(item, dict) and item.get("case_id")
    }
    cases: dict[str, dict] = {}

    bank = case_bank(run_dir)
    results_root = run_dir / "results"
    if results_root.exists():
        for result_path in results_root.glob("*/*.json"):
            item = complete_case(result_path, run_dir, bank)
            if item:
                cases[item["case_id"]] = item

    calls_root = run_dir / "calls"
    if calls_root.exists():
        for case_dir in calls_root.glob("*/*"):
            if not case_dir.is_dir() or case_dir.name in cases:
                continue
            cases[case_dir.name] = partial_case(case_dir, failures.get(case_dir.name), run_dir)
            resumes = manifest.get("resume_events") or []
            resumed_at = resumes[-1].get("resumed_at") if resumes else None
            if resumed_at and not failures.get(case_dir.name):
                try:
                    resume_time = datetime.fromisoformat(resumed_at.replace("Z", "+00:00")).timestamp()
                    if case_dir.stat().st_ctime < resume_time:
                        cases[case_dir.name].update(status="queued", activity="Waiting for recovery", active_since=None)
                except (ValueError, TypeError):
                    pass

    for case_id, error in failures.items():
        if case_id not in cases:
            cases[case_id] = {
                "case_id": case_id,
                "domain": domain_for(case_id),
                "status": "failed",
                "messages": [],
                "retries": [],
                "judge": None,
                "failure": error,
                "hw_view": [],
                "hw_view_active_ids": [],
                "hw_view_phase": "failed",
                "hw_view_turn": None,
                "hw_view_reason": None,
                "turns": 0,
                "stop_reason": None,
                "modified": None,
            }

    status_order = {"running": 0, "failed": 1, "complete": 2}
    ordered = sorted(
        cases.values(),
        key=lambda item: (
            status_order.get(item.get("status"), 9),
            item.get("modified") or "",
            item["case_id"],
        ),
    )
    status_counts = {
        status: sum(item["status"] == status for item in ordered)
        for status in ("running", "complete", "failed")
    }
    sequence = [str(case_id) for case_id in manifest.get("case_ids", [])]
    if not sequence:
        sequence = sorted(cases)
    for item in ordered:
        item["case_index"] = sequence.index(item["case_id"]) + 1 if item["case_id"] in sequence else None
        item["case_total"] = len(sequence) or manifest.get("case_count_per_arm")
        for key in ("repeat", "repeat_position", "source_case_id"):
            if key in bank.get(item["case_id"], {}): item[key] = bank[item["case_id"]][key]
    # Review notes are a separate, versioned record. They never replace scores.
    review = read_json(RUNS / "reviews" / f"{run_dir.name}.json", {}) or {}
    if review.get("source_cases_sha256") == manifest.get("cases_sha256") and review.get("source_cases_sha256"):
        notes = review.get("cases", {})
        for item in ordered:
            note = notes.get(item["case_id"])
            if isinstance(note, dict):
                item["case_review"] = {
                    key: str(note[key])[:3000] for key in
                    ("status", "owner", "finding", "action", "decision") if key in note
                }
    activity_dates = [item.get("modified") for item in ordered]
    activity_dates += [manifest.get("started_at"), manifest.get("finished_at"), latest_file_update([
        run_dir / "run_manifest.json", run_dir / "failures.json", run_dir / "STOP_REQUESTED",
    ])]
    activity_timestamps = []
    for value in activity_dates:
        try:
            activity_timestamps.append(datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp())
        except (ValueError, TypeError):
            continue
    last_activity = datetime.fromtimestamp(max(activity_timestamps), timezone.utc).isoformat() if activity_timestamps else None
    manifest_view = {
        key: manifest.get(key)
        for key in (
            "runner_version",
            "model",
            "reasoning_effort",
            "model_transport",
            "worker_model",
            "worker_reasoning_effort",
            "worker_transport",
            "checker_model",
            "checker_reasoning_effort",
            "checker_transport",
            "judge_model",
            "judge_reasoning_effort",
            "judge_transport",
            "arms",
            "case_count_per_arm",
            "case_ids",
            "concurrency",
            "stop_mode",
            "worker",
            "turn_rule",
            "worker_reply_limits",
            "quality_scoring_version",
            "challenge_index_version",
            "cases_sha256",
            "workbook_sha256",
            "raw_prompt_sha256",
            "worker_prompt_sha256",
            "worker_prompt_label",
            "worker_guard_sha256",
            "evaluation_profile",
            "explicit_configuration", "assessment_contract", "judge_prompt_version", "judge_schema_sha256",
            "display_consolidation",
            "separate_worker_audit",
            "extra_input_sha256",
            "checker_prompt_sha256",
            "judge_prompt_sha256",
            "started_at",
            "finished_at",
        )
    }
    # Every historical run in this monitor was produced through CodexInvoker.
    manifest_view["model_transport"] = manifest_view.get("model_transport") or "codex"
    manifest_view["worker_transport"] = manifest_view.get("worker_transport") or "codex"
    if manifest_view.get("checker_model"):
        manifest_view["checker_transport"] = manifest_view.get("checker_transport") or "codex"
    manifest_view["judge_transport"] = manifest_view.get("judge_transport") or "codex"
    manifest_view.update(alan_version_for(manifest))
    return {
        "last_activity_at": last_activity,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run": run_dir.name,
        "runs": run_names(),
        "manifest": manifest_view,
        "runner_defaults": {**CURRENT_RUNNER_ROUTE, **current_local_alan()},
        "status_counts": status_counts,
        "cases": ordered,
        "worker_view_layout": worker_layout_views(run_dir, manifest),
        "next_configuration": next_configuration_view(),
        "recording": read_json(run_dir / "recording.json"),
        "invalid": (run_dir / "INVALID_RUN.md").exists(),
        "stop_requested": (run_dir / "STOP_REQUESTED").exists(),
        "error": None,
    }


def build_replay_payload(run_dir: Path) -> dict:
    manifest = read_json(run_dir / "run_manifest.json", {}) or {}
    failures = read_json(run_dir / "failures.json", []) or []
    failed_ids = {f.get("case_id") for f in failures if isinstance(f, dict) and f.get("arm", "full_alan") == "full_alan"}
    cases = []
    for case_id in manifest.get("case_ids", []):
        item = {"case_id": str(case_id), "events": [], "complete": False, "status": "missing", "recovered": False}
        cases.append(item)
        if not re.fullmatch(r"[A-Za-z0-9_-]+", str(case_id)):
            item["status"] = "damaged"
            continue
        try:
            events = read_events(run_dir / "calls" / "full_alan" / case_id / "replay.jsonl")
            if any(event.get("case_id") != case_id for event in events):
                raise ValueError("Replay case ID does not match")
            result = read_json(run_dir / "results" / "full_alan" / f"{case_id}.json", {}) or {}
            events = recover_completion(events, result)
            for event in events:
                event["hw_view"] = safe_hw_view(event.get("hw_view"))
                if event.get("judge"):
                    event["judge"] = safe_judge_view(event["judge"])
            complete = bool(events and events[-1]["phase"] == "complete")
            item.update(events=events, complete=complete,
                        status="complete" if complete else "failed" if case_id in failed_ids else "unfinished" if events else "missing",
                        recovered=bool(complete and events[-1].get("recovered")))
        except (ValueError, OSError, TypeError):
            # One damaged case must not hide every other recording in the run.
            item["status"] = "damaged"
    coverage = {key: sum(c["status"] == key for c in cases)
                for key in ("complete", "unfinished", "failed", "missing", "damaged")}
    coverage.update(expected=len(cases), recovered=sum(c["recovered"] for c in cases))
    return {"run": run_dir.name, "timing": "recorded_events", "text_animation": "presentation_only",
            "run_active": not bool(manifest.get("finished_at")) and any(c["status"] not in {"complete", "failed"} for c in cases),
            "coverage": coverage, "cases": cases}


class MonitorHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(HERE), **kwargs)

    def end_headers(self) -> None:
        if urlparse(self.path).path in (
            "/", "/index.html", "/replay.js", "/replay-core.js",
            "/replay-export.js", "/replay.css",
        ):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format: str, *args) -> None:
        return

    def send_json(self, status: HTTPStatus, value: dict) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_recording(self, parsed, *, include_body: bool) -> None:
        """Serve one saved recording with browser-seekable byte ranges."""
        query = parse_qs(parsed.query)
        recording = saved_recording((query.get("run") or [None])[0])
        if recording is None:
            self.send_json(
                HTTPStatus.NOT_FOUND,
                {"ok": False, "error": "Recording not found"},
            )
            return

        target, media_type = recording
        size = target.stat().st_size
        start = 0
        end = max(0, size - 1)
        status = HTTPStatus.OK
        range_header = self.headers.get("Range")
        if range_header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
            if match is None or (not match.group(1) and not match.group(2)):
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if match.group(1):
                start = int(match.group(1))
                if start >= size:
                    self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                end = int(match.group(2)) if match.group(2) else size - 1
                end = min(end, size - 1)
                if end < start:
                    self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
            else:
                suffix_length = min(int(match.group(2)), size)
                start = size - suffix_length
                end = size - 1
            status = HTTPStatus.PARTIAL_CONTENT

        content_length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(content_length))
        self.send_header("Accept-Ranges", "bytes")
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header(
            "Content-Disposition", f'inline; filename="{target.name}"'
        )
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not include_body:
            return
        try:
            remaining = content_length
            with target.open("rb") as handle:
                handle.seek(start)
                while remaining:
                    chunk = handle.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/recording":
            self.send_recording(parsed, include_body=False)
            return
        super().do_HEAD()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/replay":
            query = parse_qs(parsed.query)
            run_dir = safe_run_dir((query.get("run") or [None])[0])
            if run_dir is None:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "Run not found"})
                return
            self.send_json(HTTPStatus.OK, build_replay_payload(run_dir))
            return
        if parsed.path == "/api/state":
            query = parse_qs(parsed.query)
            state = build_state(safe_run_dir((query.get("run") or [None])[0]))
            self.send_json(HTTPStatus.OK, state)
            return
        if parsed.path == "/api/recording":
            self.send_recording(parsed, include_body=True)
            return
        if parsed.path == "/api/evidence":
            query = parse_qs(parsed.query)
            run_dir = safe_run_dir((query.get("run") or [None])[0])
            case_id = (query.get("case") or [None])[0]
            evidence = case_evidence(run_dir, case_id) if run_dir else None
            if evidence is None:
                self.send_json(
                    HTTPStatus.NOT_FOUND,
                    {"ok": False, "error": "Saved case evidence not found"},
                )
                return
            self.send_json(HTTPStatus.OK, {"ok": True, "evidence": evidence})
            return
        if parsed.path in ("/", "/index.html"):
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/clipboard":
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
            except ValueError:
                length = 0
            if length <= 0 or length > MAX_CLIPBOARD_BYTES:
                self.send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "Invalid clipboard payload"},
                )
                return
            body = read_json_from_bytes(self.rfile.read(length))
            plain_text = body.get("plain") if isinstance(body, dict) else None
            rich_html = body.get("html") if isinstance(body, dict) else None
            rich_rtf = body.get("rtf") if isinstance(body, dict) else None
            if not all(isinstance(value, str) and value for value in (plain_text, rich_html, rich_rtf)):
                self.send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "Clipboard formats are incomplete"},
                )
                return
            try:
                write_windows_clipboard(plain_text, rich_html, rich_rtf)
            except OSError as exc:
                self.send_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"ok": False, "error": str(exc)},
                )
                return
            self.send_json(
                HTTPStatus.OK,
                {"ok": True, "mode": "outlook", "formats": ["RTF", "HTML", "plain text"]},
            )
            return
        if parsed.path == "/api/recording":
            query = parse_qs(parsed.query)
            run_name = (query.get("run") or [None])[0]
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
            except ValueError:
                self.send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "Invalid recording length"},
                )
                return
            try:
                recording = save_recording(
                    run_name,
                    self.headers.get("Content-Type", ""),
                    length,
                    self.rfile,
                )
            except OverflowError as exc:
                self.send_json(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    {"ok": False, "error": str(exc)},
                )
                return
            except FileExistsError as exc:
                self.send_json(
                    HTTPStatus.CONFLICT,
                    {"ok": False, "error": str(exc)},
                )
                return
            except (EOFError, ValueError) as exc:
                self.send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": str(exc)},
                )
                return
            except OSError:
                self.send_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"ok": False, "error": "Recording could not be written"},
                )
                return
            self.send_json(HTTPStatus.CREATED, {"ok": True, "recording": recording})
            return
        if parsed.path != "/api/stop":
            self.send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Not found"})
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = read_json_from_bytes(self.rfile.read(length))
        run_dir = safe_run_dir(body.get("run") if isinstance(body, dict) else None)
        if run_dir is None:
            self.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Run not found"})
            return
        manifest = read_json(run_dir / "run_manifest.json", {}) or {}
        if manifest.get("finished_at"):
            self.send_json(HTTPStatus.CONFLICT, {"ok": False, "error": "Run already complete"})
            return
        (run_dir / "STOP_REQUESTED").write_text(
            f"Requested from live monitor at {datetime.now(timezone.utc).isoformat()}\n",
            encoding="utf-8",
            newline="\n",
        )
        self.send_json(HTTPStatus.OK, {"ok": True, "mode": "after current model reply"})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), MonitorHandler)
    print(f"Alan live monitor: http://{args.host}:{args.port}/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
