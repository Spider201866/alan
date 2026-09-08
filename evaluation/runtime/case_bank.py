"""Read the public Excel case bank without any experiment-folder dependency."""
from __future__ import annotations
import copy
import json
from collections import Counter
from pathlib import Path
import runner
ROOT = Path(__file__).resolve().parent.parent


def load_cases(workbook_path=None):
    path = Path(workbook_path or ROOT / 'data/cases.xlsx').resolve()
    wb = runner.load_workbook(path, read_only=True, data_only=False)
    try:
        clinical = [{'domain': domain, **row}
                    for sheet, (domain, width) in runner.CASE_SHEETS.items()
                    for row in runner.extract_rows(wb[sheet], width)]
        stretches = runner.extract_stretches(wb['Stretch Cases'])
        tags = {row['Case']: row for row in runner.extract_rows(wb['Analysis Tags'], 6)}
        raw = list(wb['Extra 50'].iter_rows(min_row=7, max_row=57, values_only=True))
        if len(set(raw[0])) != len(raw[0]): raise ValueError('Duplicate challenge headers')
        extra_rows = [tuple(CHALLENGE_HEADERS)] + [tuple(dict(zip(raw[0], row)).get(key) for key in CHALLENGE_HEADERS) for row in raw[1:]]
        extra = [row[:13] for row in extra_rows[1:]]
    finally:
        wb.close()
    if len(clinical) != 200 or dict(Counter(c['domain'] for c in clinical)) != {'Eye':100,'ENT':50,'Skin':50}:
        raise ValueError('Expected 100 eye, 50 ENT and 50 skin cases')
    for case in clinical:
        case['analysis'] = tags.get(case['Case'], {})
        case['stretch'] = stretches.get(case['Case'])
    challenge = []
    for row in extra:
        cid, group, focus, opening, facts, expected, stop, mode, source, source_id, digest, status, notes = row
        if mode not in {'One reply', 'Dialogue'} or not isinstance(opening,str) or not opening.strip():
            raise ValueError(f'{cid}: missing opening or invalid challenge mode')
        case = {'Case':cid,'domain':'Other','Family code':'EXT','First Line for Alan':opening,
                'Diagnosis':focus,'Management':expected,'Urgency':'Routine','Expected marker':'None',
                'Expected emergency exit':'No','stretch':None,
                'extra_test':{'group':group,'mode':mode,'expected':expected,'stop_rule':stop,'notes':notes}}
        if group == 'Emergency':
            if mode == 'Dialogue':
                for line in str(facts).splitlines():
                    field, value = line.split(':',1)
                    field = {'Local resources / access':runner.RESOURCE_FIELD}.get(field,field)
                    if field not in runner.PATIENT_FIELDS + [runner.RESOURCE_FIELD]:
                        raise ValueError(f'{cid}: invalid patient field {field}')
                    case[field]=value.strip()
        elif group != 'Robustness / security' or mode != 'One reply':
            raise ValueError(f'{cid}: invalid challenge group')
        challenge.append(case)
    apply_challenge_extensions(challenge, extra_rows)
    cases=clinical+challenge
    if len(cases)!=250 or len({c['Case'] for c in cases})!=250:
        raise ValueError('Expected 250 unique case IDs')
    if Counter(c['extra_test']['group'] for c in challenge) != {'Emergency':15,'Robustness / security':35}:
        raise ValueError('Expected 15 emergency and 35 robustness challenges')
    for index, case in enumerate(cases,1):
        case['pilot_sequence']=index
        for field in ('Case','Diagnosis','Management','Urgency','First Line for Alan'):
            if not case.get(field): raise ValueError(f'{case["Case"]}: missing {field}')
        # CaseFilter supplies patient facts only. Gold answers and analysis stay separate.
        for fact in runner.CaseFilter(case).visible_facts():
            if fact['field'] not in runner.allowed_request_fields(case['domain'])+['active_state']:
                raise ValueError(f'{case["Case"]}: gold field reached worker view')
    return cases


def select_cases(cases, selection='all', repeat=1):
    if not isinstance(repeat,int) or not 1 <= repeat <= 100:
        raise ValueError('Repeat must be between 1 and 100')
    if selection in ('all','clinical','challenge'):
        chosen = [c for c in cases if selection=='all' or bool(c.get('extra_test'))==(selection=='challenge')]
    else:
        ids = [part.strip().upper() for part in selection.split(',') if part.strip()]
        if not ids or len(ids)!=len(set(ids)): raise ValueError('Supply unique case IDs')
        by_id={c['Case']:c for c in cases}
        missing=[cid for cid in ids if cid not in by_id]
        if missing: raise ValueError('Unknown cases: '+', '.join(missing))
        chosen=[by_id[cid] for cid in ids]
    result=[]
    for iteration in range(1,repeat+1):
        for position, original in enumerate(chosen,1):
            case=copy.deepcopy(original)
            if repeat>1:
                case.update(Case=f'{original["Case"]}-R{iteration}',source_case_id=original['Case'],repeat=iteration,repeat_position=position)
            case['pilot_sequence']=len(result)+1
            result.append(case)
    return result


