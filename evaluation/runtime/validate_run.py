from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import runner
from extra50_support import behaviour_case, behaviour_quality, dialogue_test, test_mode


REQUIRED_JUDGE_KEYS = {
    "alan_primary_diagnosis",
    "diagnosis_correct",
    "equivalence_used",
    "evidence_sufficient_before_differentials",
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
    "worker_protocol_reason",
    "worker_protocol_failure",
    "marker_appropriate",
    "marker_repetition_appropriate",
    "judge_reason",
    "run_valid",
    "deployable_pass",
}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def snapshot_path(run_dir: Path, manifest: dict[str, Any], field: str) -> Path | None:
    value = manifest.get(field)
    if not value:
        return None
    path = Path(str(value))
    return path.resolve() if path.is_absolute() else (run_dir / path).resolve()


def verify_snapshot(
    run_dir: Path,
    manifest: dict[str, Any],
    path_field: str,
    hash_field: str,
    errors: list[str],
) -> Path | None:
    path = snapshot_path(run_dir, manifest, path_field)
    if path is None:
        fail(errors, f"Manifest is missing {path_field}")
    elif not path.is_file():
        fail(errors, f"Frozen input is missing: {path}")
    elif manifest.get(hash_field) != runner.sha256_file(path):
        fail(errors, f"Frozen input hash mismatch: {path_field}")
    return path


def audit_codex_events(
    run_dir: Path,
    expected_calls: int,
    errors: list[str],
) -> tuple[int, Counter[str]]:
    event_logs = sorted((run_dir / "calls").glob("**/events_attempt_*.jsonl"))
    item_types: Counter[str] = Counter()
    completed_turns = 0
    for path in event_logs:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                fail(errors, f"{path.relative_to(run_dir)}:{line_number}: invalid event JSON")
                continue
            if event.get("type") == "turn.completed":
                completed_turns += 1
            if event.get("type") == "item.completed":
                item = event.get("item")
                if isinstance(item, dict) and item.get("type"):
                    item_types[str(item["type"])] += 1

    if completed_turns != expected_calls:
        fail(errors, f"Expected {expected_calls} completed Codex calls, found {completed_turns}")
    forbidden = {
        name: count for name, count in item_types.items()
        if name not in {"agent_message", "reasoning"}
    }
    if forbidden:
        fail(errors, f"Codex used disallowed tools or item types: {forbidden}")
    return completed_turns, item_types


