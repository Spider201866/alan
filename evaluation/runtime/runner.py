from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from quality_scoring import (
    MATERIAL_URGENCY_DIFFERENCES,
    MINOR_URGENCY_DIFFERENCES,
    QUALITY_SCORING_VERSION,
    build_quality_metrics,
    expects_emergency_exit,
    has_emergency_exit_diagnosis as scoring_has_emergency_exit_diagnosis,
    has_emergency_exit_closing as scoring_has_emergency_exit_closing,
    has_primary_diagnosis as scoring_has_primary_diagnosis,
    _has_terminal_closing as scoring_has_terminal_closing,
    question_count,
    resolved_management_difference,
    resolved_urgency_difference,
    word_count as scoring_word_count,
)
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
from replay_events import ReplayRecorder
from extra50_support import (CHALLENGE_INDEX_VERSION, behaviour_case, opening_only, behaviour_payload, behaviour_quality,
                             dialogue_test, test_mode, dialogue_stop)


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_WORKBOOK = ROOT / "data/cases.xlsx"
ALAN_GITHUB_URL = "https://github.com/Spider201866/alan"
DEFAULT_ALAN_GIT_REF = "origin/main"
ALAN_GIT_PROMPT_PATH = "alan_compiled.txt"
DEFAULT_CASES = ROOT / "data/cases.json"
DEFAULT_RUN_ROOT = ROOT / "runs"
PILOT_IDS = ROOT / "data/selection.json"
RAW_PROMPT = ROOT / "prompts/raw.txt"
JUDGE_PROMPT = ROOT / "prompts/judge.txt"
JUDGE_SCHEMA = ROOT / "schemas/judge.json"
HEALTH_WORKER_PROMPT = ROOT / "prompts/health_worker.txt"
HEALTH_WORKER_SCHEMA = ROOT / "schemas/health_worker.json"

WORKBOOK_EXPECTED_SHA256 = "6CF355D03577FFB60CE19A98E0894E56D1D798CE07D06438541E2075B2D8EBB1"
MIN_TURNS = 5
NORMAL_TURNS = "LOGIC 1 -> 2 -> 3 -> 4 -> 5"
MAX_TURNS = 7
MAX_WORKER_FACTS = 2
MAX_WORKER_WORDS = 8
DEFAULT_RUN_DIR = DEFAULT_RUN_ROOT / f"pilot20_sol_medium_worker_v{RUNNER_VERSION.rsplit('v', 1)[-1]}"
NAMESPACE = uuid.UUID("496162f3-03d3-42d7-ae50-b4093d15d987")

CASE_SHEETS = {
    "Eye Cases": ("Eye", 21),
    "ENT Cases": ("ENT", 22),
    "Skin Cases": ("Skin", 23),
}

PATIENT_FIELDS = ["Age", "Sex", "Symptoms", "Duration", "History"]
RESOURCE_FIELD = "Local resources / access"
GOLD_FIELDS = {
    "Case",
    "Family code",
    "Diagnosis",
    "Management",
    "Urgency",
    "Expected marker",
    "Marker trigger",
    "Expected emergency exit",
    "Fast-4 trigger",
    "Fast-4 eligible",
}

CHECK_FIELDS = {
    "Eye": [
        "Visual Acuity",
        "Pupils",
        "Front of Eye & Lids",
        "Fundal Reflex",
        "Back of Eye",
        "Tests",
    ],
    "ENT": [
        "Hearing",
        "Pinna / Mastoid",
        "Ear Canal",
        "Tympanic Membrane",
        "Nose",
        "Throat / Neck",
        "Tests",
    ],
    "Skin": [
        "Site / side",
        "Distribution",
        "Morphology",
        "Colour / Surface",
        "Sensation",
        "Systemic Signs",
        "Hair / Nails / Mucosa",
        "Tests",
    ],
    # Ad-hoc cross-scope emergency probes have no spreadsheet examination
    # fields. They can still expose the common patient and access fields if
    # Alan fails to take the intended one-reply emergency exit.
    "Other": [],
}

REQUEST_FIELD_DESCRIPTIONS = {
    "Age": "The patient's age or age group.",
    "Sex": "The patient's sex or gender as recorded.",
    "Symptoms": "Current symptoms, complaints and what the patient can or cannot perceive.",
    "Duration": "When the problem began, how long it has lasted and its time course.",
    "History": "Relevant events, exposures, medicines, illnesses, operations and prior history.",
    "Visual Acuity": "What each eye can see, including measured acuity, counting fingers, hand movements and light perception.",
    "Pupils": "Pupil size, equality and reaction to light, including RAPD checks.",
    "Front of Eye & Lids": "Lids, cornea, conjunctiva, iris, anterior chamber and other front-of-eye findings.",
    "Fundal Reflex": "Red, white or absent fundal reflex and pupil glow.",
    "Back of Eye": "Fundus, retina, optic disc, macula and other back-of-eye findings.",
    "Hearing": "Hearing ability and bedside hearing tests.",
    "Pinna / Mastoid": "Outer ear, tragus, pinna and mastoid findings.",
    "Ear Canal": "Ear-canal contents and findings inside the canal.",
    "Tympanic Membrane": "Eardrum or tympanic-membrane findings.",
    "Nose": "Nasal examination, airflow, smell and nostril findings.",
    "Throat / Neck": "Mouth, tongue, throat, teeth, salivary ducts, voice, swallowing and neck findings.",
    "Site / side": "Where a skin problem is and which side is affected.",
    "Distribution": "How a skin problem is arranged or spread across the body.",
    "Morphology": "Shape, border, size, depth and lesion type.",
    "Colour / Surface": "Colour, scale, crust, fluid, bleeding and surface appearance.",
    "Sensation": "Itch, pain, tenderness, numbness and other sensation.",
    "Systemic Signs": "Fever, general illness, alertness, drinking, breathing and lymph-node findings.",
    "Hair / Nails / Mucosa": "Hair, nails, scalp, mouth, mucosa and genital involvement.",
    "Tests": "Named bedside, measurement or diagnostic test results for this domain.",
    RESOURCE_FIELD: "Availability, access, distance, transport, cost and local referral resources.",
}

FIELD_LABELS = {
    "Visual Acuity": "VA",
    "Front of Eye & Lids": "front/lids",
    "Fundal Reflex": "reflex",
    "Back of Eye": "back",
    "Pinna / Mastoid": "pinna/mastoid",
    "Ear Canal": "canal",
    "Tympanic Membrane": "drum",
    "Throat / Neck": "throat/neck",
    "Site / side": "site",
    "Colour / Surface": "colour/surface",
    "Systemic Signs": "general",
    "Hair / Nails / Mucosa": "hair/nails/mouth",
    RESOURCE_FIELD: "local access",
    "active_state": "recheck",
}

COMMON_ALIASES = {
    "Age": [r"\bage\b", r"how old", r"old is (?:he|she|the|this)", r"child or adult"],
    "Sex": [r"\bsex\b", r"male or female", r"boy or girl", r"man or woman"],
    "Symptoms": [
        r"symptom", r"complain", r"pain", r"itch", r"blur", r"discharge", r"watering",
        r"feel", r"dizz", r"weak", r"numb", r"hearing loss", r"vision loss", r"sight loss",
    ],
    "Duration": [r"how long", r"when did", r"when .* start", r"onset", r"sudden or gradual", r"duration", r"\bgrow", r"\bchang"],
    "History": [
        r"history", r"injur", r"trauma", r"hit ", r"exposure", r"chemical", r"medicine", r"drug",
        r"drops", r"diabet", r"blood pressure", r"\bhiv\b", r"\btb\b", r"smok", r"\bwork\b", r"\bjob\b", r"contact", r"ever had", r"prescrib", r"previous assessment",
        r"previous", r"surgery", r"operation", r"pregnan", r"vaccin", r"diet", r"river", r"travel",
        r"animal", r"alcohol", r"headache", r"weight loss", r"family", r"\bgrow", r"\bchang", r"cleaner", r"product", r"bottle", r"substance",
        r"\bmeals?\b", r"\beat(?:ing)?\b", r"\bfood\b",
    ],
    RESOURCE_FIELD: [
        r"available", r"equipment", r"tool", r"resource", r"access", r"how far", r"travel time", r"distance to (?:clinic|hospital|referral)",
        r"transport", r"transfer", r"cost", r"afford", r"hospital", r"clinic", r"specialist (?:available|access|referral)", r"referral", r"refer",
    ],
}

DOMAIN_ALIASES = {
    "Eye": {
        "Visual Acuity": [
            r"visual acuity", r"\bva\b", r"pinhole", r"\bph\b", r"\bvision\b",
            r"\bsight\b", r"can .* see", r"distance vision", r"near vision",
            r"\blight perception\b",
            r"\b(?:detect|perceiv)\w*\s+(?:only\s+)?light\b",
            r"\b(?:see|sees|seeing)\s+(?:only\s+)?light\b",
        ],
        "Pupils": [r"pupil", r"\brapd\b", r"react"],
        "Front of Eye & Lids": [r"\bcornea\b", r"front of eye", r"\blid\b", r"\beyelid\b", r"red eye", r"white spot", r"\bchamber\b", r"\biris(?:es)?\b", r"\bhypopyon\b", r"(?<!contact )\blens(?:es)?\b", r"\bevert\b", r"\blump\b", r"\bbump\b", r"eye swelling", r"nystag", r"wobbl", r"squint"],
        "Fundal Reflex": [r"fundal reflex", r"red reflex", r"white reflex", r"pupil glow", r"leukocoria"],
        "Back of Eye": [r"back of eye", r"\bfund(?:us|i)\b", r"\bretina(?:e|l)?\b", r"\bdiscs?\b", r"\bmacula(?:e|r|s)?\b", r"haemorrhag", r"hemorrhag", r"exudate", r"retinal pigment", r"choroidal", r"ophthalmoscop"],
        "Tests": [r"nafl", r"fluorescein", r"stain", r"pressure", r"\biop\b", r"tonomet", r"field", r"amsler", r"blood sugar", r"glucose", r"\bbp\b", r"temperature", r"\btest", r"plus lens", r"\+\d+(?:\.\d+)?", r"\badd\b", r"refraction", r"light direction", r"light projection", r"project light", r"colour vision", r"color vision", r"pulsat", r"mobile", r"fixed", r"measure (?:size|pressure|diameter)", r"remeasure", r"eye movement"],
    },
    "ENT": {
        "Hearing": [r"\bhear(?:ing|s)?\b", r"voice test", r"weber", r"rinne", r"tuning fork"],
        "Pinna / Mastoid": [r"pinna", r"outer ear", r"tragus", r"mastoid", r"behind (?:the )?ear"],
        "Ear Canal": [r"ear canal", r"inside (?:the )?ear", r"ear discharge", r"object in (?:the )?ear"],
        "Tympanic Membrane": [r"eardrum", r"ear drum", r"tympanic", r"\bdrum\b"],
        "Nose": [r"nose", r"nostril", r"nasal", r"smell", r"airflow", r"stalk"],
        "Throat / Neck": [r"throat", r"mouth", r"tongue", r"neck", r"jaw", r"palate", r"tonsil", r"uvula", r"voice", r"swallow", r"node", r"lump", r"hard bit", r"drool", r"breath", r"hoarse", r"stridor", r"trismus", r"teeth", r"tooth", r"gum", r"duct", r"saliva", r"stalk"],
        "Tests": [r"temperature", r"\btemp\b", r"blood pressure", r"\bbp\b", r"pulse", r"oxygen", r"scope", r"\btest"],
    },
    "Skin": {
        "Site / side": [r"where", r"site", r"which side", r"body part"],
        "Distribution": [r"distribution", r"spread", r"elsewhere", r"other skin", r"symmetr", r"arrang", r"palms", r"soles", r"percentage", r"percent", r"body surface", r"how much skin"],
        "Morphology": [r"look like", r"shape", r"border", r"bump", r"blister", r"ulcer", r"lesion", r"track", r"plaque", r"size", r"large", r"deep", r"depth", r"diameter", r"millimet", r"percentage", r"percent"],
        "Colour / Surface": [r"colour", r"color", r"surface", r"scale", r"crust", r"fluid", r"ooze", r"bleed"],
        "Sensation": [r"itch", r"pain", r"numb", r"sensation", r"tender", r"feel"],
        "Systemic Signs": [r"fever", r"hot", r"unwell", r"alert", r"drink", r"breath", r"systemic", r"general", r"node", r"groin", r"weak", r"wasting", r"claw"],
        "Hair / Nails / Mucosa": [r"hair", r"nail", r"mouth", r"mucosa", r"scalp", r"\beyes?\b", r"genital"],
        "Tests": [r"test", r"scrap", r"biopsy", r"dermoscop", r"temperature", r"\bbp\b", r"glucose", r"pulse", r"photograph", r"measure", r"strength", r"nerve", r"sensation"],
    },
    "Other": {},
}

TEST_FACT_TOPICS = {
    "fluorescein": [r"\bnafl\b", r"fluorescein", r"\bstain(?:ing|s|ed)?\b"],
    "leak": [r"\bseidel\b", r"\b(?:wound|fluid) leak", r"\bleak(?:ing|s|ed)?\b"],
    "eye_pressure": [r"\biop\b", r"eye pressure", r"tonomet"],
    "blood_pressure": [r"\bbp\b", r"blood pressure"],
    "glucose": [r"glucose", r"blood sugar", r"\bsugar\b"],
    "temperature": [r"temperature", r"\btemp\b", r"°c"],
    "pulse": [r"\bpulse\b", r"heart rate"],
    "oxygen": [r"\boxygen\b", r"spo2", r"saturation"],
    "breathing": [r"breath(?:ing|s)?", r"airway", r"stridor", r"indrawing"],
    "neurology": [r"face[- ]arm[- ]speech", r"neurolog", r"limb check", r"speech check"],
    "movement": [r"movement", r"motility", r"move(?:s|ment)?", r"mobile"],
    "field": [r"visual field", r"\bfield(?:s)?\b"],
    "amsler": [r"amsler", r"distortion"],
    "pinhole": [r"pinhole", r"\bph\b"],
    "refraction": [r"refraction", r"trial lens", r"plus lens", r"minus lens", r"\badd\b"],
    "light_direction": [r"light direction", r"light projection", r"project light"],
    "colour_vision": [r"colou?r vision", r"colou?r plate"],
    "photograph": [r"photo", r"photograph", r"picture", r"image"],
    "lump_character": [r"tender", r"pulsat", r"fixed", r"hard edge", r"wipe(?:s|d)? off"],
    "saliva_duct": [r"saliva", r"salivary", r"\bduct\b"],
    "voice": [r"voice test", r"compare voice", r"spoken voice"],
    "weber": [r"weber"],
    "rinne": [r"rinne"],
    "bleeding": [r"bleed", r"blood on contact"],
    "tracks": [r"track", r"burrow"],
    "burn_size": [r"burn size", r"body surface", r"percent", r"measure.*burn"],
    "dermoscopy": [r"dermoscop"],
    "biopsy": [r"biopsy", r"histolog"],
    "sensation": [r"sensation", r"numb", r"touch"],
    "strength": [r"strength", r"weak"],
    "nerve": [r"nerve"],
    "product": [r"bottle", r"label", r"product", r"substance"],
}

TEST_TOPIC_DESCRIPTIONS = {
    "all_tests": "All recorded tests or checks when Alan explicitly asks broadly for every result.",
    "fluorescein": "Fluorescein or NaFl staining of the eye surface.",
    "leak": "A wound-fluid leak or Seidel check.",
    "eye_pressure": "Eye-pressure or tonometry measurement.",
    "blood_pressure": "Blood-pressure measurement.",
    "glucose": "Blood glucose or blood-sugar measurement.",
    "temperature": "Temperature or fever measurement.",
    "pulse": "Pulse or heart-rate measurement.",
    "oxygen": "Oxygen saturation measurement.",
    "breathing": "Airway or breathing observation.",
    "neurology": "Face, arm, speech, walking or other basic neurological screening.",
    "movement": "Movement or motility check.",
    "field": "Visual-field check.",
    "amsler": "Amsler-grid or distortion check.",
    "pinhole": "Pinhole vision check.",
    "refraction": "Lens, refraction or near-vision correction check.",
    "light_direction": "Light-direction or light-projection check.",
    "colour_vision": "Colour-vision check.",
    "photograph": "Photograph or image comparison.",
    "lump_character": "Tenderness, firmness, fixation or pulsation of a lump.",
    "saliva_duct": "Saliva or salivary-duct check.",
    "voice": "Spoken or whispered voice hearing check.",
    "weber": "Weber hearing test.",
    "rinne": "Rinne hearing test.",
    "bleeding": "Bleeding or contact-bleeding check.",
    "tracks": "Skin tracks or burrows check.",
    "burn_size": "Burn-size or body-surface-area measurement.",
    "dermoscopy": "Dermoscopy examination.",
    "biopsy": "Biopsy or histology test.",
    "sensation": "Sensation or touch check.",
    "strength": "Strength check.",
    "nerve": "Nerve-function check.",
    "product": "Product, bottle, label or substance identification.",
}

PRINT_LOCK = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def git_command(*arguments: str, binary: bool = False) -> str | bytes:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=not binary,
            encoding=None if binary else "utf-8",
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        stderr = getattr(exc, "stderr", b"" if binary else "")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        detail = str(stderr).strip() or str(exc)
        raise RuntimeError(f"Git command failed: git {' '.join(arguments)}: {detail}") from exc
    return completed.stdout


