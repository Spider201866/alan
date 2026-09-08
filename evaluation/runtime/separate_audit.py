"""Recorded, separate Alan and HW assessments without changing saved dialogues."""
from __future__ import annotations
import json
from pathlib import Path
import runner
HERE = Path(__file__).resolve().parent.parent

def payloads(case, result):
    clinical = json.loads(runner.judge_payload(case, result['transcript'],
        result.get('authorised_release_log', []), 'saved-dialogue-audit', []))
    clinical.pop('worker_integrity_visible_fact_log', None)
    clinical['separate_worker_audit'] = True
    worker = {'transcript': result['transcript'],
        'worker_visible_fact_log': result.get('worker_visible_fact_log', []),
        'contract': 'at most two directly answering facts; supplied results only'}
    return clinical, worker

def audit(case, result, destination: Path, invoker, paths=None):
    if destination.exists():
        raise ValueError('Audit destinations are immutable; choose a new directory')
    destination.mkdir(parents=True)
    paths = paths or {
        "worker_prompt": HERE / "prompts/worker_audit.txt",
        "worker_schema": HERE / "schemas/worker_audit.json",
        "clinical_prompt": HERE / "prompts/judge.txt",
        "clinical_schema": HERE / "schemas/judge.json",
    }
    clinical, worker = payloads(case, result)
    runner.write_json(destination / 'clinical-input.json', clinical)
    runner.write_json(destination / 'worker-input.json', worker)
    hw_call = invoker.new_session(paths['worker_prompt'],
        json.dumps(worker, ensure_ascii=False), destination / 'worker',
        output_schema=paths['worker_schema'], ephemeral=True)
    hw = json.loads(hw_call['reply'])
    runner.validate_judge_contract(hw, paths['worker_schema'])
    alan_call = invoker.new_session(paths['clinical_prompt'],
        json.dumps(clinical, ensure_ascii=False), destination / 'clinical',
        output_schema=paths['clinical_schema'], ephemeral=True)
    judgement = json.loads(alan_call['reply'])
    runner.validate_judge_contract(judgement, paths['clinical_schema'])
    judgement.update({key: hw[key] for key in ('worker_protocol_difference', 'worker_protocol_reason')})
    judgement = runner.finalise_judgement(judgement, result.get('stop_reason'), case=case)
    record = {'status': 'separate_model_review_requires_adjudication',
        'case_id': case['Case'], 'created_at': runner.utc_now(),
        'original_judgement': result.get('judgement'), 'reviewed_judgement': judgement,
        'worker_evidence': hw['evidence'], 'stop_reason': result.get('stop_reason'),
        'transcript_sha256': runner.sha256_text(json.dumps(result['transcript'], ensure_ascii=False)),
        'calls': {'worker': hw_call, 'clinical': alan_call},
        'prompts': {name: runner.sha256_file(path) for name, path in paths.items()}}
    runner.write_json(destination / 'review.json', record)
    return record