def validate_worker_route(
    key: str,
    case: dict[str, Any],
    result: dict[str, Any],
    errors: list[str],
) -> int:
    transcript = result.get("transcript") or []
    # Preserve historical receipts: v1 counters also removed numeric HW facts.
    count_worker = runner.worker_word_count if result.get("worker_word_count_version", 1) == 2 else runner.word_count
    if not transcript or transcript[0] != {
        "role": "health_worker",
        "text": case["First Line for Alan"],
        "opening": True,
    }:
        fail(errors, f"{key}: opening is not the exact frozen First Line for Alan")

    alan_entries = [item for item in transcript if item.get("role") == "alan"]
    worker_entries = [
        item for item in transcript
        if item.get("role") == "health_worker" and not item.get("opening")
    ]
    turns = int(result.get("turns", 0))
    if [item.get("turn") for item in alan_entries] != list(range(1, turns + 1)):
        fail(errors, f"{key}: Alan turns are not consecutive")
    if [item.get("after_alan_turn") for item in worker_entries] != list(range(1, turns)):
        fail(errors, f"{key}: worker replies do not follow turns 1..turns-1")

    extra = case.get("extra_test", {})
    injection_turn = (int(extra.get("injection_after") or 1)
                      if dialogue_test(case) and test_mode(case) in {"Staged check", "Boundary challenge"} else None)
    scripted = [entry for entry in worker_entries if entry.get("scripted_challenge")]
    expected_script_count = int(injection_turn is not None and turns > injection_turn)
    if len(scripted) != expected_script_count:
        fail(errors, f"{key}: scripted challenge count differs from its contract")
    for entry in scripted:
        if entry.get("after_alan_turn") != injection_turn or entry.get("text") != extra.get("challenge"):
            fail(errors, f"{key}: scripted challenge differs from the frozen input")
    worker_entries = [entry for entry in worker_entries if not entry.get("scripted_challenge")]
    for entry in worker_entries:
        pressure = extra.get("pressure", "") if entry.get("after_alan_turn") == 1 and dialogue_test(case) else ""
        if pressure:
            if entry.get("appended_pressure") != pressure or entry.get("text") != str(entry.get("model_reply", "")) + " " + pressure:
                fail(errors, f"{key}: appended pressure differs from the frozen input")
        elif entry.get("appended_pressure") or entry.get("model_reply") is not None:
            fail(errors, f"{key}: unexpected appended pressure")

    logs = result.get("authorised_release_log") or []
    views = result.get("worker_visible_fact_log") or []
    if len(logs) != len(worker_entries) or len(views) != len(worker_entries):
        fail(errors, f"{key}: transcript, release and visible-view lengths differ")

    replay = runner.CaseFilter(case)
    transition_count = 0
    stretch = case.get("stretch")
    target_fields = {
        part.strip() for part in str(stretch["Target field(s)"]).split(";")
    } if stretch else set()

    # Only explicitly authored unchanged atoms may survive a replaced field.
    unchanged_facts = [
        atom
        for field, value in (stretch or {}).get("Unchanged facts", {}).items()
        if field in target_fields and field not in runner.GOLD_FIELDS
        for atom in runner.atomic_facts(field, str(value))
    ]

    for log, view, worker_entry in zip(logs, views, worker_entries):
        turn = int(log.get("alan_turn", 0))
        if turn != int(view.get("alan_turn", 0)) or turn != int(worker_entry.get("after_alan_turn", 0)):
            fail(errors, f"{key}: turn {turn} logs do not align")
            continue
        if injection_turn is not None and turn > injection_turn and not replay.injection_applied:
            replay.apply_injected_state()
        if log.get("worker_reply") != worker_entry.get("model_reply", worker_entry.get("text")):
            fail(errors, f"{key} A{turn}: transcript differs from the worker log")

        alan_message = str(log.get("alan_message") or "")
        response_reason = view.get("response_reason")
        if response_reason == "terminal_resource_check":
            replayed = replay.terminal_resource_reply(alan_message)
        else:
            replayed = replay.view_for_turn(alan_message)
        if replayed is None:
            fail(errors, f"{key} A{turn}: resource check does not replay")
            continue
        visible = view.get("visible_facts") or []
        offered = view.get("offered_facts") or visible
        if view.get("view_mode") != "all_non_gold_case_facts":
            fail(errors, f"{key} A{turn}: wrong worker-view mode")
        if visible != replay.visible_facts():
            fail(errors, f"{key} A{turn}: visible case view does not replay")
        if offered != replayed.offered:
            fail(errors, f"{key} A{turn}: worker offer does not replay")
        if log.get("state_transition") != replayed.state_transition:
            fail(errors, f"{key} A{turn}: stretch transition does not replay")
        if log.get("state_transition") is not None:
            transition_count += 1

        visible_by_id = {str(item.get("id")): item for item in visible}
        offered_by_id = {str(item.get("id")): item for item in offered}
        if len(visible_by_id) != len(visible):
            fail(errors, f"{key} A{turn}: duplicate visible fact IDs")
        for fact in visible:
            field = fact.get("field")
            if field in runner.GOLD_FIELDS or (field in target_fields and fact not in unchanged_facts):
                fail(errors, f"{key} A{turn}: hidden field entered the worker view")
            if field == "active_state" and not stretch:
                fail(errors, f"{key} A{turn}: active state on a non-stretch case")

        used_ids = [str(value) for value in view.get("used_fact_ids", [])]
        if len(used_ids) != len(set(used_ids)):
            fail(errors, f"{key} A{turn}: duplicate used fact IDs")
        if len(used_ids) > runner.MAX_WORKER_FACTS:
            fail(errors, f"{key} A{turn}: too many used facts")
        if any(value not in offered_by_id for value in used_ids):
            fail(errors, f"{key} A{turn}: used fact ID is outside the worker offer")
        expected_usage = runner.worker_fact_usage(offered, used_ids)
        if view.get("fact_usage") != expected_usage or log.get("fact_usage") != expected_usage:
            fail(errors, f"{key} A{turn}: fact-usage receipt is wrong")

        source_facts = [offered_by_id[value] for value in used_ids if value in offered_by_id]
        released = log.get("released") or []
        if len(released) != len(source_facts):
            fail(errors, f"{key} A{turn}: judge release-log length is wrong")
        for released_fact, source_fact in zip(released, source_facts):
            if released_fact.get("fact_id") != source_fact.get("id"):
                fail(errors, f"{key} A{turn}: released fact ID is wrong")
            if released_fact.get("field") != source_fact.get("field"):
                fail(errors, f"{key} A{turn}: released field is wrong")
            if "worker_reply" in released_fact:
                if released_fact.get("value") != source_fact.get("value"):
                    fail(errors, f"{key} A{turn}: judge log changed the authorised source value")
                if released_fact.get("worker_reply") != log.get("worker_reply"):
                    fail(errors, f"{key} A{turn}: judge log changed the spoken worker reply")
            elif released_fact.get("value") != log.get("worker_reply"):
                fail(errors, f"{key} A{turn}: legacy judge log changed the spoken worker reply")

        if not log.get("worker_payload_sha256"):
            fail(errors, f"{key} A{turn}: worker payload hash is missing")
        if log.get("worker_reply_words") != count_worker(str(log.get("worker_reply") or "")):
            fail(errors, f"{key} A{turn}: stale worker word count")
        for error in runner.health_worker_contract_errors(
            str(log.get("worker_reply") or ""),
            used_ids,
            offered,
        ):
            fail(errors, f"{key} A{turn}: {error}")

    if result.get("state_transition_count") != transition_count:
        fail(errors, f"{key}: recorded transition count is inconsistent")
    if result.get("worker_interpretation_calls"):
        fail(errors, f"{key}: obsolete interpretation calls were recorded")
    if [runner.word_count(str(item.get("text") or "")) for item in alan_entries] != result.get("alan_reply_word_counts"):
        fail(errors, f"{key}: Alan word counts are stale")
    if [count_worker(str(item.get("model_reply", item.get("text")) or "")) for item in worker_entries] != result.get("worker_reply_word_counts"):
        fail(errors, f"{key}: worker word counts are stale")
    return transition_count