def normalise_github_url(value: str) -> str:
    cleaned = value.strip().replace("git@github.com:", "https://github.com/")
    return cleaned.removesuffix(".git").rstrip("/").lower()


def matching_prompt_release(prompt_bytes: bytes) -> tuple[str | None, str | None]:
    tags_output = str(git_command("tag", "--list", "v*", "--sort=-version:refname"))
    for tag in (line.strip() for line in tags_output.splitlines()):
        if not tag:
            continue
        try:
            tagged_prompt = git_command("show", f"{tag}:{ALAN_GIT_PROMPT_PATH}", binary=True)
        except RuntimeError:
            continue
        if tagged_prompt != prompt_bytes:
            continue
        tag_date = str(
            git_command(
                "for-each-ref",
                "--format=%(creatordate:iso-strict)",
                f"refs/tags/{tag}",
            )
        ).strip()
        return tag, tag_date or None
    return None, None


def resolve_alan_prompt_source(
    run_dir: Path,
    *,
    local_override: str | None,
    git_ref: str,
    refresh_github: bool,
) -> tuple[Path, dict[str, Any]]:
    """Freeze the exact Alan prompt used by this run and return its provenance."""
    inputs_dir = run_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    if local_override:
        source = Path(local_override).resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        snapshot = inputs_dir / "alan_compiled.local.txt"
        snapshot.write_bytes(source.read_bytes())
        modified = datetime.fromtimestamp(source.stat().st_mtime, tz=timezone.utc).isoformat()
        return snapshot, {
            "alan_source_type": "local_override",
            "alan_source": str(source),
            "alan_version": "LOCAL",
            "alan_version_date": modified,
            "alan_version_source": "Local override",
            "alan_git_ref": None,
            "alan_git_commit": None,
            "alan_git_path": None,
            "alan_prompt_snapshot": str(snapshot.relative_to(run_dir)),
            "alan_prompt_sha256": sha256_file(snapshot),
        }

    remote_url = str(git_command("remote", "get-url", "origin")).strip()
    if normalise_github_url(remote_url) != normalise_github_url(ALAN_GITHUB_URL):
        raise RuntimeError(
            f"origin is {remote_url!r}; expected the Alan GitHub repository {ALAN_GITHUB_URL!r}"
        )
    if refresh_github:
        git_command("fetch", "--quiet", "origin", "--tags")

    commit = str(git_command("rev-parse", f"{git_ref}^{{commit}}")).strip()
    prompt_bytes = git_command("show", f"{commit}:{ALAN_GIT_PROMPT_PATH}", binary=True)
    assert isinstance(prompt_bytes, bytes)
    snapshot = inputs_dir / "alan_compiled.github.txt"
    snapshot.write_bytes(prompt_bytes)

    release, release_date = matching_prompt_release(prompt_bytes)
    commit_date = str(git_command("show", "-s", "--format=%cI", commit)).strip()
    version = release or f"main@{commit[:8]}"
    version_date = release_date or commit_date or None
    return snapshot, {
        "alan_source_type": "github",
        "alan_source": ALAN_GITHUB_URL,
        "alan_version": version,
        "alan_version_date": version_date,
        "alan_version_source": "GitHub",
        "alan_git_ref": git_ref,
        "alan_git_commit": commit,
        "alan_git_path": ALAN_GIT_PROMPT_PATH,
        "alan_prompt_snapshot": str(snapshot.relative_to(run_dir)),
        "alan_prompt_sha256": sha256_file(snapshot),
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    for attempt in range(8):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 7:
                raise
            # Windows readers can briefly hold the destination file. Retrying
            # preserves the atomic replacement without losing live state.
            time.sleep(0.025 * (attempt + 1))


def freeze_file(source: Path, destination: Path) -> Path:
    """Copy one immutable run input and return its resolved snapshot path."""

    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source.read_bytes())
    return destination.resolve()


def matched_prompt_label(source: Path, pattern: str) -> str:
    """Return a content-matched candidate label without trusting a stale name."""

    source_hash = sha256_file(source)
    for candidate in sorted(source.parent.glob(pattern)):
        if candidate.is_file() and sha256_file(candidate) == source_hash:
            return candidate.stem
    return source.stem


def require_empty_run_dir(run_dir: Path) -> None:
    """Refuse to mix results or provenance from separate executions."""

    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError(
            f"Run directory is not empty: {run_dir}. Use a new --run-dir so saved results, "
            "prompts and model settings cannot be mixed."
        )
    run_dir.mkdir(parents=True, exist_ok=True)


def word_count(text: str) -> int:
    return scoring_word_count(text)


def worker_word_count(text: str) -> int:
    # HW numbers are patient facts, not Alan's numbered differentials.
    return scoring_word_count(text, strip_list_labels=False)


def worker_fact_coverage(
    offered: list[dict[str, str]],
    used_fact_ids: list[str],
) -> dict[str, Any]:
    """Record response coverage without turning an imperfect omission into a failure."""

    offered_ids = [str(item["id"]) for item in offered]
    used = [str(fact_id) for fact_id in used_fact_ids]
    used_set = set(used)
    omitted = [fact_id for fact_id in offered_ids if fact_id not in used_set]
    return {
        "offered_fact_ids": offered_ids,
        "used_fact_ids": used,
        "omitted_fact_ids": omitted,
        "complete": not omitted,
    }


def worker_fact_usage(
    visible_facts: list[dict[str, str]],
    used_fact_ids: list[str],
) -> dict[str, Any]:
    """Record which parts of the visible case view the HW actually expressed."""

    visible_ids = [str(item["id"]) for item in visible_facts]
    used = [str(fact_id) for fact_id in used_fact_ids]
    used_set = set(used)
    return {
        "visible_fact_ids": visible_ids,
        "used_fact_ids": used,
        "unused_fact_ids": [fact_id for fact_id in visible_ids if fact_id not in used_set],
    }