def apply_challenge_extensions(cases, rows):
    assert rows[0][14] == "Planned test depth" and rows[0][27] == "Adapter contract"
    assert rows[0][28:32] == ("Execution opening — runner", "Inject after Alan reply",
                              "Injected test message — driver", "Assessment target — judge")
    for case, row in zip(cases, rows[1:], strict=True):
        assert row[0] == case["Case"] and row[27] == "alan-challenge-v1", row[0]
        challenge_objective = case["extra_test"]["expected"]
        mode, bank, release, challenge, checks, stop, provenance, previous, readiness = row[14:23]
        domain, context, pressure, completion, contract = row[23:28]
        execution_opening, inject_after, injected_message, assessment_target = row[28:32]
        assert mode in {"Opening check", "Staged check", "Whole dialogue", "Emergency short"}
        assert domain in {"Eye", "ENT", "Skin", "Other"}
        expected_policy = {"Opening check": {"First Alan reply"},
                           "Staged check": {"Alan ending", "Resolved clarification"},
                           "Whole dialogue": {"Alan ending"}, "Emergency short": {"Emergency ending"}}
        assert completion in expected_policy[mode], case["Case"]
        assert execution_opening
        source_opening = case["First Line for Alan"]
        case["First Line for Alan"] = execution_opening
        case["domain"] = domain
        case["extra_test"].update(contract=contract, planned_mode=mode, expected=checks,
                                  challenge_objective=challenge_objective, stop_rule=stop,
                                  clarification_context=context or "", pressure=pressure or "",
                                  challenge=injected_message or "", completion_policy=completion,
                                  source_opening=source_opening, injection_after=int(inject_after or 0),
                                  assessment_target=assessment_target)
        # The verbose release plan, provenance and previous verdict stay audit-only in the workbook.
        # They are never forwarded to either participant or to the new judge.
        allowed = runner.PATIENT_FIELDS + runner.CHECK_FIELDS[domain] + [runner.RESOURCE_FIELD]
        if row[32]:
            assert rows[0][32] == 'HW fact bank after injection — no gold'
            assert mode == 'Staged check' and inject_after and injected_message
            after = {}
            for line in row[32].splitlines():
                field, value = line.split(':', 1)
                assert field in allowed and value.strip() and field not in after
                after[field] = value.strip()
            case['extra_test']['facts_after_injection'] = after
        if mode in {"Staged check", "Whole dialogue"}:
            for line in bank.splitlines():
                field, value = line.split(":", 1)
                field = {"Local resources / access": runner.RESOURCE_FIELD}.get(field, field)
                assert field in allowed and value.strip(), (case["Case"], field)
                assert field not in case, (case["Case"], "duplicate field", field)
                case[field] = value.strip()
        elif mode == "Staged check":
            raise AssertionError("Staged checks require a fact bank")
        elif mode == "Opening check":
            assert not inject_after and not injected_message and not context and not pressure
        if mode == "Staged check":
            assert inject_after in {1, 2, 3, 4} and injected_message and not pressure
        elif mode != "Whole dialogue":
            assert not inject_after and not injected_message
        visible = runner.CaseFilter(case).visible_facts()
        assert all(f["field"] in allowed for f in visible)
        if mode == "Opening check":
            assert not visible
    counts = Counter(c["extra_test"]["planned_mode"] for c in cases)
    assert counts == {"Opening check": 8, "Staged check": 20, "Whole dialogue": 7, "Emergency short": 15}
    staged = [c for c in cases if c["extra_test"]["planned_mode"] == "Staged check"]
    assert Counter(c["extra_test"]["injection_after"] for c in staged) == {1: 5, 2: 5, 3: 5, 4: 5}
    assert [c["Case"] for c in staged if c["extra_test"]["completion_policy"] == "Resolved clarification"] == ["EXT-R32"]


CHALLENGE_HEADERS = ['Test ID', 'Group', 'Focus', 'First Line for Alan', 'HW facts if asked', 'Expected behaviour — judge only', 'Stop rule — runner only', 'Test mode', 'Original source file', 'Original source ID', 'Source SHA256', 'Status', 'Audit notes', 'ID count', 'Planned test depth', 'HW fact bank — no gold', 'When facts are released', 'Second challenge — test driver only', 'Conversation checks — judge only', 'Stop and evidence rules', 'Follow-up source / changes', 'First-run result and human review', 'Conversation readiness', 'Fact domain — runner', 'Clarification context — HW only', 'One-time pressure after first HW reply', 'Completion policy — runner', 'Adapter contract', 'Execution opening — runner', 'Inject after Alan reply', 'Injected test message — driver', 'Assessment target — judge', 'HW fact bank after injection — no gold']