def validate_challenge_assessment(key, case, result, schema_path, errors):
    judgement = result.get("judgement") or {}
    derived = {"outcome", "judge_reason", "run_valid"}
    raw = {name: value for name, value in judgement.items() if name not in derived}
    try:
        runner.validate_judge_contract(raw, schema_path)
        expected = behaviour_quality(case, raw, result.get("stop_reason"), result.get("transcript") or [])
    except (ValueError, runner.CodexError, OSError) as exc:
        fail(errors, f"{key}: invalid challenge assessment: {exc}")
        return
    expected_derived = {"outcome": expected["test_check"]["outcome"],
                        "judge_reason": raw["reason"], "run_valid": expected["challenge_index"]["applicable"]}
    for name, value in expected_derived.items():
        if judgement.get(name) != value:
            fail(errors, f"{key}: {name} derivation is wrong")
    if result.get("quality") != expected:
        fail(errors, f"{key}: challenge score is stale or irreproducible")


def validate(run_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    failures = json.loads((run_dir / "failures.json").read_text(encoding="utf-8"))
    results = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((run_dir / "results").glob("*/*.json"))
    ]

    if failures:
        fail(errors, f"failures.json is not empty: {failures}")
    current_runner_format = manifest.get("runner_version") == runner.RUNNER_VERSION
    current_scoring_format = manifest.get("quality_scoring_version") == runner.QUALITY_SCORING_VERSION
    if not current_runner_format:
        warnings.append(
            f"Historical runner version preserved: {manifest.get('runner_version')} != {runner.RUNNER_VERSION}"
        )
    if manifest.get("worker_interpretation_prompt_snapshot"):
        fail(errors, "Obsolete health-worker interpretation prompt is active")
    if not current_scoring_format:
        warnings.append(
            f"Historical quality score preserved: {manifest.get('quality_scoring_version')} != "
            f"{runner.QUALITY_SCORING_VERSION}"
        )
    for field in ("model_transport", "worker_transport", "judge_transport"):
        if manifest.get(field) != runner.MODEL_TRANSPORT:
            fail(errors, f"Manifest {field} is not the recorded {runner.MODEL_TRANSPORT} route")

    cases_path = verify_snapshot(run_dir, manifest, "cases_snapshot", "cases_sha256", errors)
    verify_snapshot(run_dir, manifest, "raw_prompt_snapshot", "raw_prompt_sha256", errors)
    alan_prompt = verify_snapshot(run_dir, manifest, "alan_prompt_snapshot", "alan_prompt_sha256", errors)
    for path_field, hash_field in (
        ("worker_prompt_snapshot", "worker_prompt_sha256"),
        ("worker_schema_snapshot", "worker_schema_sha256"),
        ("judge_prompt_snapshot", "judge_prompt_sha256"),
        ("judge_schema_snapshot", "judge_schema_sha256"),
    ):
        verify_snapshot(run_dir, manifest, path_field, hash_field, errors)

    judge_schema_path = snapshot_path(run_dir, manifest, "judge_schema_snapshot")
    saved_judge_schema = json.loads(judge_schema_path.read_text(encoding="utf-8")) if judge_schema_path and judge_schema_path.is_file() else None
    expected_judge_keys = (set(saved_judge_schema["required"]) | {
        "urgency_correct", "management_adequate", "worker_protocol_failure",
        "run_valid", "deployable_pass", "assessment_kind", "assessment_objective_met", "test_fidelity_valid",
    }) if saved_judge_schema else REQUIRED_JUDGE_KEYS
    case_map: dict[str, dict[str, Any]] = {}
    if cases_path and cases_path.is_file():
        cases = json.loads(cases_path.read_text(encoding="utf-8"))["cases"]
        case_map = {case["Case"]: case for case in cases}
    if alan_prompt and manifest.get("alan_source_type") == "github":
        if manifest.get("alan_source") != runner.ALAN_GITHUB_URL:
            fail(errors, "Alan GitHub repository does not match the canonical source")
        commit = manifest.get("alan_git_commit")
        git_path = manifest.get("alan_git_path")
        if not commit or not git_path:
            fail(errors, "GitHub Alan prompt provenance is incomplete")
        else:
            try:
                tracked = runner.git_command("show", f"{commit}:{git_path}", binary=True)
                if tracked != alan_prompt.read_bytes():
                    fail(errors, "Frozen Alan prompt differs from its recorded Git commit")
            except runner.CodexError as exc:
                fail(errors, f"Could not verify recorded Alan Git commit: {exc}")

    arms = list(manifest.get("arms") or [])
    case_ids = list(manifest.get("case_ids") or [])
    expected_keys = {(case_id, arm) for case_id in case_ids for arm in arms}
    observed_keys = {(str(row.get("case_id")), str(row.get("arm"))) for row in results}
    if observed_keys != expected_keys:
        fail(errors, f"Result set differs from manifest: expected {sorted(expected_keys)}, got {sorted(observed_keys)}")

    expected_codex_calls = 0
    transition_counter: Counter[str] = Counter()
    recomputed_diagnosis: Counter[str] = Counter()
    recomputed_deployable: Counter[str] = Counter()
    for result in results:
        key = f"{result.get('case_id')}/{result.get('arm')}"
        case = case_map.get(str(result.get("case_id")))
        if not case:
            fail(errors, f"{key}: case is absent from the frozen input")
            continue
        if result.get("runner_version") != manifest.get("runner_version"):
            fail(errors, f"{key}: runner version differs from the manifest")
        for result_field, manifest_field in (
            ("model", "model"),
            ("reasoning_effort", "reasoning_effort"),
            ("worker_model", "worker_model"),
            ("worker_reasoning_effort", "worker_reasoning_effort"),
            ("judge_model", "judge_model"),
            ("judge_reasoning_effort", "judge_reasoning_effort"),
        ):
            if result.get(result_field) != manifest.get(manifest_field):
                fail(errors, f"{key}: {result_field} differs from the manifest")
        for field in ("model_transport", "worker_transport", "judge_transport"):
            if result.get(field) != manifest.get(field):
                fail(errors, f"{key}: wrong or missing {field}")

        expected_prompt_hash = (
            manifest["raw_prompt_sha256"]
            if result["arm"] == "raw"
            else manifest["alan_prompt_sha256"]
        )
        if result.get("prompt_sha256") != expected_prompt_hash:
            fail(errors, f"{key}: prompt hash does not match its arm")
        if result.get("worker_prompt_sha256") != manifest.get("worker_prompt_sha256"):
            fail(errors, f"{key}: worker prompt hash mismatch")
        if not result.get("started_at") or not isinstance(result.get("elapsed_ms"), (int, float)) or result["elapsed_ms"] <= 0:
            fail(errors, f"{key}: missing or invalid end-to-end timing")
        turns = int(result.get("turns", 0))
        valid_turn_count = (
            1 <= turns <= 2
            if runner.expects_emergency_exit(case) and not behaviour_case(case)
            else (1 if behaviour_case(case) else runner.MIN_TURNS) <= turns <= runner.MAX_TURNS
        )
        # A faithfully recorded wrong-route exit is a model outcome, not corrupt data.
        if result.get("stop_reason") == "wrong_route_terminal":
            valid_turn_count = 1 <= turns <= runner.MAX_TURNS
        if (
            result.get("stop_reason") == "terminal_closing"
            and not runner.expects_emergency_exit(case)
            and 1 <= turns < runner.MIN_TURNS
        ):
            # The runner accepts explicit endings before MIN_TURNS. Preserve the
            # recorded model outcome, but require a separate staging review.
            valid_turn_count = True
            warnings.append(f"{key}: explicit closing after {turns} replies; review stage discipline")
        if not valid_turn_count:
            fail(errors, f"{key}: invalid turn count {result.get('turns')}")

        transition_counter[key] = validate_worker_route(key, case, result, errors)
        judgement = result.get("judgement", {})
        is_challenge = behaviour_case(case)
        if is_challenge:
            schema_path = run_dir / "inputs/extra50_judge_schema.json"
            validate_challenge_assessment(key, case, result, schema_path, errors)
        elif current_runner_format and set(judgement) != expected_judge_keys:
            fail(errors, f"{key}: judge keys mismatch")
        if current_runner_format and not is_challenge:
            expected_judgement = runner.finalise_judgement(
                dict(judgement),
                stop_reason=result.get("stop_reason"),
                case=case,
            )
            for derived_field in (
                "urgency_correct", "management_adequate", "worker_protocol_failure",
                "run_valid", "deployable_pass", "assessment_kind", "assessment_objective_met", "test_fidelity_valid",
            ):
                if judgement.get(derived_field) != expected_judgement.get(derived_field):
                    fail(errors, f"{key}: {derived_field} derivation is wrong")
        if is_challenge:
            pass  # Checked above with its own frozen contract and Challenge Index.
        elif current_scoring_format:
            expected_quality = runner.build_quality_metrics(
                case,
                result["arm"],
                result.get("transcript") or [],
                judgement,
            )
            if result.get("quality") != expected_quality:
                fail(errors, f"{key}: quality score is stale or irreproducible")
        else:
            saved_quality = result.get("quality") or {}
            saved_version = saved_quality.get("version")
            manifest_version = manifest.get("quality_scoring_version")
            if saved_version == manifest_version:
                pass
            elif saved_version == runner.QUALITY_SCORING_VERSION:
                history = result.get("rescoring_history") or []
                preserved_original = any(
                    isinstance(entry, dict)
                    and isinstance(entry.get("quality"), dict)
                    and entry["quality"].get("version") == manifest_version
                    for entry in history
                )
                if not preserved_original:
                    fail(errors, f"{key}: rescored quality does not preserve the manifest version")
                expected_quality = runner.build_quality_metrics(
                    case,
                    result["arm"],
                    result.get("transcript") or [],
                    judgement,
                )
                if saved_quality != expected_quality:
                    fail(errors, f"{key}: rescored quality is stale or irreproducible")
            else:
                fail(errors, f"{key}: saved quality version differs from the manifest")

        if not current_scoring_format or not result.get("quality", {}).get("screening_objective"):
            recomputed_diagnosis[result["arm"]] += int(bool(judgement.get("diagnosis_correct")))
        recomputed_deployable[result["arm"]] += int(bool(judgement.get("deployable_pass")))
        expected_codex_calls += len(result.get("model_calls") or [])
        expected_codex_calls += len(result.get("worker_calls") or [])
        rescore_calls = result.get("rescore_calls") or []
        rescore_call_dirs = [
            str(call.get("call_dir") or f"missing:{index}")
            for index, call in enumerate(rescore_calls)
            if isinstance(call, dict)
        ]
        unique_rescore_call_dirs = set(rescore_call_dirs)
        expected_codex_calls += len(unique_rescore_call_dirs)
        if len(unique_rescore_call_dirs) != len(rescore_call_dirs):
            warnings.append(
                f"{key}: historical rejudges reused an evidence directory; only the latest call is preserved"
            )
        expected_codex_calls += 1
        separate_audit = result.get("separate_worker_audit") or {}
        if separate_audit:
            worker_audit_call = separate_audit.get("calls", {}).get("worker", {})
            if not worker_audit_call.get("thread_id"):
                fail(errors, f"{key}: missing separate HW-auditor call receipt")
            expected_codex_calls += 1
        elif manifest.get("separate_worker_audit") and not runner.behaviour_case(case):
            fail(errors, f"{key}: missing separate HW audit")
        if result.get("checker_calls") or any(
            log.get("checker_results")
            for log in result.get("authorised_release_log") or []
        ):
            fail(errors, f"{key}: obsolete reply-referee evidence was recorded")

    for arm in arms:
        displayed = summary.get("arms", {}).get(arm, {})
        if displayed.get("n", 0) != sum(result.get("arm") == arm for result in results):
            fail(errors, f"{arm}: summary result count is stale")
        if displayed.get("diagnosis_correct") != recomputed_diagnosis[arm]:
            fail(errors, f"{arm}: summary diagnosis count is stale")
        if displayed.get("deployable_pass") != recomputed_deployable[arm]:
            fail(errors, f"{arm}: summary deployable count is stale")
    expected_pairs = len(case_ids) if {"raw", "full_alan"}.issubset(set(arms)) else 0
    if summary.get("paired", {}).get("complete_pairs") != expected_pairs:
        fail(errors, "Summary paired count is stale")
    if (run_dir / "INVALID_RUN.md").exists():
        fail(errors, "Run directory is explicitly marked invalid")

    completed_calls, item_types = audit_codex_events(run_dir, expected_codex_calls, errors)
    report = {
        "validator": "alan-dialogue-run-validator-v1",
        "run_dir": str(run_dir.resolve()),
        "result_count": len(results),
        "expected_result_count": len(expected_keys),
        "pair_count": expected_pairs,
        "observed_stretch_transitions": sum(transition_counter.values()),
        "completed_codex_calls": completed_calls,
        "codex_item_types": dict(item_types),
        "diagnosis_correct": dict(recomputed_diagnosis),
        "deployable_pass": dict(recomputed_deployable),
        "errors": errors,
        "warnings": warnings,
        "status": "PASS" if not errors else "FAIL",
    }
    runner.write_json(run_dir / "VALIDATION.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    report = validate(args.run_dir.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