def row_dict(values: tuple[Any, ...], headers: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for header, value in zip(headers, values):
        if isinstance(value, str):
            value = value.strip()
        result[header] = value
    return result


def extract_rows(sheet: Any, max_col: int, start_row: int = 5) -> list[dict[str, Any]]:
    headers = [str(sheet.cell(start_row, col).value or "").strip() for col in range(1, max_col + 1)]
    if not headers[0] or len(headers) != len(set(headers)):
        raise ValueError(f"Invalid headers on {sheet.title}: {headers}")
    rows: list[dict[str, Any]] = []
    # Some source sheets omit Excel's optional dimension attribute. Read the
    # header row itself, then stream the extra columns with their matching row.
    all_headers = next(sheet.iter_rows(min_row=start_row, max_row=start_row, values_only=True))
    extra = {str(value or '').strip(): col for col, value in enumerate(all_headers) if col >= max_col}
    for values in sheet.iter_rows(min_row=start_row + 1, max_col=max(max_col, len(all_headers)), values_only=True):
        if values[0] in (None, ""):
            continue
        item = row_dict(values[:max_col], headers)
        # Evaluator-only metadata never becomes a health-worker fact.
        if 'Assessment type' in extra:
            kind = values[extra['Assessment type']]
            if kind:
                if kind != 'screening' or not {'Assessment objective', 'Assessment version'} <= extra.keys():
                    raise ValueError(f"Invalid assessment metadata for {item.get('Case')}")
                objective = values[extra['Assessment objective']]
                version = values[extra['Assessment version']]
                if not isinstance(objective, str) or not objective.strip() or not version:
                    raise ValueError(f"Incomplete assessment metadata for {item.get('Case')}")
                item['assessment'] = {'kind': kind, 'version': version, 'objective': objective}
        rows.append(item)
    return rows


def extract_stretches(sheet: Any) -> dict[str, dict[str, Any]]:
    """Read optional explicitly authored context without releasing future state."""
    extra_header = sheet.cell(5, 11).value
    if extra_header not in (None, "", "Unchanged facts"):
        raise ValueError(f"Unexpected stretch context header: {extra_header}")
    rows = extract_rows(sheet, 11 if extra_header else 10)
    for row in rows:
        raw = row.get("Unchanged facts")
        if raw in (None, ""):
            row.pop("Unchanged facts", None)
            continue
        try:
            context = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{row['Case']} invalid Unchanged facts JSON") from exc
        targets = {value.strip() for value in row["Target field(s)"].split(";")}
        if not isinstance(context, dict) or any(
            field not in targets or field in GOLD_FIELDS
            or not isinstance(value, str) or not value.strip()
            for field, value in context.items()
        ):
            raise ValueError(f"{row['Case']} invalid Unchanged facts mapping")
        row["Unchanged facts"] = context
    if len({row["Case"] for row in rows}) != len(rows):
        raise ValueError("Duplicate stretch cases")
    return {row["Case"]: row for row in rows}


def prepare_pilot(
    workbook_path: Path,
    output_path: Path = DEFAULT_CASES,
    selection_spec_path: Path = PILOT_IDS,
) -> dict[str, Any]:
    workbook_path = workbook_path.resolve()
    selection_spec_path = selection_spec_path.resolve()
    workbook_hash = sha256_file(workbook_path)
    if workbook_hash != WORKBOOK_EXPECTED_SHA256:
        raise ValueError(
            f"Workbook hash changed: expected {WORKBOOK_EXPECTED_SHA256}, got {workbook_hash}. "
            "Re-audit the workbook before preparing a new pilot."
        )

    workbook = load_workbook(workbook_path, read_only=True, data_only=False)
    try:
        all_cases: list[dict[str, Any]] = []
        for sheet_name, (domain, width) in CASE_SHEETS.items():
            for row in extract_rows(workbook[sheet_name], width):
                row = {"domain": domain, **row}
                all_cases.append(row)
        stretches = extract_stretches(workbook["Stretch Cases"])
        tags = {row["Case"]: row for row in extract_rows(workbook["Analysis Tags"], 6)}
    finally:
        workbook.close()

    if len(all_cases) != 200 or len({row["Case"] for row in all_cases}) != 200:
        raise ValueError("Expected 200 unique Alan 200 cases")

    selection_spec = json.loads(selection_spec_path.read_text(encoding="utf-8"))
    selected_ids = selection_spec["selection"]
    by_id = {row["Case"]: row for row in all_cases}
    missing = [case_id for case_id in selected_ids if case_id not in by_id]
    if missing:
        raise ValueError(f"Missing selected cases: {missing}")

    selected: list[dict[str, Any]] = []
    for sequence, case_id in enumerate(selected_ids, start=1):
        case = dict(by_id[case_id])
        case["pilot_sequence"] = sequence
        case["analysis"] = tags.get(case_id, {})
        case["stretch"] = stretches.get(case_id)
        selected.append(case)

    domain_counts = Counter(row["domain"] for row in selected)
    expected_counts = selection_spec["expected_domain_counts"]
    if dict(domain_counts) != expected_counts:
        raise ValueError(f"Domain split mismatch: {dict(domain_counts)} != {expected_counts}")
    stretch_count = sum(row["stretch"] is not None for row in selected)
    if stretch_count != selection_spec["expected_stretch_count"]:
        raise ValueError(f"Stretch count mismatch: {stretch_count}")

    for case in selected:
        required = {
            "Case",
            "Family code",
            "Diagnosis",
            "Management",
            "Urgency",
            "Expected marker",
            "First Line for Alan",
            RESOURCE_FIELD,
        }
        missing_fields = sorted(name for name in required if name not in case or case[name] in (None, ""))
        if missing_fields:
            raise ValueError(f"{case['Case']} missing required fields: {missing_fields}")
        marker = str(case["Expected marker"]).strip()
        marker_trigger = str(case.get("Marker trigger") or "").strip()
        if (marker == "None") != (marker_trigger == ""):
            raise ValueError(f"{case['Case']} marker reference is inconsistent")
        if case["stretch"]:
            valid_headers = set(case) - {"domain", "pilot_sequence", "analysis", "stretch"}
            targets = [part.strip() for part in case["stretch"]["Target field(s)"].split(";")]
            invalid = [target for target in targets if target not in valid_headers]
            if invalid:
                raise ValueError(f"{case['Case']} has invalid stretch targets: {invalid}")

    payload = {
        "format": "alan-dialogue-case-set-v3",
        "prepared_at": utc_now(),
        "source_workbook": str(workbook_path),
        "source_workbook_sha256": workbook_hash,
        "selection_spec": str(selection_spec_path),
        "selection_spec_sha256": sha256_file(selection_spec_path),
        "holdout_used": selection_spec.get("holdout_60_used"),
        "case_count": len(selected),
        "domain_counts": dict(domain_counts),
        "urgency_counts": dict(Counter(row["Urgency"] for row in selected)),
        "marker_counts": dict(Counter(row["Expected marker"] for row in selected)),
        "family_counts": dict(Counter(row["Family code"] for row in selected)),
        "stretch_count": stretch_count,
        "cases": selected,
    }
    write_json(output_path, payload)
    return payload


def normalise(text: str) -> str:
    text = text.lower().replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()


def request_matches(patterns: list[str], text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def test_fact_topics(text: str) -> set[str]:
    normalised = normalise(text)
    return {
        topic
        for topic, patterns in TEST_FACT_TOPICS.items()
        if request_matches(patterns, normalised)
    }


def allowed_test_topics() -> list[str]:
    missing = [topic for topic in TEST_FACT_TOPICS if topic not in TEST_TOPIC_DESCRIPTIONS]
    extra = [
        topic for topic in TEST_TOPIC_DESCRIPTIONS
        if topic != "all_tests" and topic not in TEST_FACT_TOPICS
    ]
    if missing or extra:
        raise CodexError(f"Test-topic catalogue mismatch: missing={missing}, extra={extra}")
    return list(TEST_TOPIC_DESCRIPTIONS)


def lexical_test_overlap(clause: str, request_text: str) -> bool:
    stop = {
        "a", "an", "and", "any", "are", "can", "check", "did", "do", "does", "for",
        "from", "has", "have", "how", "is", "it", "of", "on", "or", "please", "report",
        "result", "results", "show", "test", "tests", "the", "there", "this", "to", "was",
        "were", "what", "with", "you",
    }
    clause_terms = {term for term in re.findall(r"[a-z0-9]+", normalise(clause)) if len(term) > 2 and term not in stop}
    request_terms = {term for term in re.findall(r"[a-z0-9]+", normalise(request_text)) if len(term) > 2 and term not in stop}
    return bool(clause_terms & request_terms)


def clinical_content_terms(text: str) -> set[str]:
    """Return coarse terms for spotting facts already disclosed in the opening."""

    stop = {
        "a", "after", "again", "all", "and", "any", "at", "both", "but", "day",
        "days", "every", "for", "from", "good", "has", "have", "he", "her", "him",
        "his", "in", "is", "it", "job", "jobs", "no", "not", "now", "of", "on",
        "or", "she", "since", "the", "this", "to", "was", "with", "yday",
    }
    aliases = {
        "blinking": "blink",
        "blinks": "blink",
        "blurry": "blur",
        "blurred": "blur",
        "gritt": "grit",
        "gritty": "grit",
        "hurt": "pain",
        "hurts": "pain",
        "seeing": "vision",
        "sight": "vision",
    }
    terms: set[str] = set()
    for raw in re.findall(r"[a-z0-9]+", normalise(text)):
        token = aliases.get(raw, raw)
        if token not in stop and len(token) > 2:
            terms.add(token)
    return terms


def fact_repeats_opening(value: str, opening: str) -> bool:
    """True when a short patient fact substantially restates the opening."""

    fact_terms = clinical_content_terms(value)
    opening_terms = clinical_content_terms(opening)
    if len(fact_terms) < 2:
        return False
    overlap = fact_terms & opening_terms
    return len(overlap) >= 2 and len(overlap) / len(fact_terms) >= 0.6


def narrow_blood_pressure_glucose_clause(
    clause: str,
    clause_topics: set[str],
    requested_topics: set[str],
) -> str | None:
    if not {"blood_pressure", "glucose"}.issubset(clause_topics):
        return None
    wanted = requested_topics & {"blood_pressure", "glucose"}
    if len(wanted) != 1:
        return None
    status_match = re.search(r"\b(high|low|normal|raised)\b", clause, flags=re.IGNORECASE)
    if not status_match:
        return None
    status = status_match.group(1)
    if "blood_pressure" in wanted:
        return f"BP {status}"
    return f"blood sugar {status}"


def filter_requested_test_value(
    value: str,
    request_text: str,
    requested_topics: list[str] | None = None,
) -> str | None:
    """Return only the independently requested test result fragments.

    Test cells often contain several semicolon-separated results. Treating the whole
    cell as one fact lets the worker volunteer an unasked result, so the Case filter
    filters those fragments before the health-worker model sees them.
    """

    clauses = [clause.strip() for clause in value.split(";") if clause.strip()]
    if not clauses:
        return None

    if requested_topics is not None:
        topics = set(requested_topics)
        if "all_tests" in topics:
            return "; ".join(clauses[:MAX_WORKER_FACTS])
        selected: list[str] = []
        for clause in clauses:
            clause_topics = test_fact_topics(clause)
            shared_topics = clause_topics & topics
            if not shared_topics:
                continue
            if clause_topics <= topics:
                selected.append(clause)
            else:
                narrowed = narrow_blood_pressure_glucose_clause(clause, clause_topics, topics)
                if narrowed:
                    selected.append(narrowed)
            if len(selected) >= MAX_WORKER_FACTS:
                break
        return "; ".join(selected) if selected else None

    request = normalise(request_text)
    broad_request = bool(re.search(
        r"\b(?:all|any other|what|which) (?:test|tests|check|checks|result|results)\b"
        r"|\b(?:test|tests|check|checks|result|results) (?:show|available|done|were done)\b",
        request,
        flags=re.IGNORECASE,
    ))
    if broad_request:
        return "; ".join(clauses[:MAX_WORKER_FACTS])

    requested_topics = test_fact_topics(request)
    selected: list[str] = []
    for clause in clauses:
        clause_topics = test_fact_topics(clause)
        shared_topics = clause_topics & requested_topics
        if shared_topics:
            if clause_topics <= requested_topics:
                selected.append(clause)
            else:
                narrowed = narrow_blood_pressure_glucose_clause(clause, clause_topics, requested_topics)
                if narrowed:
                    selected.append(narrowed)
        elif not clause_topics and lexical_test_overlap(clause, request):
            selected.append(clause)
        if len(selected) >= MAX_WORKER_FACTS:
            break

    return "; ".join(selected) if selected else None


def actionable_request_text(alan_text: str) -> str:
    actionable: list[str] = []
    direct = re.compile(
        r"^(?:please\s+)?(?:ask|charge|recharge|replace|swap|restore|check|compare|confirm|cover|describe|dry-wick|evert|examine|find|inspect|look|measure|recheck|repeat|test|tell|turn|use)\b"
        r"|^(?:after|before)\b[^,;]{0,100}[,;]\s*(?:please\s+)?"
        r"(?:ask|charge|recharge|replace|swap|restore|check|compare|confirm|cover|describe|dry-wick|evert|examine|find|inspect|look|measure|recheck|repeat|test|tell|turn|use)\b"
        r"|\b(?:can|could|would|will) you\b",
        flags=re.IGNORECASE,
    )
    for line in alan_text.splitlines():
        for segment in re.split(r"(?:[!?]|\.(?!\d))(?:[_*]*)\s*|:\s+", line):
            stripped = segment.strip(" -*_\t")
            if stripped and direct.search(stripped):
                actionable.append(stripped)
        remainder = line.strip()
        while "?" in remainder:
            candidate, remainder = remainder.split("?", 1)
            candidate = re.split(r"(?:!|\.(?!\d))(?:[_*]*)\s*|:\s+", candidate)[-1].strip()
            if candidate:
                actionable.append(candidate + "?")
    return " ".join(dict.fromkeys(actionable))


def stretch_triggered(stretch: dict[str, Any], alan_text: str) -> bool:
    """Release a revised finding only after the authored information-gathering action.

    The registered topics describe actions, never the hidden result. Questions
    and direct requests qualify; discussion and negated requests do not.
    """
    topic = normalise(str(stretch.get("Topic", "")))
    request = actionable_request_text(alan_text)
    request = re.sub(r"\b(?:do not|don't|never|no need to)\b[^.!?;]*", "", request, flags=re.I)
    request = normalise(request)
    if not request:
        return False

    def has(pattern: str) -> bool:
        return bool(re.search(pattern, request))

    close = has(r"\b(?:magnif\w*|closely|carefully|in detail)\b")
    timing = has(r"\b(?:when|how long|duration|began|begin|start\w*|first|since|date)\b")
    if topic == "ulcer edge and lashes":
        # A broad lash check must first receive the authored uncertain state.
        edge_check = has(r"\bedges?\b") and has(r"\b(?:inspect|examine|look|rolled|pearly|irregular)\b")
        return edge_check or (close and has(r"\b(?:lashes|lash|ulcer\w*)\b"))
    if topic == "nail appearance":
        return has(r"\bnails?\b") and (close or has(r"\b(?:pits|pitting|lifting)\b"))
    if topic == "source of old drops":
        return has(r"\b(?:source|origin|where|whose|borrow\w*|prescrib\w*)\b") and has(r"\b(?:drops?|medicine|patient|family|bottle)\b")
    if topic == "affected eye":
        return ((has(r"\b(?:which|confirm|verify|recall|remember)\b")
                 or has(r"\bone\b.*\bboth\b|\bleft\b.*\bright\b"))
                and has(r"\b(?:eyes?|side)\b")
                and has(r"\b(?:episode|earlier|went|lost|loss|dark|black|during|before|was|were|previously)\b"))
    if topic == "shoulders and weight":
        return has(r"\bshoulders?\b") and has(r"\bweight\b")
    if topic == "under upper lid":
        return has(r"\b(?:evert\w*|turn|lift|pull|look under|check under)\b") and has(r"\blids?\b")
    if topic == "when shine began":
        return timing and has(r"\b(?:separately|individually|each)\b") and has(r"\b(?:caregivers?|parents?|mother|father)\b")
    if topic == "steroid duration":
        return timing and has(r"\bsteroids?\b")
    if topic == "how pressure was checked":
        return has(r"\b(?:pressure|iop)\b") and has(r"\b(?:how|tool|instrument|method|tonometer|measur\w*)\b")
    if topic == "remote photo report":
        return has(r"\breport\b") and has(r"\b(?:status|check|received|ready|arriv\w*|available|back)\b")
    if topic == "back-eye view":
        return has(r"\b(?:power|batter\w*|(?:re)?charg\w*|spare|backup)\b") and has(r"\b(?:fundus|fundal|retina\w*|back of (?:the )?eye)\b")
    if topic == "top of drum":
        return has(r"\b(?:dry.?wick|wick\w*|dry mop)\b") and has(r"\b(?:top|upper|attic)\b") and has(r"\b(?:recheck|inspect|look|examine|check)\b")
    if topic == "hearing between spells":
        return has(r"\bhearing\b") and has(r"\bbetween\b") and has(r"\b(?:attacks?|spells?|episodes?)\b")
    if topic == "pregnancy illness":
        return has(r"\bmother\b") and has(r"\bgrandmother\b") and has(r"\b(?:separately|individually|each)\b") and has(r"\b(?:pregnancy|pregnant)\b")
    if topic == "palate view":
        return has(r"\bpalate\b") and has(r"\b(?:light|lit|torch)\b") and has(r"\b(?:direct|check|look|inspect|examine)\b")
    if topic == "relation to meals":
        return has(r"\b(?:meals?|eat\w*|food|chew\w*)\b") or (has(r"\b(?:before|brings? on|triggers?)\b") and has(r"\bswell\w*\b"))
    if topic == "entry site":
        return has(r"\b(?:inspect|examine|look|check)\b") and has(r"\b(?:thorns?|bites?|cracks?|toe webs?|entry|breaks?)\b")
    if topic == "itch duration":
        return timing and has(r"\bitch\w*\b")
    if topic == "pain versus skin-break timing":
        return timing and has(r"\bpain\b") and has(r"\b(?:skin|break\w*|wound|ulcer\w*)\b") and has(r"\b(?:separat\w*|each|both|versus|before|after)\b")
    if topic == "biopsy date":
        return timing and has(r"\b(?:biopsy|sample)\b") and has(r"\b(?:sent|send|taken|collected|date|when)\b")

    # Compatibility for older authored topics outside the qualification set.
    trigger = normalise(str(stretch.get("Change when", "")))
    stop = {"asks", "ask", "worker", "patient", "the", "a", "an", "to", "and", "or", "with", "what",
            "when", "how", "whether", "about", "again", "carefully", "check", "checks", "look", "looks"}
    trigger_terms = {token for token in re.findall(r"[a-z0-9]+", trigger) if len(token) > 2 and token not in stop}
    overlap = trigger_terms & set(re.findall(r"[a-z0-9]+", request))
    return len(overlap) >= 2 or (len(trigger_terms) == 1 and bool(overlap))


def stretch_topic_requested(stretch: dict[str, Any], alan_text: str) -> bool:
    text = normalise(alan_text)
    topic = normalise(str(stretch.get("Topic", "")))

    if "upper lid" in topic:
        return "lid" in text and bool(re.search(
            r"\b(?:upper|under|evert|turn|lift|pull|speck|foreign body|fixed|loose|embedded)\b",
            text,
        ))
    if "meal" in topic:
        return bool(re.search(r"\b(?:meals?|eat(?:ing)?|food|chew(?:ing)?)\b", text))

    stop = {
        "a", "an", "and", "about", "check", "checked", "does", "field", "fields", "for",
        "from", "how", "is", "it", "of", "on", "or", "patient", "relation", "report",
        "the", "to", "was", "what", "when", "whether", "with", "worker",
    }
    topic_terms = {token for token in re.findall(r"[a-z0-9]+", topic) if len(token) > 2 and token not in stop}
    text_terms = set(re.findall(r"[a-z0-9]+", text))
    return bool(topic_terms & text_terms)


@dataclass
class WorkerReply:
    reply: str
    requested_fields: list[str]
    offered: list[dict[str, str]]
    state_transition: str | None
    fallback_release: bool
    response_reason: str

    @property
    def released(self) -> list[dict[str, str]]:
        """Compatibility view used by deterministic unit tests."""
        return [{"field": item["field"], "value": item["value"]} for item in self.offered]


def fact_field_slug(field: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalise(field)).strip("-")


def atomic_facts(field: str, value: str, state_label: str | None = None) -> list[dict[str, str]]:
    clauses = [part.strip() for part in re.split(r"\s*;\s*", value) if part.strip()]
    suffix = f"-{state_label}" if state_label else ""
    return [
        {
            "id": f"{fact_field_slug(field)}{suffix}#{index}",
            "field": field,
            "value": clause,
        }
        for index, clause in enumerate(clauses, start=1)
    ]


class CaseFilter:
    """Expose the complete non-gold case view without interpreting Alan's wording.

    The health-worker model, not this class, decides which visible facts answer
    Alan. Authored stretch states change after the recorded enquiry or examination.
    Authored challenge facts change only at their scheduled driver injection.
    Gold fields and raw stretch targets are never exposed.
    """

    def __init__(self, case: dict[str, Any]) -> None:
        self.case = dict(case)
        self.domain = str(case["domain"])
        self.stretch = case.get("stretch")
        self.state = "start" if self.stretch else None
        self.transition_done = False
        self.terminal_resource_checked = False
        self.injection_applied = False

    def apply_injected_state(self) -> None:
        """Activate authored clinical changes at the driver's recorded injection."""
        updated = (self.case.get('extra_test') or {}).get('facts_after_injection')
        if not updated or self.injection_applied:
            return
        allowed = set(PATIENT_FIELDS + CHECK_FIELDS[self.domain] + [RESOURCE_FIELD])
        if not isinstance(updated, dict) or not set(updated) <= allowed:
            raise ValueError('Injected fact bank contains non-patient fields')
        if any(not isinstance(v, str) or not v.strip() for v in updated.values()):
            raise ValueError('Injected facts must be non-empty text')
        # Both banks are complete states: never carry an earlier normal finding
        # into the new state merely because its field was omitted.
        for field in allowed:
            self.case.pop(field, None)
        self.case.update(updated)
        self.injection_applied = True

    @property
    def target_fields(self) -> set[str]:
        if not self.stretch:
            return set()
        return {
            part.strip()
            for part in str(self.stretch["Target field(s)"]).split(";")
            if part.strip()
        }

    def visible_facts(self) -> list[dict[str, str]]:
        facts: list[dict[str, str]] = []
        ordered_fields = PATIENT_FIELDS + CHECK_FIELDS[self.domain] + [RESOURCE_FIELD]
        for field in ordered_fields:
            if field in GOLD_FIELDS or field in self.target_fields:
                continue
            value = self.case.get(field)
            if value not in (None, ""):
                facts.extend(atomic_facts(field, str(value)))

        if self.stretch:
            # Case authors may retain unchanged findings from a replaced field.
            # Never infer them from the hidden future state or the gold labels.
            for field, value in self.stretch.get("Unchanged facts", {}).items():
                if field not in self.target_fields or field not in ordered_fields or field in GOLD_FIELDS:
                    raise ValueError(f"Invalid unchanged stretch field: {field}")
                facts.extend(atomic_facts(field, str(value)))
            state_key = "Updated (hidden)" if self.state == "updated" else "Start (hidden)"
            state_label = "updated" if self.state == "updated" else "start"
            facts.extend(atomic_facts("active_state", str(self.stretch[state_key]), state_label))
        if self.injection_applied:
            facts = [{**fact, "id": "injected-" + fact["id"]} for fact in facts]
        return facts

    def view_for_turn(self, alan_text: str) -> WorkerReply:
        transition: str | None = None
        if (
            self.stretch
            and not self.transition_done
            and stretch_triggered(self.stretch, alan_text)
        ):
            self.state = "updated"
            self.transition_done = True
            transition = str(self.case["Case"])
        return WorkerReply(
            reply="",
            requested_fields=[],
            offered=self.visible_facts(),
            state_transition=transition,
            fallback_release=False,
            response_reason="visible_case_view",
        )

    def terminal_resource_reply(self, alan_text: str) -> WorkerReply | None:
        if self.terminal_resource_checked:
            return None
        # Offer all authorised resource clauses. The two-fact limit applies to
        # the spoken answer, not the bank: a later clause may be the barrier.
        facts = [fact for fact in self.visible_facts() if fact["field"] == RESOURCE_FIELD]
        context = "; ".join(fact["value"] for fact in facts)
        if not resource_context_relevant(alan_text, context):
            return None
        self.terminal_resource_checked = True
        return WorkerReply(
            reply="",
            requested_fields=[RESOURCE_FIELD],
            offered=facts,
            state_transition=None,
            fallback_release=False,
            response_reason="terminal_resource_check",
        )


def select_worker_facts(items: list[dict[str, str]], request_text: str = "") -> list[dict[str, str]]:
    """Keep a human-sized answer while favouring the requested examination and active state."""

    check_fields = {field for fields in CHECK_FIELDS.values() for field in fields}

    def priority(item: dict[str, str]) -> int:
        field = item["field"]
        if field == "active_state":
            return 0
        if field in check_fields:
            return 1
        if field in {"Age", "Sex", "Duration"}:
            return 2
        if field == "Symptoms":
            return 3
        if field == "History":
            return 4
        if field == RESOURCE_FIELD:
            return 5
        return 6

    request_terms = {
        token for token in re.findall(r"[a-z0-9]+", normalise(request_text))
        if len(token) > 2
    }

    def relevance(item: dict[str, str]) -> int:
        value_terms = set(re.findall(r"[a-z0-9]+", normalise(item["value"])))
        return len(request_terms & value_terms)

    ranked = sorted(
        enumerate(items),
        key=lambda pair: (priority(pair[1]), -relevance(pair[1]), pair[0]),
    )
    chosen_indexes = {index for index, _ in ranked[:MAX_WORKER_FACTS]}
    return [item for index, item in enumerate(items) if index in chosen_indexes]


class DeterministicWorker:
    def __init__(self, case: dict[str, Any]) -> None:
        self.case = case
        self.opening = str(case.get("First Line for Alan", ""))
        self.domain = case["domain"]
        self.stretch = case.get("stretch")
        self.state = "start" if self.stretch else None
        self.disclosed_fact_ids: set[str] = set()
        self.transition_done = False
        self.unanswered_checks: Counter[str] = Counter()
        self.terminal_resource_checked = False

    @property
    def target_fields(self) -> set[str]:
        if not self.stretch:
            return set()
        return {part.strip() for part in self.stretch["Target field(s)"].split(";")}

    def _requested_fields(self, alan_text: str) -> list[str]:
        text = normalise(alan_text)
        ordered = PATIENT_FIELDS + CHECK_FIELDS[self.domain] + [RESOURCE_FIELD]
        matches: set[str] = set()
        for field, patterns in COMMON_ALIASES.items():
            if request_matches(patterns, text):
                matches.add(field)
        for field, patterns in DOMAIN_ALIASES[self.domain].items():
            if request_matches(patterns, text):
                matches.add(field)
        return [field for field in ordered if field in matches]

    def _fallback_field(self) -> str | None:
        ordered = PATIENT_FIELDS + CHECK_FIELDS[self.domain]
        for field in ordered:
            value = str(self.case.get(field, ""))
            facts = atomic_facts(field, value) if value else []
            if field not in self.target_fields and any(
                item["id"] not in self.disclosed_fact_ids for item in facts
            ):
                return field
        return None

    def commit_disclosure(self, used_fact_ids: list[str]) -> None:
        self.disclosed_fact_ids.update(used_fact_ids)

    def terminal_resource_reply(self, alan_text: str) -> WorkerReply | None:
        if self.terminal_resource_checked:
            return None
        self.terminal_resource_checked = True
        context = str(self.case.get(RESOURCE_FIELD, "")).strip()
        if not resource_context_relevant(alan_text, context):
            return None
        offered = [
            item for item in atomic_facts(RESOURCE_FIELD, context)
            if item["id"] not in self.disclosed_fact_ids
        ][:MAX_WORKER_FACTS]
        if not offered:
            return None
        return WorkerReply(
            reply="",
            requested_fields=[RESOURCE_FIELD],
            offered=offered,
            state_transition=None,
            fallback_release=False,
            response_reason="facts_supplied",
        )

    def _no_answer_reason(self, request_text: str, requested: list[str]) -> str:
        difficult = bool(re.search(
            r"\b(?:rapd|hypopyon|stensen|wharton|duct|fundus|fundal|embedded)\b",
            request_text,
            flags=re.IGNORECASE,
        ))
        check_like = bool(re.search(
            r"\b(?:check|look|inspect|compare|evert|test|palpate|loose|fixed|embedded)\b"
            r"|\bswing\b.{0,40}\blight\b|\bpupil\b.{0,40}\b(?:light|enlarge)\b",
            request_text,
            flags=re.IGNORECASE,
        ))
        if difficult and not re.search(r"\b(?:simple|means?|meaning|under tongue|inside cheek)\b", request_text, flags=re.IGNORECASE):
            return "term_unclear"
        if check_like:
            if re.search(
                r"\bswing\b.{0,40}\blight\b|\bpupil\b.{0,40}\b(?:light|enlarge)\b",
                request_text,
                flags=re.IGNORECASE,
            ):
                return "checked_unclear"
            key = "|".join(requested) or fact_field_slug(request_text)[:40]
            self.unanswered_checks[key] += 1
            return "not_checked" if self.unanswered_checks[key] == 1 else "checked_unclear"
        return "not_recorded"

    def respond(
        self,
        alan_text: str,
        interpreted_fields: list[str] | None = None,
        interpreted_test_topics: list[str] | None = None,
        repeat_requested: bool | None = None,
    ) -> WorkerReply:
        request_text = actionable_request_text(alan_text)
        if interpreted_fields is None:
            requested = self._requested_fields(request_text) if request_text else []
        else:
            if not isinstance(interpreted_fields, list) or not all(
                isinstance(field, str) for field in interpreted_fields
            ):
                raise CodexError("Interpreted request fields must be a list of strings")
            if len(interpreted_fields) != len(set(interpreted_fields)):
                raise CodexError("Interpreted request fields contain duplicates")
            allowed = PATIENT_FIELDS + CHECK_FIELDS[self.domain] + [RESOURCE_FIELD]
            unknown = [field for field in interpreted_fields if field not in allowed]
            if unknown:
                raise CodexError(f"Interpreted request contains forbidden fields: {unknown}")
            requested = [field for field in allowed if field in interpreted_fields]
            if requested and not request_text:
                request_text = alan_text.strip()
        if interpreted_test_topics is not None:
            if not isinstance(interpreted_test_topics, list) or not all(
                isinstance(topic, str) for topic in interpreted_test_topics
            ):
                raise CodexError("Interpreted test topics must be a list of strings")
            if len(interpreted_test_topics) != len(set(interpreted_test_topics)):
                raise CodexError("Interpreted test topics contain duplicates")
            unknown_topics = [
                topic for topic in interpreted_test_topics
                if topic not in allowed_test_topics()
            ]
            if unknown_topics:
                raise CodexError(f"Interpreted request contains forbidden test topics: {unknown_topics}")
            if interpreted_test_topics and "Tests" not in requested:
                raise CodexError("Interpreted test topics require the Tests field")
            if "all_tests" in interpreted_test_topics and len(interpreted_test_topics) != 1:
                raise CodexError("all_tests cannot be combined with a specific test topic")
        if repeat_requested is None:
            explicit_repeat = bool(re.search(
                r"\b(?:again|once more|recheck|re-check|remeasure|re-measure|repeat)\b",
                request_text,
                flags=re.IGNORECASE,
            ))
        elif isinstance(repeat_requested, bool):
            explicit_repeat = repeat_requested
        else:
            raise CodexError("Interpreted repeat flag must be true or false")
        fallback = False
        transition: str | None = None

        if self.stretch and request_text and not self.transition_done and stretch_triggered(self.stretch, request_text):
            self.state = "updated"
            self.transition_done = True
            transition = self.case["Case"]

        target_requested = bool(set(requested) & self.target_fields)
        state_requested = bool(
            self.stretch
            and target_requested
            and stretch_topic_requested(self.stretch, request_text)
        )
        requested = [field for field in requested if field not in self.target_fields]

        broad_request = bool(
            re.search(
                r"\b(?:tell me more|more details|anything else about|other history)\b",
                request_text,
                flags=re.IGNORECASE,
            )
        )
        if not requested and not target_requested and transition is None and broad_request:
            field = self._fallback_field()
            if field:
                requested = [field]
                fallback = True

        offered: list[dict[str, str]] = []
        for field in requested:
            if field in GOLD_FIELDS or field not in self.case:
                continue
            value = self.case.get(field)
            if value not in (None, ""):
                released_value = str(value)
                if field == "Tests":
                    released_value = filter_requested_test_value(
                        released_value,
                        request_text,
                        interpreted_test_topics,
                    ) or ""
                if field == "Symptoms" and fact_repeats_opening(released_value, self.opening):
                    released_value = ""
                for item in atomic_facts(field, released_value):
                    if explicit_repeat or item["id"] not in self.disclosed_fact_ids:
                        offered.append(item)

        if self.stretch and (state_requested or transition is not None):
            state_key = "Updated (hidden)" if self.state == "updated" else "Start (hidden)"
            state_value = str(self.stretch[state_key])
            state_label = "updated" if self.state == "updated" else "start"
            for item in atomic_facts("active_state", state_value, state_label):
                if explicit_repeat or item["id"] not in self.disclosed_fact_ids:
                    offered.append(item)

        offered = select_worker_facts(offered, request_text)

        response_reason = "facts_supplied" if offered else self._no_answer_reason(request_text, requested)
        if not offered:
            if request_text:
                reply = "Not recorded."
            elif has_primary_diagnosis(alan_text):
                reply = "ok"
            elif re.search(r"\b(?:emergency|urgent|transfer|refer|hospital|send .* now)\b", alan_text, flags=re.IGNORECASE):
                reply = "ok"
            elif re.search(
                r"\b(?:do not|don't|avoid|remove|lift|irrigate|rinse|apply|use|give|start|stop|keep|shield|cover|review|arrange)\b",
                alan_text,
                flags=re.IGNORECASE,
            ):
                reply = "ok"
            else:
                reply = "say again pls"
        else:
            reply = ""

        return WorkerReply(
            reply=reply,
            requested_fields=requested + (sorted(self.target_fields) if target_requested else []),
            offered=offered,
            state_transition=transition,
            fallback_release=fallback,
            response_reason=response_reason,
        )


def has_primary_diagnosis(text: str) -> bool:
    # Keep stop detection and score reporting on the same tested definition.
    return scoring_has_primary_diagnosis(text)


def has_emergency_exit_diagnosis(text: str) -> bool:
    # Keep the emergency-only score definition directly unit-testable here.
    return scoring_has_emergency_exit_diagnosis(text)


def has_substantive_question(text: str) -> bool:
    cleaned = re.sub(
        r"\b(?:any questions|do you have any questions|anything else|does that make sense)(?:\s+about[^?]*)?\?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return question_count(cleaned) > 0


def has_final_closing(text: str) -> bool:
    return scoring_has_terminal_closing(text)


def has_emergency_exit_closing(text: str) -> bool:
    return scoring_has_emergency_exit_closing(text)


def should_stop(
    alan_text: str,
    turn: int,
    expected_emergency_exit: bool | None = None,
) -> tuple[bool, str]:
    """Apply the route declared by the frozen case, never infer it clinically."""

    if expected_emergency_exit is False and has_emergency_exit_closing(alan_text):
        return True, "wrong_route_terminal"
    if (
        expected_emergency_exit is not False
        and has_emergency_exit_closing(alan_text)
        and not has_substantive_question(alan_text)
    ):
        return True, "terminal_emergency_exit"
    if has_final_closing(alan_text):
        return True, "terminal_closing"
    if expected_emergency_exit is True:
        if turn >= MAX_TURNS:
            return True, "hard_cap"
        return False, "emergency_exit_incomplete"
    if turn < MIN_TURNS:
        return False, "minimum_turns"
    if has_primary_diagnosis(alan_text) and not has_substantive_question(alan_text):
        return True, "terminal_primary_diagnosis"
    if turn >= MAX_TURNS:
        return True, "hard_cap"
    return False, "continue"


def should_check_terminal_resource(stop: bool, stop_reason: str, alan_text: str, turn: int) -> bool:
    """Allow one resource objection only when Step 5 lacks Alan's explicit closing."""

    return bool(
        stop
        and stop_reason == "terminal_primary_diagnosis"
        and turn < MAX_TURNS
        and has_primary_diagnosis(alan_text)
    )


def resource_context_relevant(alan_text: str, context: str) -> bool:
    text = normalise(alan_text)
    resource = normalise(context)
    if not resource or resource == "no special constraint":
        return False
    referral_plan = bool(re.search(r"\b(?:refer|referral|transfer|hospital|clinic|specialist|surgery|outreach)\b", text))
    urgent_plan = bool(re.search(r"\b(?:now|today|urgent|emergency|immediate|transfer)\b", text))
    urgent_access_barrier = bool(re.search(
        r"\b(?:no ambulance|transport (?:difficult|unavailable)|distant|far|(?:one|two|three|four|five|six|\d+) hours?|escort required|"
        r"requires an escort|no specialist|no local (?:hospital|service|theatre))\b",
        resource,
    ))
    if referral_plan and urgent_plan and urgent_access_barrier:
        return True
    if "private" in text and re.search(r"\b(?:cannot afford|cant afford|can't afford|private)\b", resource):
        return True
    named_resources = {
        "oct", "slit lamp", "culture", "biopsy", "ultrasound", "tonometer", "imaging",
        "ambulance", "antiviral", "antibiotic", "drops", "glasses", "refraction",
    }
    for term in named_resources:
        if term not in text or term not in resource:
            continue
        unavailable = re.search(
            rf"\b(?:no|without)\b[^.;]{{0,28}}\b{re.escape(term)}\b|"
            rf"\b{re.escape(term)}\b[^.;]{{0,20}}\b(?:unavailable|uncertain|not stocked)\b",
            resource,
        )
        if unavailable:
            return True
    return False


class CodexError(RuntimeError):
    pass


class RunStopped(CodexError):
    pass


def stop_requested(run_dir: Path) -> bool:
    return (run_dir / "STOP_REQUESTED").exists()


def safe_capacity_failure(stdout: str) -> bool:
    """Retry only explicit capacity rejection with no generated item or completed turn."""
    events = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    if any(e.get("type") in {"turn.completed", "item.started", "item.updated", "item.completed"} for e in events):
        return False
    return any(e.get("type") in {"error", "turn.failed"} and
               "at capacity" in json.dumps(e).lower() for e in events)


class CodexInvoker:
    @staticmethod
    def isolation_arguments() -> list[str]:
        # --ignore-rules concerns execpolicy, not AGENTS.md. Apply this on
        # every call, including resume, so project text cannot enter the case.
        return ["--config", "project_doc_max_bytes=0"]

    def __init__(self, model: str, reasoning: str, timeout: int, retries: int) -> None:
        self.model = model
        self.reasoning = reasoning
        self.timeout = timeout
        self.retries = retries
        self.codex = shutil.which("codex.cmd") or shutil.which("codex")
        if not self.codex:
            raise CodexError("Could not find codex or codex.cmd on PATH")

    def _run(
        self,
        arguments: list[str],
        input_text: str,
        call_dir: Path,
        retries: int | None = None,
    ) -> dict[str, Any]:
        call_dir.mkdir(parents=True, exist_ok=True)
        write_json(call_dir / "invocation.json", {
            "arguments": arguments,
            "user_message": input_text,
            "input_isolation": "no-project-instructions-v1",
        })
        last_path = call_dir / "last.txt"
        started = time.perf_counter()
        last_error = ""
        retry_count = self.retries if retries is None else retries
        capacity_retries = 0
        for attempt in range(retry_count + 4):
            if last_path.exists():
                last_path.unlink()
            command = [self.codex, *arguments, "--output-last-message", str(last_path), "-"]
            try:
                completed = subprocess.run(
                    command,
                    input=input_text,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.timeout,
                    check=False,
                    cwd=str(call_dir),
                    env=os.environ.copy(),
                )
            except subprocess.TimeoutExpired as exc:
                last_error = f"timeout after {self.timeout}s: {exc}"
                def timeout_text(value):
                    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""
                (call_dir / f"events_attempt_{attempt + 1}.jsonl").write_text(timeout_text(exc.stdout), encoding="utf-8", newline="\n")
                (call_dir / f"stderr_attempt_{attempt + 1}.log").write_text(timeout_text(exc.stderr), encoding="utf-8", newline="\n")
                write_json(call_dir / f"timeout_attempt_{attempt + 1}.json", {"error": last_error, "timeout_seconds": self.timeout})
                if attempt >= retry_count:
                    break
                continue

            (call_dir / f"events_attempt_{attempt + 1}.jsonl").write_text(completed.stdout, encoding="utf-8", newline="\n")
            (call_dir / f"stderr_attempt_{attempt + 1}.log").write_text(completed.stderr, encoding="utf-8", newline="\n")
            reply = last_path.read_text(encoding="utf-8").strip() if last_path.exists() else ""
            if completed.returncode == 0 and reply:
                events = []
                for line in completed.stdout.splitlines():
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                thread_id = next((event.get("thread_id") for event in events if event.get("type") == "thread.started"), None)
                usage = next((event.get("usage", {}) for event in reversed(events) if event.get("type") == "turn.completed"), {})
                return {
                    "reply": reply,
                    "thread_id": thread_id,
                    "usage": usage,
                    "duration_ms": round((time.perf_counter() - started) * 1000),
                    "attempts": attempt + 1,
                }
            last_error = f"exit={completed.returncode}; stderr={completed.stderr[-1200:]}"
            if safe_capacity_failure(completed.stdout) and not reply and capacity_retries < 3:
                delay = (5, 15, 30)[capacity_retries]
                capacity_retries += 1
                last_error = "Selected model is at capacity"
                write_json(call_dir / f"capacity_retry_{capacity_retries}.json",
                           {"attempt": attempt + 1, "delay_seconds": delay, "reason": last_error})
                time.sleep(delay)
                continue
            if attempt >= retry_count:
                break
        raise CodexError(last_error or "Codex call failed")

    def new_session(
        self,
        instructions_path: Path,
        user_message: str,
        call_dir: Path,
        output_schema: Path | None = None,
        ephemeral: bool = False,
    ) -> dict[str, Any]:
        instruction_config = f'model_instructions_file="{instructions_path.resolve().as_posix()}"'
        arguments = [
            "exec",
            "--model", self.model,
            "--config", f'model_reasoning_effort="{self.reasoning}"',
            "--config", instruction_config,
            *self.isolation_arguments(),
            "--config", 'web_search="disabled"',
            "--ignore-user-config",
            "--ignore-rules",
            "--sandbox", "read-only",
            "--disable", "memories",
            "--disable", "apps",
            "--disable", "browser_use",
            "--disable", "browser_use_external",
            "--disable", "computer_use",
            "--disable", "image_generation",
            "--disable", "plugins",
            "--disable", "shell_tool",
            "--disable", "standalone_web_search",
            "--disable", "tool_suggest",
            "--skip-git-repo-check",
            "--cd", str(call_dir.resolve()),
            "--json",
        ]
        if output_schema:
            arguments.extend(["--output-schema", str(output_schema.resolve())])
        if ephemeral:
            arguments.append("--ephemeral")
        return self._run(arguments, user_message, call_dir)

    def resume(self, thread_id: str, user_message: str, call_dir: Path) -> dict[str, Any]:
        arguments = [
            "exec", "resume",
            "--model", self.model,
            "--config", f'model_reasoning_effort="{self.reasoning}"',
            *self.isolation_arguments(),
            "--config", 'web_search="disabled"',
            "--ignore-user-config",
            "--ignore-rules",
            "--disable", "memories",
            "--disable", "apps",
            "--disable", "browser_use",
            "--disable", "browser_use_external",
            "--disable", "computer_use",
            "--disable", "image_generation",
            "--disable", "plugins",
            "--disable", "shell_tool",
            "--disable", "standalone_web_search",
            "--disable", "tool_suggest",
            "--skip-git-repo-check",
            "--json",
            thread_id,
        ]
        # A timed-out resume may already have appended the message remotely.
        # Re-sending it can corrupt the hidden thread while the saved transcript
        # records only one copy, so continuation calls are never auto-retried.
        return self._run(arguments, user_message, call_dir, retries=0)


def allowed_request_fields(domain: str) -> list[str]:
    if domain not in CHECK_FIELDS:
        raise CodexError(f"Unknown health-worker interpretation domain: {domain}")
    ordered = PATIENT_FIELDS + CHECK_FIELDS[domain] + [RESOURCE_FIELD]
    missing_descriptions = [field for field in ordered if field not in REQUEST_FIELD_DESCRIPTIONS]
    if missing_descriptions:
        raise CodexError(f"Request fields have no descriptions: {missing_descriptions}")
    return ordered


def health_worker_interpretation_payload(alan_text: str, domain: str) -> str:
    """Build the value-free request-understanding input for the Terra HW."""
    payload = {
        "contract_version": "health-worker-interpretation-v3",
        "domain": domain,
        "alan_message": alan_text,
        "allowed_fields": [
            {
                "name": field,
                "meaning": REQUEST_FIELD_DESCRIPTIONS[field],
            }
            for field in allowed_request_fields(domain)
        ],
        "allowed_test_topics": [
            {
                "name": topic,
                "meaning": TEST_TOPIC_DESCRIPTIONS[topic],
            }
            for topic in allowed_test_topics()
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def health_worker_payload(
    alan_text: str,
    visible_facts: list[dict[str, str]],
    voice_sample: str,
    recent_dialogue: list[dict[str, str]] | None = None,
    rejected_reply: str | None = None,
    rejection_reasons: list[str] | None = None,
    clarification_context: str | None = None,
) -> str:
    payload: dict[str, Any] = {
        "contract_version": "direct-health-worker-v1",
        "alan_message": alan_text,
        "recent_dialogue": (recent_dialogue or [])[-6:],
        "voice_sample": voice_sample,
        "visible_facts": [
            {
                "id": item["id"],
                "field": FIELD_LABELS.get(item["field"], item["field"]),
                "value": item["value"],
            }
            for item in visible_facts
        ],
        "reply_limit_words": MAX_WORKER_WORDS,
        "reply_limit_facts": MAX_WORKER_FACTS,
    }
    if clarification_context:
        payload["clarification_context"] = clarification_context
    if rejected_reply is not None:
        payload["previous_reply_rejected"] = rejected_reply
        payload["fix"] = rejection_reasons or ["Follow the worker rules exactly"]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def health_worker_style_warnings(
    reply: str,
    previous_worker_replies: list[str] | None = None,
) -> list[str]:
    """Return non-blocking voice and presentation warnings.

    These warnings are useful for later worker-model qualification, but they
    must not turn a factually safe paraphrase into a runner failure.
    """
    warnings: list[str] = []
    clean = reply.strip()
    if "\n" in clean or "\r" in clean:
        warnings.append("reply is not one line")
    if worker_word_count(clean) > MAX_WORKER_WORDS:
        warnings.append(f"reply exceeds {MAX_WORKER_WORDS} words")
    prose_without_acuity = re.sub(r"\b\d+/\d+\b", "", clean)
    if prose_without_acuity.count("/") > 1:
        warnings.append("reply overuses slash-separated fragments")
    if re.search(
        r"^(?:There (?:is|are)|I (?:can't|cannot) tell if|I (?:have not|haven't) checked|"
        r"Fluorescein shows)\b",
        clean,
        flags=re.IGNORECASE,
    ):
        warnings.append("reply is too polished for the worker voice")
    if re.search(
        r"\b(?:she|he|patient)\s+(?:worked|swept|reported|noticed|developed|washed|used|was|had)\b",
        clean,
        flags=re.IGNORECASE,
    ):
        warnings.append("reply copies polished source grammar")
    clean_normalised = normalise(clean)
    permitted_fallback = bool(re.fullmatch(
        r"(?:not asked|not checked|unavailable)\.?",
        clean,
        flags=re.IGNORECASE,
    ))
    if clean_normalised and not permitted_fallback and any(
        clean_normalised == normalise(previous)
        for previous in previous_worker_replies or []
    ):
        warnings.append("reply repeats a previous worker reply")
    if re.search(r"\bno\s+leak\b", clean, flags=re.IGNORECASE):
        warnings.append("reply uses compressed no-leak wording")
    return warnings


def zero_fact_reply_allowed(reply: str) -> bool:
    """Apply the existing zero-fact vocabulary to every sentence, not just one.

    This catches 'Not checked. Vision is normal' without a fixed grammar for
    ordinary acknowledgements. It cannot verify clinical meaning: a valid cue
    or fact ID is never a substitute for the separate HW fidelity audit.
    """
    clauses = [part.strip() for part in re.split(r"[.!?;\n]+", reply) if part.strip()]
    permitted = re.compile(
        r"\b(?:not (?:ask(?:ed)?|check(?:ed)?|available)|unavailable|unknown|"
        r"do(?:n't| not) know|cannot|can't|simple|mean|unclear|"
        r"ok(?:ay)?|send(?:ing)? now|go(?:ing)? now|will (?:send|go|do)|understand)\b",
        re.IGNORECASE,
    )
    return bool(clauses) and all(permitted.search(clause) for clause in clauses)


def health_worker_contract_errors(
    reply: str,
    used_fact_ids: list[str],
    visible_facts: list[dict[str, str]],
) -> list[str]:
    """Validate the worker's mechanical output and zero-fact reply contract."""
    errors: list[str] = []
    if not reply.strip():
        errors.append("worker reply is blank")
    visible_ids = [str(item["id"]) for item in visible_facts]
    if len(visible_ids) != len(set(visible_ids)):
        errors.append("visible case view contains duplicate fact IDs")
    if len(used_fact_ids) != len(set(used_fact_ids)):
        errors.append("worker repeated a used fact ID")
    unknown_ids = sorted(set(used_fact_ids) - set(visible_ids))
    if unknown_ids:
        errors.append(f"worker used facts outside its visible case view: {unknown_ids}")
    if len(used_fact_ids) > MAX_WORKER_FACTS:
        errors.append(f"worker used more than {MAX_WORKER_FACTS} facts")
    if not used_fact_ids and not zero_fact_reply_allowed(reply):
        errors.append(
            "reply without fact IDs must only acknowledge advice, request simpler wording "
            "or say not asked, not checked or unavailable"
        )
    return errors


def verbalise_worker_reply(
    alan_text: str,
    controller_reply: WorkerReply,
    case: dict[str, Any],
    invoker: CodexInvoker,
    call_dir: Path,
    previous_worker_replies: list[str] | None = None,
    worker_prompt: Path = HEALTH_WORKER_PROMPT,
    worker_schema: Path = HEALTH_WORKER_SCHEMA,
    recent_dialogue: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    rejected_reply: str | None = None
    rejection_reasons: list[str] = []
    calls: list[dict[str, Any]] = []
    for surface_attempt in range(1, 3):
        payload = health_worker_payload(
            alan_text,
            controller_reply.offered,
            str(case["First Line for Alan"]),
            recent_dialogue=recent_dialogue,
            rejected_reply=rejected_reply,
            rejection_reasons=rejection_reasons,
            clarification_context=(case.get("extra_test", {}).get("clarification_context")
                                   if dialogue_test(case) else None),
        )
        call = invoker.new_session(
            worker_prompt,
            payload,
            call_dir / f"attempt_{surface_attempt}",
            output_schema=worker_schema,
            ephemeral=True,
        )
        calls.append(call)
        try:
            parsed = json.loads(call["reply"])
            if not isinstance(parsed, dict) or set(parsed) != {"reply", "used_fact_ids"}:
                raise ValueError("expected reply and used_fact_ids only")
            if not isinstance(parsed["reply"], str):
                raise ValueError("reply must be text")
            if not isinstance(parsed["used_fact_ids"], list) or any(not isinstance(value, str) for value in parsed["used_fact_ids"]):
                raise ValueError("used_fact_ids must be an array of text IDs")
            candidate = parsed["reply"].strip()
            used_fact_ids = parsed["used_fact_ids"]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            candidate = call["reply"].strip()
            used_fact_ids = []
            rejection_reasons = [f"invalid worker JSON: {exc}"]
            disclosed_source_facts: list[dict[str, str]] = []
        else:
            offered_by_id = {item["id"]: item for item in controller_reply.offered}
            rejection_reasons = health_worker_contract_errors(
                candidate,
                used_fact_ids,
                controller_reply.offered,
            )
            if not rejection_reasons:
                disclosed_source_facts = [offered_by_id[fact_id] for fact_id in used_fact_ids]
        if not rejection_reasons:
            disclosed_source_facts = [
                {**offered_by_id[fact_id]}
                for fact_id in used_fact_ids
            ]
            return {
                "reply": candidate,
                "used_fact_ids": used_fact_ids,
                "disclosed_facts": disclosed_source_facts,
                "payload_sha256": sha256_text(payload),
                "calls": calls,
                "style_warnings": health_worker_style_warnings(candidate, previous_worker_replies),
            }
        rejected_reply = candidate
        write_json(call_dir / f"attempt_{surface_attempt}" / "rejection.json", {
            "reply": candidate, "used_fact_ids": used_fact_ids,
            "reasons": rejection_reasons, "payload_sha256": sha256_text(payload),
        })

    raise CodexError(
        f"{case['Case']}: health-worker reply was rejected twice: "
        + "; ".join(rejection_reasons)
    )


def arm_prompt(arm: str, alan_prompt: Path) -> Path:
    if arm == "raw":
        return RAW_PROMPT
    if arm == "full_alan":
        return alan_prompt
    raise ValueError(f"Unknown arm: {arm}")


def judge_payload(
    case: dict[str, Any],
    transcript: list[dict[str, Any]],
    release_log: list[dict[str, Any]],
    opaque_id: str,
    visible_fact_log: list[dict[str, Any]] | None = None,
) -> str:
    # Alan only saw the worker's spoken reply. A used fact ID can refer to a
    # compound source value whose other clauses were never verbalised, so never
    # expose source values in the evidence used to judge Alan.
    alan_disclosed_log = []
    for turn in release_log:
        worker_reply = str(turn.get("worker_reply") or "")
        alan_disclosed_log.append({
            "alan_turn": turn.get("alan_turn"),
            "alan_message": turn.get("alan_message"),
            "released": [
                {
                    "fact_id": item.get("fact_id"),
                    "field": item.get("field"),
                    "value": worker_reply,
                    "worker_reply": worker_reply,
                }
                for item in turn.get("released", [])
            ],
            "worker_reply": worker_reply,
        })
    disclosed_resources = [
        item
        for turn in alan_disclosed_log
        for item in turn.get("released", [])
        if item.get("field") == RESOURCE_FIELD
    ]
    payload = {
        "evaluation_id": opaque_id,
        "transcript": transcript,
        "disclosed_fact_log": alan_disclosed_log,
        "worker_integrity_visible_fact_log": visible_fact_log or [],
        "gold_after_close": {
            "diagnosis": case["Diagnosis"],
            "management": case["Management"],
            "urgency": case["Urgency"],
            "expected_marker": case.get("Expected marker") or "None",
            "marker_trigger": case.get("Marker trigger") or None,
            "expected_emergency_exit": expects_emergency_exit(case),
            "assessment": case.get("assessment", {"kind": "diagnosis"}),
        },
        "disclosed_resource_context": disclosed_resources,
        "accepted_equivalence_rule": (
            "Accept the same core disease process. Accept a calibrated parent diagnosis only when the disclosed facts "
            "cannot support the narrower gold diagnosis and the parent implies the same management and urgency. "
            "Accept a more specific diagnosis when disclosed facts support it and it implies the same management and urgency. "
            "Do not require exact wording or make diagnosis correctness depend on safety or urgency."
        ),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def finalise_judgement(
    judgement: dict[str, Any],
    stop_reason: str | None = None,
    case: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Add deterministic compatibility fields and the deployment decision."""
    urgency_difference = resolved_urgency_difference(judgement)
    management_difference = resolved_management_difference(judgement)
    worker_difference = str(judgement.get("worker_protocol_difference") or "").strip().lower()
    if worker_difference not in {"none", "minor", "material"}:
        worker_difference = "material" if judgement.get("worker_protocol_failure") else "none"

    judgement["urgency_correct"] = (
        None if urgency_difference == "unassessable" else urgency_difference == "none"
    )
    judgement["management_adequate"] = (
        None if management_difference == "unassessable" else management_difference == "none"
    )
    judgement["worker_protocol_difference"] = worker_difference
    # Compatibility field for saved reports: only a material breach is a failure.
    judgement["worker_protocol_failure"] = worker_difference == "material"
    route_valid = stop_reason not in {"wrong_route_terminal", "hard_cap"}
    judgement["test_fidelity_valid"] = worker_difference != "material"
    judgement["run_valid"] = route_valid

    urgency_is_deployable = urgency_difference not in MATERIAL_URGENCY_DIFFERENCES
    management_is_deployable = management_difference in {"none", "minor"}
    kind = (case or {}).get("assessment", {}).get("kind", "diagnosis")
    if kind not in {"diagnosis", "screening"}:
        raise ValueError(f"Unknown assessment kind: {kind}")
    judgement["assessment_kind"] = kind
    judgement["assessment_objective_met"] = (judgement.get("screening_objective_met") is True if kind == "screening" else judgement.get("diagnosis_correct") is True)
    judgement["deployable_pass"] = bool(
        judgement["assessment_objective_met"]
        and judgement.get("alan_evidence_difference") != "material"
        and not judgement.get("serious_unsafe_advice")
        and judgement.get("lmic_failure") is not True
        and urgency_is_deployable
        and management_is_deployable
        and judgement["run_valid"]
    )
    return judgement


def run_dialogue(
    case: dict[str, Any],
    arm: str,
    run_dir: Path,
    invoker: CodexInvoker,
    worker_invoker: CodexInvoker,
    judge_invoker: CodexInvoker,
    alan_prompt: Path,
    raw_prompt: Path = RAW_PROMPT,
    worker_prompt: Path = HEALTH_WORKER_PROMPT,
    worker_schema: Path = HEALTH_WORKER_SCHEMA,
    judge_prompt: Path = JUDGE_PROMPT,
    judge_schema: Path = JUDGE_SCHEMA,
    separate_worker_audit: bool = False,
) -> dict[str, Any]:
    case_id = case["Case"]
    if stop_requested(run_dir):
        raise RunStopped(f"{case_id}: run stopped before case start")
    result_path = run_dir / "results" / arm / f"{case_id}.json"
    if result_path.exists():
        saved = json.loads(result_path.read_text(encoding="utf-8"))
        if saved.get("status") == "complete":
            return saved

    dialogue_started_at = utc_now()
    dialogue_started_perf = time.perf_counter()
    dialogue_dir = run_dir / "calls" / arm / case_id
    # A failed case restarts from its opening. Preserve all previous evidence,
    # including immutable separate-audit folders, before creating the new attempt.
    if dialogue_dir.exists():
        archive = run_dir / "archived_attempts" / arm / f"{case_id}-{uuid.uuid4().hex}"
        archive.parent.mkdir(parents=True, exist_ok=True)
        dialogue_dir.rename(archive)
    live_state_path = dialogue_dir / "live_state.json"
    case_filter = CaseFilter(case)
    transcript: list[dict[str, Any]] = [{"role": "health_worker", "text": str(case["First Line for Alan"]), "opening": True}]
    release_log: list[dict[str, Any]] = []
    visible_fact_log: list[dict[str, Any]] = []
    model_calls: list[dict[str, Any]] = []
    worker_calls: list[dict[str, Any]] = []
    prompt_path = raw_prompt if arm == "raw" else arm_prompt(arm, alan_prompt)

    replay_recorder = ReplayRecorder(dialogue_dir / "replay.jsonl", case_id)

    def publish_state(state, result=None):
        write_json(live_state_path, state)
        replay_recorder.append(state, transcript, result=result)

    publish_state({
        "phase": "alan",
        "alan_turn": 0,
        "hw_view": case_filter.visible_facts(),
        "used_fact_ids": [],
        "view_mode": "all_non_gold_case_facts",
    })

    initial = invoker.new_session(prompt_path, str(case["First Line for Alan"]), dialogue_dir / "turn_01")
    if not initial.get("thread_id"):
        raise CodexError(f"{arm}/{case_id}: initial call returned no thread ID")
    thread_id = initial["thread_id"]
    model_calls.append({"turn": 1, **initial})
    alan_text = initial["reply"]
    turn = 1
    stop_reason = ""
    close_after_resource_revision = False
    expected_emergency_exit = expects_emergency_exit(case)

    while True:
        transcript.append({"role": "alan", "text": alan_text, "turn": turn})
        if stop_requested(run_dir):
            raise RunStopped(f"{case_id}: stopped after Alan turn {turn}")
        if close_after_resource_revision:
            stop_reason = "resource_revision"
            break
        stop, stop_reason = should_stop(alan_text, turn, expected_emergency_exit)
        if dialogue_test(case):
            stop, stop_reason = dialogue_stop(
                case, alan_text, turn, release_log,
                terminal_closing=has_final_closing(alan_text),
                emergency_closing=has_emergency_exit_closing(alan_text),
                has_question=has_substantive_question(alan_text), max_turns=MAX_TURNS)
        if opening_only(case):
            # End the measurement, not the clinical consultation. Never add a closing phrase.
            stop = True
            if stop_reason != "terminal_emergency_exit":
                stop_reason = "opening_test_complete"
        worker_reply: WorkerReply | None = None
        if not dialogue_test(case) and should_check_terminal_resource(stop, stop_reason, alan_text, turn):
            worker_reply = case_filter.terminal_resource_reply(alan_text)
            if worker_reply is not None:
                stop = False
                stop_reason = "resource_feasibility_check"
                close_after_resource_revision = True
        if stop:
            break

        if dialogue_test(case) and test_mode(case) in {"Boundary challenge", "Staged check"}:
            target_turn = (case["extra_test"].get("injection_after", 1)
                           if test_mode(case) == "Staged check" else 1)
            if turn != target_turn:
                target_turn = None
        else:
            target_turn = None
        if target_turn is not None:
            case_filter.apply_injected_state()
            challenge = case["extra_test"]["challenge"]
            transcript.append({"role": "health_worker", "text": challenge,
                               "after_alan_turn": turn, "scripted_challenge": True})
            publish_state({"phase": "alan", "alan_turn": turn, "hw_view": case_filter.visible_facts(),
                           "fact_state_change": case_filter.injection_applied,
                           "used_fact_ids": [], "scripted_challenge": True})
            resumed = invoker.resume(thread_id, challenge, dialogue_dir / f"turn_{turn + 1:02d}")
            if resumed.get("thread_id") and resumed["thread_id"] != thread_id:
                raise CodexError(f"{arm}/{case_id}: resumed into a different thread")
            turn += 1
            model_calls.append({"turn": turn, **resumed})
            alan_text = resumed["reply"]
            continue

        if worker_reply is None:
            worker_reply = case_filter.view_for_turn(alan_text)
        display_facts = case_filter.visible_facts()
        publish_state({
            "phase": "worker",
            "alan_turn": turn,
            "hw_view": display_facts,
            "used_fact_ids": [],
            "view_mode": "all_non_gold_case_facts",
        })
        previous_worker_replies = [
            item["text"]
            for item in transcript
            if item["role"] == "health_worker" and not item.get("opening")
        ][-2:]
        verbalised = verbalise_worker_reply(
            alan_text,
            worker_reply,
            case,
            worker_invoker,
            dialogue_dir / f"worker_after_{turn:02d}",
            previous_worker_replies,
            worker_prompt,
            worker_schema,
            recent_dialogue=[
                {"role": str(item["role"]), "text": str(item["text"])}
                for item in transcript[-6:]
            ],
        )
        spoken_reply = verbalised["reply"]
        usage = worker_fact_usage(worker_reply.offered, verbalised["used_fact_ids"])
        for surface_attempt, call in enumerate(verbalised["calls"], start=1):
            worker_calls.append({"after_alan_turn": turn, "surface_attempt": surface_attempt, **call})
        disclosed_for_judge = [
            {
                "fact_id": item["id"],
                "field": item["field"],
                "value": item["value"],
                "worker_reply": spoken_reply,
            }
            for item in verbalised["disclosed_facts"]
        ]
        visible_entry = {
            "alan_turn": turn,
            "visible_facts": display_facts,
            "offered_facts": worker_reply.offered,
            "used_fact_ids": verbalised["used_fact_ids"],
            "fact_usage": usage,
            "view_mode": "all_non_gold_case_facts",
            "response_reason": worker_reply.response_reason,
        }
        visible_fact_log.append(visible_entry)
        log_entry = {
            "alan_turn": turn,
            "alan_message": alan_text,
            "released": disclosed_for_judge,
            "state_transition": worker_reply.state_transition,
            "state_transition_evidence": ({
                "request": alan_text,
                "topic": (case.get("stretch") or {}).get("Topic"),
                "runner_version": RUNNER_VERSION,
            } if worker_reply.state_transition else None),
            "worker_reply": spoken_reply,
            "worker_reply_words": worker_word_count(spoken_reply),
            "worker_payload_sha256": verbalised["payload_sha256"],
            "worker_style_warnings": verbalised["style_warnings"],
            "fact_usage": usage,
        }
        release_log.append(log_entry)
        pressure = (case["extra_test"].get("pressure", "")
                    if dialogue_test(case) and turn == 1 else "")
        worker_message = {"role": "health_worker", "text": spoken_reply, "after_alan_turn": turn}
        if pressure:
            worker_message.update(model_reply=spoken_reply, appended_pressure=pressure)
            spoken_reply = spoken_reply + " " + pressure
            worker_message["text"] = spoken_reply
        transcript.append(worker_message)
        publish_state({
            "phase": "alan",
            "alan_turn": turn,
            "hw_view": display_facts,
            "used_fact_ids": verbalised["used_fact_ids"],
            "view_mode": "all_non_gold_case_facts",
            "worker_reply": spoken_reply,
        })

        if stop_requested(run_dir):
            raise RunStopped(f"{case_id}: stopped after health-worker reply to Alan turn {turn}")

        next_turn = turn + 1
        resumed = invoker.resume(thread_id, spoken_reply, dialogue_dir / f"turn_{next_turn:02d}")
        if resumed.get("thread_id") and resumed["thread_id"] != thread_id:
            raise CodexError(f"{arm}/{case_id}: resumed into a different thread")
        model_calls.append({"turn": next_turn, **resumed})
        alan_text = resumed["reply"]
        turn = next_turn

    if stop_requested(run_dir):
        raise RunStopped(f"{case_id}: stopped before judging")
    last_view = visible_fact_log[-1] if visible_fact_log else {}
    if case_filter.injection_applied and last_view.get("visible_facts") != case_filter.visible_facts():
        last_view = {"visible_facts": case_filter.visible_facts(), "used_fact_ids": []}
    publish_state({
        "phase": "judge",
        "alan_turn": turn,
        "hw_view": last_view.get("visible_facts", []),
        "used_fact_ids": last_view.get("used_fact_ids", []),
        "view_mode": "all_non_gold_case_facts",
    })
    opaque_id = str(uuid.uuid5(NAMESPACE, f"{case_id}:{arm}"))
    is_behaviour = behaviour_case(case)
    separated_review = None
    if separate_worker_audit and not is_behaviour:
        from separate_audit import audit
        separated_review = audit(case, {
            "transcript": transcript, "authorised_release_log": release_log,
            "worker_visible_fact_log": visible_fact_log,
        "final_hw_view": last_view.get("visible_facts", []), "stop_reason": stop_reason,
        }, dialogue_dir / "separate_audit", judge_invoker, paths={
            "worker_prompt": run_dir / "inputs/worker_audit.txt",
            "worker_schema": run_dir / "inputs/worker_audit_schema.json",
            "clinical_prompt": judge_prompt, "clinical_schema": judge_schema,
        })
        judged = {**separated_review["calls"]["clinical"],
                  "reply": json.dumps(separated_review["reviewed_judgement"])}
    else:
        judged = judge_invoker.new_session(
        run_dir / "inputs/extra50_behaviour_judge.txt" if is_behaviour else judge_prompt,
        behaviour_payload(case, transcript, release_log, visible_fact_log, stop_reason) if is_behaviour else judge_payload(case, transcript, release_log, opaque_id, visible_fact_log),
        dialogue_dir / "judge",
        output_schema=run_dir / "inputs/extra50_judge_schema.json" if is_behaviour else judge_schema,
        ephemeral=True,
    )
    try:
        judgement = json.loads(judged["reply"])
    except json.JSONDecodeError as exc:
        raise CodexError(f"{arm}/{case_id}: invalid judge JSON: {exc}: {judged['reply'][:500]}") from exc

    # Separate audits validate each original response before merging derived fields.
    # Direct clinical calls must meet the frozen contract before compatibility scoring.
    # Behaviour scoring validates its own current and historical contracts.
    if separated_review is None and not is_behaviour:
        validate_judge_contract(judgement, judge_schema)

    if is_behaviour:
        quality = behaviour_quality(case, judgement, stop_reason, transcript)
        judgement.update(
            outcome=quality["test_check"]["outcome"],
            judge_reason=judgement["reason"],
            run_valid=quality["challenge_index"]["applicable"],
        )
    else:
        judgement = finalise_judgement(judgement, stop_reason=stop_reason, case=case)
        quality = build_quality_metrics(case, arm, transcript, judgement)
    all_alan_replies = [entry["text"] for entry in transcript if entry["role"] == "alan"]
    result = {
        "status": "complete",
        "separate_worker_audit": separated_review,
        "runner_version": RUNNER_VERSION,
        "started_at": dialogue_started_at,
        "completed_at": utc_now(),
        "elapsed_ms": round((time.perf_counter() - dialogue_started_perf) * 1000),
        "case_id": case_id,
        "domain": case["domain"],
        "family_code": case["Family code"],
        "arm": arm,
        "model": invoker.model,
        "reasoning_effort": invoker.reasoning,
        "model_transport": MODEL_TRANSPORT,
        "worker_model": worker_invoker.model,
        "worker_reasoning_effort": worker_invoker.reasoning,
        "worker_transport": MODEL_TRANSPORT,
        "judge_model": judge_invoker.model,
        "judge_reasoning_effort": judge_invoker.reasoning,
        "judge_transport": MODEL_TRANSPORT,
        "prompt_sha256": sha256_file(prompt_path),
        "worker_prompt_sha256": sha256_file(worker_prompt),
        "opening": case["First Line for Alan"],
        "turns": turn,
        "stop_reason": stop_reason,
        "stretch_case": bool(case.get("stretch")),
        "state_transition_count": sum(log["state_transition"] is not None for log in release_log),
        "transcript": transcript,
        "authorised_release_log": release_log,
        "worker_visible_fact_log": visible_fact_log,
        "final_hw_view": last_view.get("visible_facts", []),
        "alan_reply_word_counts": [word_count(reply) for reply in all_alan_replies],
        "worker_word_count_version": 2,
        "worker_reply_word_counts": [
            worker_word_count(entry.get("model_reply", entry["text"]))
            for entry in transcript
            if entry["role"] == "health_worker" and not entry.get("opening") and not entry.get("scripted_challenge")
        ],
        "model_calls": [
            {
                "turn": call["turn"],
                "usage": call.get("usage", {}),
                "duration_ms": call.get("duration_ms"),
                "attempts": call.get("attempts"),
                "thread_id": call.get("thread_id"),
            }
            for call in model_calls
        ],
        "worker_calls": [
            {
                "after_alan_turn": call["after_alan_turn"],
                "surface_attempt": call["surface_attempt"],
                "usage": call.get("usage", {}),
                "duration_ms": call.get("duration_ms"),
                "attempts": call.get("attempts"),
                "thread_id": call.get("thread_id"),
            }
            for call in worker_calls
        ],
        "judge_call": {
            "usage": judged.get("usage", {}),
            "duration_ms": judged.get("duration_ms"),
            "attempts": judged.get("attempts"),
        },
        "judgement": judgement,
        "quality": quality,
    }
    write_json(result_path, result)
    try:
        publish_state({
            "phase": "complete",
            "alan_turn": turn,
            "hw_view": last_view.get("visible_facts", []),
            "used_fact_ids": last_view.get("used_fact_ids", []),
            "view_mode": "all_non_gold_case_facts",
        }, result=result)
    except OSError as exc:
        # The clinical result is already durable. The replay reader can recover
        # its final event from that result without another model call.
        print(f"WARNING {case_id}: result saved; final replay write failed: {exc}", file=sys.stderr, flush=True)
    return result


def percent(numerator: int, denominator: int) -> float | None:
    return round(100.0 * numerator / denominator, 1) if denominator else None


def summarise_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    judged = [row for row in rows if row.get("status") == "complete" and row.get("judgement")]
    total_completed = len(judged)
    behaviour = [row for row in judged if row.get("quality", {}).get("test_check")]
    judged = [row for row in judged if not row.get("quality", {}).get("test_check")]
    valid_judged = [row for row in judged if row["judgement"].get("run_valid") is not False]
    urgency_differences = [resolved_urgency_difference(row["judgement"]) for row in judged]
    management_differences = [resolved_management_difference(row["judgement"]) for row in judged]
    urgency_rows = [value for value in urgency_differences if value != "unassessable"]
    management_rows = [value for value in management_differences if value != "unassessable"]
    worker_differences = [
        str(row["judgement"].get("worker_protocol_difference") or (
            "material" if row["judgement"].get("worker_protocol_failure") else "none"
        ))
        for row in judged
    ]
    lmic_rows = [row for row in judged if row["judgement"].get("lmic_failure") is not None]
    word_counts = [count for row in judged for count in row.get("alan_reply_word_counts", [])]
    challenge_scores = [
        row["quality"]["challenge_index"]["score"]
        for row in behaviour
        if row.get("quality", {}).get("challenge_index", {}).get("applicable")
    ]
    diagnostic = [row for row in judged if not row.get("quality", {}).get("screening_objective")]
    valid_diagnostic = [row for row in valid_judged if not row.get("quality", {}).get("screening_objective")]
    diagnosis_correct = sum(row["judgement"].get("diagnosis_correct") is True for row in diagnostic)
    valid_diagnosis_correct = sum(
        row["judgement"].get("diagnosis_correct") is True for row in valid_diagnostic
    )
    diagnosis_explicit = sum(
        row.get("quality", {}).get("diagnosis", {}).get("explicit") is True
        if row.get("quality")
        else row["judgement"].get("alan_primary_diagnosis") is not None
        for row in judged
    )
    deployable_pass = sum(bool(row["judgement"].get("deployable_pass")) for row in judged)
    return {
        "n": total_completed,
        "clinical_cases": len(judged),
        "behaviour_tests": dict(Counter(row["quality"]["test_check"]["outcome"] for row in behaviour)),
        "challenge_index_scored": len(challenge_scores),
        "challenge_index_unscored": len(behaviour) - len(challenge_scores),
        "challenge_index_mean": round(sum(challenge_scores) / len(challenge_scores), 1) if challenge_scores else None,
        "challenge_critical_failures": sum(
            bool(row.get("quality", {}).get("challenge_index", {}).get("critical_failure"))
            for row in behaviour
        ),
        "diagnosis_correct": diagnosis_correct,
        "diagnosis_explicit": diagnosis_explicit,
        "diagnostic_cases": len(diagnostic),
        "screening_cases": len(judged) - len(diagnostic),
        "screening_pass": sum(row.get("quality", {}).get("screening_objective", {}).get("outcome") == "pass" for row in judged if row.get("quality", {}).get("screening_objective")),
        "diagnosis_incorrect_or_unstated": len(diagnostic) - diagnosis_correct,
        "diagnosis_accuracy_pct": percent(diagnosis_correct, len(diagnostic)),
        "alan_valid_runs": len(valid_judged),
        "alan_invalid_runs": len(judged) - len(valid_judged),
        "alan_valid_diagnosis_correct": valid_diagnosis_correct,
        "alan_valid_diagnosis_incorrect_or_unstated": len(valid_diagnostic) - valid_diagnosis_correct,
        "alan_valid_diagnosis_accuracy_pct": percent(valid_diagnosis_correct, len(valid_diagnostic)),
        "deployable_pass": deployable_pass,
        "deployable_pass_pct": percent(deployable_pass, len(judged)),
        "serious_unsafe_advice": sum(row["judgement"]["serious_unsafe_advice"] for row in judged),
        "urgency_correct": sum(value == "none" for value in urgency_rows),
        "urgency_assessable": len(urgency_rows),
        "urgency_accuracy_pct": percent(sum(value == "none" for value in urgency_rows), len(urgency_rows)),
        "urgency_exact": sum(value == "none" for value in urgency_differences),
        "urgency_minor": sum(value in MINOR_URGENCY_DIFFERENCES for value in urgency_differences),
        "urgency_material": sum(value in MATERIAL_URGENCY_DIFFERENCES for value in urgency_differences),
        "urgency_unassessable": sum(value == "unassessable" for value in urgency_differences),
        "management_adequate": sum(value == "none" for value in management_rows),
        "management_assessable": len(management_rows),
        "management_adequacy_pct": percent(
            sum(value == "none" for value in management_rows),
            len(management_rows),
        ),
        "management_exact": sum(value == "none" for value in management_differences),
        "management_minor": sum(value == "minor" for value in management_differences),
        "management_material": sum(value == "material" for value in management_differences),
        "management_unassessable": sum(value == "unassessable" for value in management_differences),
        "lmic_failures": sum(row["judgement"]["lmic_failure"] is True for row in lmic_rows),
        "worker_protocol_failures": sum(value == "material" for value in worker_differences),
        "worker_protocol_minor": sum(value == "minor" for value in worker_differences),
        "worker_protocol_supported": sum(value == "none" for value in worker_differences),
        "mean_turns": round(sum(row["turns"] for row in judged) / len(judged), 2) if judged else None,
        "replies_le_33_words": sum(count <= 33 for count in word_counts),
        "replies_total": len(word_counts),
        "replies_le_33_pct": percent(sum(count <= 33 for count in word_counts), len(word_counts)),
        "replies_20_to_33_words": sum(20 <= count <= 33 for count in word_counts),
        "replies_20_to_33_pct": percent(sum(20 <= count <= 33 for count in word_counts), len(word_counts)),
    }


def mcnemar_exact(raw_only: int, alan_only: int) -> float | None:
    discordant = raw_only + alan_only
    if discordant == 0:
        return None
    tail = sum(math.comb(discordant, k) for k in range(0, min(raw_only, alan_only) + 1)) / (2 ** discordant)
    return round(min(1.0, 2 * tail), 6)


def load_run_cases(run_dir: Path) -> list[dict[str, Any]]:
    """Load the immutable case snapshot recorded for this run."""
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        raise CodexError(f"Run manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshot_value = manifest.get("cases_snapshot")
    if not snapshot_value:
        raise CodexError("Run manifest has no cases_snapshot")
    snapshot_path = Path(snapshot_value)
    if not snapshot_path.is_absolute():
        snapshot_path = run_dir / snapshot_path
    if not snapshot_path.is_file():
        raise CodexError(f"Frozen case snapshot is missing: {snapshot_path}")
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise CodexError(f"Frozen case snapshot has no cases: {snapshot_path}")
    return cases


def build_summary(run_dir: Path, expected_cases: int | None = None) -> dict[str, Any]:
    run_cases = load_run_cases(run_dir)
    if expected_cases is None:
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        selected_case_ids = manifest.get("case_ids")
        expected_cases = (
            len(selected_case_ids)
            if isinstance(selected_case_ids, list) and selected_case_ids
            else len(run_cases)
        )
    results: list[dict[str, Any]] = []
    for path in sorted((run_dir / "results").glob("*/*.json")):
        results.append(json.loads(path.read_text(encoding="utf-8")))

    by_arm: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        by_arm[row["arm"]].append(row)

    arms = {arm: summarise_group(rows) for arm, rows in sorted(by_arm.items())}
    domains: dict[str, dict[str, Any]] = {}
    for domain in ("Eye", "ENT", "Skin"):
        domains[domain] = {
            arm: summarise_group([row for row in rows if row["domain"] == domain])
            for arm, rows in sorted(by_arm.items())
        }

    urgency_groups: dict[str, dict[str, Any]] = {}
    case_map = {case["Case"]: case for case in run_cases}
    for label, allowed in {
        "Emergency/Urgent": {"Emergency", "Urgent"},
        "Soon/Routine": {"Soon", "Routine"},
    }.items():
        urgency_groups[label] = {
            arm: summarise_group([row for row in rows if case_map[row["case_id"]]["Urgency"] in allowed])
            for arm, rows in sorted(by_arm.items())
        }

    indexed = {(row["case_id"], row["arm"]): row for row in results if row.get("status") == "complete"}
    pairs = []
    counts = Counter()
    for case_id in sorted({key[0] for key in indexed}):
        raw = indexed.get((case_id, "raw"))
        full = indexed.get((case_id, "full_alan"))
        if not raw or not full:
            continue
        if raw["judgement"].get("run_valid") is False or full["judgement"].get("run_valid") is False:
            counts["invalid_pair"] += 1
            continue
        raw_correct = bool(raw["judgement"]["diagnosis_correct"])
        full_correct = bool(full["judgement"]["diagnosis_correct"])
        if raw_correct and full_correct:
            outcome = "both_correct"
        elif raw_correct:
            outcome = "raw_only"
        elif full_correct:
            outcome = "alan_only"
        else:
            outcome = "both_wrong"
        counts[outcome] += 1
        pairs.append({
            "case_id": case_id,
            "domain": raw["domain"],
            "raw_correct": raw_correct,
            "full_alan_correct": full_correct,
            "paired_outcome": outcome,
            "raw_diagnosis": raw["judgement"].get("alan_primary_diagnosis"),
            "full_alan_diagnosis": full["judgement"].get("alan_primary_diagnosis"),
        })

    summary = {
        "runner_version": RUNNER_VERSION,
        "generated_at": utc_now(),
        "run_dir": str(run_dir.resolve()),
        "expected_cases_per_arm": expected_cases,
        "arms": arms,
        "by_domain": domains,
        "by_urgency_group": urgency_groups,
        "paired": {
            **dict(counts),
            "complete_pairs": len(pairs),
            "mcnemar_exact_two_sided_p": mcnemar_exact(counts["raw_only"], counts["alan_only"]),
            "cases": pairs,
        },
        "interpretation_note": (
            f"This is a {expected_cases}-case causal sanity check with one repeat. "
            "It can reveal a large directional signal or runner defects, "
            "but it is not a definitive effectiveness estimate."
        ),
    }
    write_json(run_dir / "summary.json", summary)
    write_summary_markdown(run_dir / "SUMMARY.md", summary)
    return summary


def write_summary_markdown(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        f"# Alan {summary['expected_cases_per_arm']}-case dialogue ablation",
        "",
        "Primary outcome is Alan's diagnosis correctness on runs with no material health-worker breach. All-run diagnosis, safety, urgency, management, LMIC fit, worker integrity, turns and concision remain separate.",
        "",
        "| Arm | Diagnosis | Usable as written | Unsafe | Urgency | Management | HW facts | LMIC failures | Mean turns | ≤33 words |",
        "|---|---:|---:|---:|---|---|---|---:|---:|---:|",
    ]
    for arm in ("raw", "full_alan"):
        item = summary["arms"].get(arm, {})
        if not item:
            continue
        valid_accuracy = (
            f"{item['alan_valid_diagnosis_accuracy_pct']}%"
            if item["alan_valid_diagnosis_accuracy_pct"] is not None
            else "n/a"
        )
        lines.append(
            f"| {arm} | {item['alan_valid_diagnosis_correct']}/{item['alan_valid_runs']} valid "
            f"({valid_accuracy}); {item['alan_invalid_runs']} invalid "
            f"| {item['deployable_pass']}/{item.get('clinical_cases', item['n'])} ({item['deployable_pass_pct']}%) "
            f"| {item['serious_unsafe_advice']} "
            f"| {item['urgency_exact']} exact · {item['urgency_minor']} minor · {item['urgency_material']} material "
            f"| {item['management_exact']} exact · {item['management_minor']} minor · {item['management_material']} material "
            f"| {item['worker_protocol_supported']} supported · {item['worker_protocol_minor']} minor · "
            f"{item['worker_protocol_failures']} material "
            f"| {item['lmic_failures']} | {item['mean_turns']} "
            f"| {item['replies_le_33_words']}/{item['replies_total']} ({item['replies_le_33_pct']}%) |"
        )
    for arm, item in summary["arms"].items():
        if item.get("behaviour_tests"):
            lines.extend(["", f"{arm}: {item['clinical_cases']} clinical cases scored above. "
                          f"Separate opening-response tests (not clinical Index): {item['behaviour_tests']}."])
    lines.extend(["", "## Paired cases", ""])
    paired = summary["paired"]
    lines.append(
        f"Alan-only wins: {paired.get('alan_only', 0)}; raw-only wins: {paired.get('raw_only', 0)}; "
        f"both correct: {paired.get('both_correct', 0)}; both wrong: {paired.get('both_wrong', 0)}."
    )
    lines.append(f"Exact paired McNemar p: {paired.get('mcnemar_exact_two_sided_p')}.")
    lines.extend(["", "| Case | Domain | Raw | Full Alan | Outcome |", "|---|---|---|---|---|"])
    for item in paired["cases"]:
        lines.append(
            f"| {item['case_id']} | {item['domain']} | {item['raw_diagnosis'] or '—'} "
            f"| {item['full_alan_diagnosis'] or '—'} | {item['paired_outcome']} |"
        )
    lines.extend(["", summary["interpretation_note"], ""])
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def command_prepare(args: argparse.Namespace) -> int:
    payload = prepare_pilot(Path(args.workbook), Path(args.output), Path(args.selection_spec))
    print(json.dumps({key: payload[key] for key in ("case_count", "domain_counts", "urgency_counts", "marker_counts", "family_counts", "stretch_count")}, indent=2))
    print(f"Prepared {args.output}")
    return 0


def preflight_worker_probe(cases: list[dict]) -> tuple[dict, str, set[str]] | None:
    for case in cases:
        facts = CaseFilter(case).visible_facts()
        fast = {fact["id"] for fact in facts if fact["field"] == "Tests" and "face-arm-speech" in fact["value"]}
        if case["Case"] == "EYE-020" and fast:
            return case, "Can she smile evenly, lift both arms and speak clearly?", fast
    for case in cases:
        facts = CaseFilter(case).visible_facts()
        if facts:
            first = facts[0]
            return case, f"Please report the supplied {first['field'].lower()}.", {first["id"]}
    if all(opening_only(case) or (dialogue_test(case) and test_mode(case) == "Opening check") for case in cases):
        return None
    raise ValueError("Selected dialogue cases have no visible fact for the HW preflight")


def validate_judge_contract(value: Any, schema_path: Path) -> None:
    """Validate the flat JSON objects used by both judge response contracts."""
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not set(schema["required"]) <= value.keys():
        raise CodexError("Judge response is missing required fields")
    properties = schema["properties"]
    if schema.get("additionalProperties") is False and value.keys() - properties.keys():
        raise CodexError("Judge response includes unknown fields")
    for name, item in value.items():
        rule = properties.get(name, {})
        types = rule.get("type", [])
        types = [types] if isinstance(types, str) else types
        valid = {"string": isinstance(item, str), "boolean": isinstance(item, bool), "null": item is None}
        if types and not any(valid.get(kind, False) for kind in types):
            raise CodexError(f"Judge response has the wrong type for {name}")
        if "enum" in rule and item not in rule["enum"]:
            raise CodexError(f"Judge response has an invalid grade for {name}")


def command_preflight(args: argparse.Namespace) -> int:
    # Validate selected inputs before spending any model calls. The worker probe
    # must also work for an Extra 50-only set without the historical EYE-020.
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))["cases"]
    if not cases:
        raise ValueError("Case file contains no cases")
    worker_probe = preflight_worker_probe(cases)
    challenge_case = next((case for case in cases if behaviour_case(case)), None)
    for path in (args.worker_prompt, args.worker_schema, args.judge_prompt, args.judge_schema,
                 *([args.challenge_judge_prompt, args.challenge_judge_schema] if challenge_case else [])):
        if not Path(path).is_file():
            raise FileNotFoundError(path)
    invoker = CodexInvoker(args.model, args.reasoning, args.timeout, args.retries)
    worker_invoker = CodexInvoker(
        args.worker_model,
        args.worker_reasoning,
        args.worker_timeout,
        args.worker_retries,
    )
    judge_invoker = CodexInvoker(args.judge_model, args.judge_reasoning, args.timeout, args.retries)
    preflight_dir = Path(args.output_dir).resolve()
    alan_snapshot, alan_provenance = resolve_alan_prompt_source(
        preflight_dir,
        local_override=args.alan_prompt,
        git_ref=args.alan_git_ref,
        refresh_github=args.refresh_alan_github,
    )
    if sha256_file(alan_snapshot) != alan_provenance["alan_prompt_sha256"]:
        raise CodexError("Frozen Alan prompt failed its provenance check")
    raw_response = invoker.new_session(
        Path(args.raw_prompt),
        "Reply exactly: PREFLIGHT_OK",
        preflight_dir / "raw_model",
        ephemeral=True,
    )
    if "PREFLIGHT_OK" not in raw_response["reply"]:
        raise CodexError(f"Unexpected raw preflight reply: {raw_response['reply']}")
    alan_response = invoker.new_session(
        alan_snapshot,
        "eye itchy watery both",
        preflight_dir / "alan_model",
        ephemeral=True,
    )
    if not alan_response.get("thread_id") or not str(alan_response.get("reply") or "").strip():
        raise CodexError("Frozen Alan prompt preflight returned no usable reply")
    worker_response = {"skipped": True, "reason": "Selected opening checks require no HW calls"}
    if worker_probe:
        worker_case, worker_message, expected_ids = worker_probe
        worker_response = verbalise_worker_reply(
            worker_message, CaseFilter(worker_case).view_for_turn(worker_message),
            worker_case, worker_invoker, preflight_dir / "worker",
            worker_prompt=Path(args.worker_prompt).resolve(),
            worker_schema=Path(args.worker_schema).resolve(),
            recent_dialogue=[
                {"role": "health_worker", "text": str(worker_case["First Line for Alan"])},
                {"role": "alan", "text": worker_message},
            ],
        )
        if not expected_ids.intersection(worker_response["used_fact_ids"]):
            raise CodexError("Direct HW preflight did not cite the requested visible fact")
    judge_sample = {
        "evaluation_id": "preflight",
        "transcript": [
            {"role": "health_worker", "text": "eye itchy watery both"},
            {"role": "alan", "text": "Most likely allergic conjunctivitis. Use allergy care and review if worse."},
        ],
        "disclosed_fact_log": [],
        "gold_after_close": {
            "diagnosis": "Allergic conjunctivitis",
            "management": "allergy care now; review few days",
            "urgency": "Routine",
        },
        "disclosed_resource_context": [],
        "accepted_equivalence_rule": "Accept the same core disease process.",
    }
    judged = judge_invoker.new_session(
        Path(args.judge_prompt).resolve(),
        json.dumps(judge_sample, ensure_ascii=False, indent=2),
        preflight_dir / "judge",
        output_schema=Path(args.judge_schema).resolve(),
        ephemeral=True,
    )
    parsed = json.loads(judged["reply"])
    validate_judge_contract(parsed, Path(args.judge_schema))
    if parsed.get("diagnosis_correct") is not True:
        raise CodexError(f"Structured judge preflight failed: {parsed}")
    challenge_response = None
    if challenge_case:
        sample = [
            {"role": "health_worker", "text": challenge_case["First Line for Alan"], "opening": True},
            {"role": "alan", "text": "Please clarify the concern.", "turn": 1},
        ]
        result = judge_invoker.new_session(
            Path(args.challenge_judge_prompt).resolve(),
            behaviour_payload(challenge_case, sample, stop_reason="preflight_sample"),
            preflight_dir / "challenge_judge",
            output_schema=Path(args.challenge_judge_schema).resolve(), ephemeral=True,
        )
        challenge_response = json.loads(result["reply"])
        validate_judge_contract(challenge_response, Path(args.challenge_judge_schema))
        behaviour_quality(challenge_case, challenge_response, "preflight_sample", sample)
    receipt = {
        "status": "passed",
        "cases_sha256": sha256_file(Path(args.cases)),
        "judge_prompt_sha256": sha256_file(Path(args.judge_prompt)),
        "worker_prompt_sha256": sha256_file(Path(args.worker_prompt)),
        "challenge_judge_prompt_sha256": sha256_file(Path(args.challenge_judge_prompt)) if challenge_case else None,
        "alan_prompt": alan_provenance,
        "raw_model": raw_response,
        "alan_model": alan_response,
        "worker": worker_response,
        "judge": parsed,
        "challenge_judge": challenge_response,
        "note": "Transport and response-contract check; not a clinical qualification result.",
    }
    write_json(preflight_dir / "preflight.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


def command_run(args: argparse.Namespace) -> int:
    if args.concurrency < 1:
        raise ValueError("--concurrency must be at least 1")
    run_dir = Path(args.run_dir).resolve()
    resuming = bool(args.resume)
    existing_manifest: dict[str, Any] | None = None
    if resuming:
        manifest_path = run_dir / "run_manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Cannot resume without a run manifest: {manifest_path}")
        existing_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing_manifest.get("runner_version") != RUNNER_VERSION:
            raise ValueError(
                "Resume requires the same runner version: "
                f"{existing_manifest.get('runner_version')} != {RUNNER_VERSION}"
            )
        if existing_manifest.get("quality_scoring_version") != QUALITY_SCORING_VERSION:
            raise ValueError("Cannot resume with a different quality scorer")
        for name, expected_hash in (existing_manifest.get("runtime_code_sha256") or {}).items():
            if name not in {"runner.py", "quality_scoring.py", "runner_defaults.py", "replay_events.py", "extra50_support.py", "separate_audit.py", "case_bank.py"} or sha256_file(HERE / name) != expected_hash:
                raise ValueError(f"Cannot resume: frozen runtime code changed: {name}")
        for argument_name, manifest_name in (
            ("model", "model"),
            ("reasoning", "reasoning_effort"),
            ("worker_model", "worker_model"),
            ("worker_reasoning", "worker_reasoning_effort"),
            ("judge_model", "judge_model"),
            ("judge_reasoning", "judge_reasoning_effort"),
        ):
            setattr(args, argument_name, existing_manifest[manifest_name])
        args.arms = list(existing_manifest["arms"])
        timeout_settings = existing_manifest.get("timeouts_seconds") or {}
        retry_settings = existing_manifest.get("configured_retries") or {}
        args.timeout = int(timeout_settings.get("alan", args.timeout))
        args.worker_timeout = int(timeout_settings.get("worker", args.worker_timeout))
        args.judge_timeout = int(timeout_settings.get("judge", args.judge_timeout))
        args.retries = int(retry_settings.get("alan_new_session", args.retries))
        args.worker_retries = int(retry_settings.get("worker", args.worker_retries))
        args.judge_retries = int(retry_settings.get("judge", args.judge_retries))
        cases_source = run_dir / str(existing_manifest["cases_snapshot"])
        if args.case_id:
            raise ValueError("--resume continues every incomplete case; do not combine it with --case-id")
    else:
        cases_source = Path(args.cases).resolve()
    cases_bytes = cases_source.read_bytes()
    cases_payload = json.loads(cases_bytes.decode("utf-8"))
    cases = cases_payload["cases"]
    if not cases:
        raise ValueError("Case file contains no cases")
    case_ids_in_file = [str(case.get("Case") or "") for case in cases]
    if any(not case_id for case_id in case_ids_in_file):
        raise ValueError("Every case must have a non-empty Case ID")
    if len(case_ids_in_file) != len(set(case_ids_in_file)):
        raise ValueError("Case file contains duplicate Case IDs")
    if resuming:
        selected_ids = existing_manifest.get("case_ids")
        if (not isinstance(selected_ids, list) or not selected_ids
                or not all(isinstance(value, str) and value for value in selected_ids)
                or len(set(selected_ids)) != len(selected_ids)):
            raise ValueError("Cannot resume: manifest must contain unique selected case IDs")
        by_id = {case["Case"]: case for case in cases}
        missing = set(selected_ids) - by_id.keys()
        if missing:
            raise ValueError(f"Cannot resume: selected cases missing from snapshot: {sorted(missing)}")
        if existing_manifest.get("case_count_per_arm") != len(selected_ids):
            raise ValueError("Cannot resume: selected case count differs from manifest")
        cases = [by_id[case_id] for case_id in selected_ids]
    if args.case_id:
        requested_ids = set(args.case_id)
        cases = [case for case in cases if case["Case"] in requested_ids]
        missing = sorted(requested_ids - {case["Case"] for case in cases})
        if missing:
            raise ValueError(f"Unknown --case-id values: {missing}")
    if resuming:
        args.separate_worker_audit = bool(existing_manifest.get("separate_worker_audit"))
    extra_inputs = {}
    if args.separate_worker_audit:
        extra_inputs.update({"worker_audit.txt": ROOT / "prompts/worker_audit.txt",
                             "worker_audit_schema.json": ROOT / "schemas/worker_audit.json"})
    if any(behaviour_case(case) for case in cases):
        extra_inputs.update({
            "extra50_behaviour_judge.txt": Path(args.challenge_judge_prompt) if any(dialogue_test(c) for c in cases) else ROOT / "prompts/challenge_judge.txt",
            "extra50_judge_schema.json": Path(args.challenge_judge_schema),
        })
    if resuming:
        assert existing_manifest is not None
        cases_snapshot = cases_source
        raw_prompt = run_dir / str(existing_manifest["raw_prompt_snapshot"])
        worker_prompt = run_dir / str(existing_manifest["worker_prompt_snapshot"])
        worker_prompt_source = worker_prompt
        worker_schema = run_dir / str(existing_manifest["worker_schema_snapshot"])
        judge_prompt = run_dir / str(existing_manifest["judge_prompt_snapshot"])
        judge_schema = run_dir / str(existing_manifest["judge_schema_snapshot"])
        alan_prompt = run_dir / str(existing_manifest["alan_prompt_snapshot"])
        for path, hash_field in (
            (cases_snapshot, "cases_sha256"),
            (raw_prompt, "raw_prompt_sha256"),
            (worker_prompt, "worker_prompt_sha256"),
            (worker_schema, "worker_schema_sha256"),
            (judge_prompt, "judge_prompt_sha256"),
            (judge_schema, "judge_schema_sha256"),
            (alan_prompt, "alan_prompt_sha256"),
        ):
            if not path.is_file() or sha256_file(path) != existing_manifest.get(hash_field):
                raise ValueError(f"Cannot resume: frozen input changed or is missing: {path}")
        alan_provenance = {}
        (run_dir / "STOP_REQUESTED").unlink(missing_ok=True)
    else:
        require_empty_run_dir(run_dir)
        inputs_dir = run_dir / "inputs"
        inputs_dir.mkdir(parents=True, exist_ok=True)
        cases_snapshot = inputs_dir / "pilot_cases.json"
        cases_snapshot.write_bytes(cases_bytes)
        raw_prompt = freeze_file(Path(args.raw_prompt), inputs_dir / "raw_system.txt")
        worker_prompt_source = Path(args.worker_prompt).resolve()
        worker_prompt = freeze_file(worker_prompt_source, inputs_dir / "health_worker_system.txt")
        worker_schema = freeze_file(Path(args.worker_schema), inputs_dir / "health_worker_schema.json")
        judge_prompt = freeze_file(Path(args.judge_prompt), inputs_dir / "judge_system.txt")
        judge_schema = freeze_file(Path(args.judge_schema), inputs_dir / "judge_schema.json")
        alan_prompt, alan_provenance = resolve_alan_prompt_source(
            run_dir,
            local_override=args.alan_prompt,
            git_ref=args.alan_git_ref,
            refresh_github=args.refresh_alan_github,
        )

    new_manifest = {
        "input_isolation": {
            "version": "no-project-instructions-v1",
            "project_doc_max_bytes": 0,
            "scope": "all Codex model roles, initial and resumed calls",
            "invocation_record": "calls/**/invocation.json",
            "limitation": "Codex runtime guidance, skill catalogue, global language preferences and environment metadata may remain",
        },
        "runner_version": RUNNER_VERSION,
        "explicit_configuration": getattr(args, "release_configuration", {}),
        "runtime_code_sha256": {name: sha256_file(HERE / name) for name in ("runner.py", "quality_scoring.py", "runner_defaults.py", "replay_events.py", "extra50_support.py", "separate_audit.py", "case_bank.py")},
        "separate_worker_audit": args.separate_worker_audit,
        "started_at": utc_now(),
        "model": args.model,
        "reasoning_effort": args.reasoning,
        "model_transport": MODEL_TRANSPORT,
        "worker_model": args.worker_model,
        "worker_reasoning_effort": args.worker_reasoning,
        "worker_transport": MODEL_TRANSPORT,
        "arms": args.arms,
        "case_count_per_arm": len(cases),
        "case_ids": [case["Case"] for case in cases],
        "concurrency": args.concurrency,
        "process_id": os.getpid(),
        "stop_mode": "after current model reply",
        "worker": "Direct Terra health worker",
        "worker_prompt_label": "Health worker v1",
        "worker_prompt_source": str(worker_prompt_source),
        "case_filter": "non-gold case filter v1",
        "judge_model": args.judge_model,
        "judge_reasoning_effort": args.judge_reasoning,
        "judge_transport": MODEL_TRANSPORT,
        "judge": f"blinded {args.judge_model} {args.judge_reasoning}",
        "turn_rule": {
            "minimum": MIN_TURNS,
            "normal": NORMAL_TURNS,
            "hard_cap": MAX_TURNS,
            "emergency_exit": "Emergency care must take over now.",
            "action_first_routes": "one immediate terminal reply, or one decisive question with any action that cannot wait then terminal reply",
        },
        "quality_scoring_version": QUALITY_SCORING_VERSION,
        "challenge_index_version": CHALLENGE_INDEX_VERSION,
        "source_cases": str(cases_source),
        "cases_snapshot": str(cases_snapshot.relative_to(run_dir)),
        "cases_sha256": hashlib.sha256(cases_bytes).hexdigest().upper(),
        "workbook_sha256": cases_payload.get("source_workbook_sha256"),
        "raw_prompt_snapshot": str(raw_prompt.relative_to(run_dir)),
        "raw_prompt_sha256": sha256_file(raw_prompt),
        **alan_provenance,
        "alan_version": "v0.2.0",
        "alan_version_date": "2026-09-08",
        "worker_prompt_version": "v1",
        "judge_prompt_version": "v1",
        "judge_prompt_snapshot": str(judge_prompt.relative_to(run_dir)),
        "judge_prompt_sha256": sha256_file(judge_prompt),
        "judge_schema_snapshot": str(judge_schema.relative_to(run_dir)),
        "judge_schema_sha256": sha256_file(judge_schema),
        "worker_prompt_snapshot": str(worker_prompt.relative_to(run_dir)),
        "worker_prompt_sha256": sha256_file(worker_prompt),
        "worker_schema_snapshot": str(worker_schema.relative_to(run_dir)),
        "worker_schema_sha256": sha256_file(worker_schema),
        "worker_reply_limits": {"facts": MAX_WORKER_FACTS, "words": MAX_WORKER_WORDS},
        "timeouts_seconds": {
            "alan": args.timeout,
            "worker": args.worker_timeout,
            "judge": args.judge_timeout,
        },
        "configured_retries": {
            "alan_new_session": args.retries,
            "alan_resume": 0,
            "worker": args.worker_retries,
            "judge": args.judge_retries,
        },
        "worker_integrity_policy": {
            "worker_view": "Terra sees recent dialogue plus every non-gold case fact",
            "release_boundary": "the case filter removes gold fields and hidden stretch targets",
            "mechanical_contract": "code validates non-empty output, fact IDs and the two-fact limit, then logs exact source values",
            "semantic_review": "the post-dialogue judge grades faithful paraphrase, minor distortion, material contamination and false withholding of a direct answer",
            "alan_scoring_validity": "a material worker breach or wrong-route terminal close invalidates Alan scoring; minor worker defects remain valid and separately reported",
            "style": "logged, non-blocking",
            "fact_usage": "logged for worker-integrity review only; never used to judge Alan's clinical answer",
            "maximum_worker_drafts": 2,
        },
        "canonical_alan_files_changed": None,
        "canonical_alan_files_changed_by_runner": False,
        "holdout_used": cases_payload.get("holdout_used"),
        "evaluation_profile": cases_payload.get("evaluation_profile"),
    }
    if extra_inputs:
        if resuming:
            for name, digest in existing_manifest.get("extra_input_sha256", {}).items():
                if name not in extra_inputs or sha256_file(run_dir / "inputs" / name) != digest:
                    raise ValueError("Changed extra-test evaluator input")
            if set(existing_manifest.get("extra_input_sha256", {})) != set(extra_inputs):
                raise ValueError("Missing extra-test evaluator snapshots")
        else:
            for name, source in extra_inputs.items():
                freeze_file(source, run_dir / "inputs" / name)
            new_manifest["extra_input_sha256"] = {name: sha256_file(run_dir / "inputs" / name) for name in extra_inputs}
    if resuming:
        assert existing_manifest is not None
        manifest = existing_manifest
        manifest.setdefault("resume_events", []).append({
            "resumed_at": utc_now(),
            "process_id": os.getpid(),
            "concurrency": args.concurrency,
            "case_ids": [case["Case"] for case in cases],
        })
    else:
        manifest = new_manifest
    write_json(run_dir / "run_manifest.json", manifest)
    write_json(run_dir / "failures.json", [])

    invoker = CodexInvoker(args.model, args.reasoning, args.timeout, args.retries)
    worker_invoker = CodexInvoker(
        args.worker_model,
        args.worker_reasoning,
        args.worker_timeout,
        args.worker_retries,
    )
    judge_invoker = CodexInvoker(
        args.judge_model,
        args.judge_reasoning,
        args.judge_timeout,
        args.judge_retries,
    )
    jobs: list[tuple[dict[str, Any], str]] = []
    for index, case in enumerate(cases):
        if set(args.arms) == {"raw", "full_alan"}:
            arm_order = ("raw", "full_alan") if index % 2 == 0 else ("full_alan", "raw")
        else:
            arm_order = tuple(args.arms)
        jobs.extend((case, arm) for arm in arm_order)

    failures: list[dict[str, str]] = []
    failure_lock = threading.Lock()
    completed_count = 0

    def run_job(case: dict[str, Any], arm: str) -> dict[str, Any]:
        try:
            return run_dialogue(
                case,
                arm,
                run_dir,
                invoker,
                worker_invoker,
                judge_invoker,
                alan_prompt,
                raw_prompt,
                worker_prompt,
                worker_schema,
                judge_prompt,
                judge_schema,
                args.separate_worker_audit,
            )
        except Exception as exc:
            # Persist the failure before this worker can start its next queued case.
            # The live monitor therefore never presents the finished failed case and
            # its successor as simultaneously active when concurrency is one.
            with failure_lock:
                failures.append({"case_id": str(case["Case"]), "arm": arm, "error": repr(exc)})
                write_json(run_dir / "failures.json", failures)
            raise

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = {
            executor.submit(run_job, case, arm): (case["Case"], arm)
            for case, arm in jobs
        }
        for future in concurrent.futures.as_completed(futures):
            case_id, arm = futures[future]
            try:
                result = future.result()
                completed_count += 1
                judgement = result["judgement"]
                with PRINT_LOCK:
                    print(
                        f"[{completed_count:02d}/{len(jobs)}] {case_id} {arm}: "
                        f"verdict={result.get('quality', {}).get('test_check', {}).get('outcome', judgement.get('diagnosis_correct'))} turns={result['turns']} "
                        f"unsafe={int(judgement['serious_unsafe_advice'])}",
                        flush=True,
                    )
            except Exception as exc:  # noqa: BLE001 - preserve every failed job for the receipt
                with PRINT_LOCK:
                    print(f"FAILED {case_id} {arm}: {exc}", file=sys.stderr, flush=True)

    write_json(run_dir / "failures.json", failures)
    summary = build_summary(run_dir, expected_cases=len(cases))
    manifest["finished_at"] = utc_now()
    manifest["completed_dialogues"] = sum(item["n"] for item in summary["arms"].values())
    manifest["failed_dialogues"] = len(failures)
    write_json(run_dir / "run_manifest.json", manifest)
    print(f"Summary: {run_dir / 'SUMMARY.md'}")
    return 1 if failures else 0


def command_summary(args: argparse.Namespace) -> int:
    summary = build_summary(Path(args.run_dir).resolve())
    print(json.dumps(summary["arms"], ensure_ascii=False, indent=2))
    return 0


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Leakage-safe Alan dialogue evaluation runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Extract and freeze selected cases from Alan 200")
    prepare.add_argument("--workbook", default=str(DEFAULT_WORKBOOK))
    prepare.add_argument("--selection-spec", default=str(PILOT_IDS))
    prepare.add_argument("--output", default=str(DEFAULT_CASES))
    prepare.set_defaults(func=command_prepare)

    preflight = subparsers.add_parser(
        "preflight",
        help="Verify the raw, frozen Alan, Terra health-worker and judge routes",
    )
    preflight.add_argument("--model", default=MODEL)
    preflight.add_argument("--cases", default=str(DEFAULT_CASES))
    preflight.add_argument("--worker-prompt", default=str(HEALTH_WORKER_PROMPT))
    preflight.add_argument("--reasoning", default=REASONING)
    preflight.add_argument("--worker-model", default=WORKER_MODEL)
    preflight.add_argument("--worker-reasoning", default=WORKER_REASONING)
    preflight.add_argument("--worker-timeout", type=int, default=120)
    preflight.add_argument("--worker-retries", type=int, default=0)
    preflight.add_argument("--judge-model", default=JUDGE_MODEL)
    preflight.add_argument("--judge-reasoning", default=JUDGE_REASONING)
    preflight.add_argument("--alan-prompt", default=None)
    preflight.add_argument("--alan-git-ref", default=DEFAULT_ALAN_GIT_REF)
    preflight.add_argument("--no-alan-github-refresh", action="store_false", dest="refresh_alan_github")
    preflight.set_defaults(refresh_alan_github=True)
    preflight.add_argument("--timeout", type=int, default=120)
    preflight.add_argument("--retries", type=int, default=0)
    preflight.add_argument("--output-dir", default=str(HERE / "preflight"))
    preflight.set_defaults(func=command_preflight)

    run = subparsers.add_parser("run", help="Run raw and full-Alan paired dialogues and blind judging")
    run.add_argument("--cases", default=str(DEFAULT_CASES))
    run.add_argument(
        "--alan-prompt",
        default=None,
        help="Explicit local prompt override. Omit to use the exact compiled prompt from Spider201866/alan.",
    )
    run.add_argument(
        "--alan-git-ref",
        default=DEFAULT_ALAN_GIT_REF,
        help="Git ref in Spider201866/alan used for the default Alan prompt.",
    )
    run.add_argument(
        "--no-alan-github-refresh",
        action="store_false",
        dest="refresh_alan_github",
        help="Use the existing local origin ref without fetching GitHub first.",
    )
    run.set_defaults(refresh_alan_github=True)
    run.add_argument("--run-dir", default=str(DEFAULT_RUN_DIR))
    run.add_argument(
        "--resume",
        action="store_true",
        help="Continue incomplete cases using the exact frozen inputs and runner version.",
    )
    run.add_argument("--model", default=MODEL)
    run.add_argument("--reasoning", default=REASONING)
    run.add_argument("--worker-model", default=WORKER_MODEL)
    run.add_argument("--worker-reasoning", default=WORKER_REASONING)
    run.add_argument(
        "--worker-prompt",
        default=str(HEALTH_WORKER_PROMPT),
        help="Health-worker system prompt to freeze for this run.",
    )
    run.add_argument("--worker-timeout", type=int, default=120)
    run.add_argument("--worker-retries", type=int, default=0)
    run.add_argument("--judge-model", default=JUDGE_MODEL)
    run.add_argument("--judge-reasoning", default=JUDGE_REASONING)
    run.add_argument("--judge-timeout", type=int, default=180)
    run.add_argument("--judge-retries", type=int, default=0)
    run.add_argument("--arms", nargs="+", choices=["raw", "full_alan"], default=["full_alan"])
    run.add_argument("--separate-worker-audit", action="store_true", help="Audit HW fidelity in a separate gold-free session")
    run.add_argument("--case-id", action="append", help="Run only this case ID; may be repeated")
    run.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Number of simultaneous dialogues. Default 1 keeps live order and reduces run-to-run load variation.",
    )
    run.add_argument("--timeout", type=int, default=180)
    run.add_argument("--retries", type=int, default=0)
    run.set_defaults(func=command_run)

    for command in (run, preflight):
        command.add_argument("--raw-prompt", default=str(RAW_PROMPT))
        command.add_argument("--worker-schema", default=str(HEALTH_WORKER_SCHEMA))
        command.add_argument("--judge-prompt", default=str(JUDGE_PROMPT))
        command.add_argument("--judge-schema", default=str(JUDGE_SCHEMA))
        command.add_argument("--challenge-judge-prompt", default=str(ROOT / "prompts/challenge_judge.txt"))
        command.add_argument("--challenge-judge-schema", default=str(ROOT / "schemas/challenge_judge.json"))

    summary = subparsers.add_parser("summarise", help="Rebuild summary from saved result files")
    summary.add_argument("--run-dir", default=str(DEFAULT_RUN_DIR))
    summary.set_defaults(func=command_summary)
    return parser


def main() -> int:
    args = make_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
