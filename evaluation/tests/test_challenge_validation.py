"""Assessment routing and scripted-driver receipts are separate from HW speech."""
import copy
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
import runner
from case_bank import load_cases
from extra50_support import behaviour_quality, test_mode
from validate_run import validate_challenge_assessment, validate_worker_route

class ChallengeValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.cases=[case for case in load_cases() if case.get('extra_test')]

    def test_challenge_uses_its_own_score_and_schema(self):
        case=self.cases[0]
        raw={'objective_grade':'met','safety_integrity_grade':'sound','process_completion_grade':'sound',
             'run_evaluable':True,'reason':'Objective met.','evidence':'Immediate action.','serious_unsafe_advice':False}
        transcript=[{'role':'alan','text':'Arrange emergency care now.'}]
        quality=behaviour_quality(case,raw,'terminal_emergency_exit',transcript)
        result={'transcript':transcript,'stop_reason':'terminal_emergency_exit','quality':quality,
                'judgement':dict(raw,outcome=quality['test_check']['outcome'],judge_reason=raw['reason'],run_valid=True)}
        errors=[]
        validate_challenge_assessment('test',case,result,ROOT/'schemas/challenge_judge.json',errors)
        self.assertEqual(errors,[])
        for mutate in (lambda r:r['quality']['challenge_index'].update(score=1),
                       lambda r:r['judgement'].update(run_valid=False),
                       lambda r:r['judgement'].update(diagnosis_correct=True)):
            broken=copy.deepcopy(result);mutate(broken);errors=[]
            validate_challenge_assessment('test',case,broken,ROOT/'schemas/challenge_judge.json',errors)
            self.assertTrue(errors)

    @staticmethod
    def receipt(case):
        turns=6
        cf=runner.CaseFilter(case)
        transcript=[{'role':'health_worker','text':case['First Line for Alan'],'opening':True}]
        logs=[];views=[];words=[]
        extra=case['extra_test']
        injection=int(extra.get('injection_after') or 1) if test_mode(case) in {'Staged check','Boundary challenge'} else None
        question='Describe the patient.'
        for turn in range(1,turns+1):
            transcript.append({'role':'alan','text':question,'turn':turn})
            if turn==turns: break
            if turn==injection:
                cf.apply_injected_state()
                transcript.append({'role':'health_worker','text':extra['challenge'],'after_alan_turn':turn,'scripted_challenge':True})
                continue
            offered=cf.view_for_turn(question)
            visible=cf.visible_facts()
            usage=runner.worker_fact_usage(offered.offered,[])
            reply='Not checked'
            views.append({'alan_turn':turn,'visible_facts':visible,'offered_facts':offered.offered,
                          'used_fact_ids':[],'fact_usage':usage,'view_mode':'all_non_gold_case_facts','response_reason':offered.response_reason})
            logs.append({'alan_turn':turn,'alan_message':question,'worker_reply':reply,'released':[],
                         'state_transition':offered.state_transition,'fact_usage':usage,'worker_payload_sha256':'synthetic',
                         'worker_reply_words':runner.worker_word_count(reply)})
            entry={'role':'health_worker','text':reply,'after_alan_turn':turn}
            pressure=extra.get('pressure','') if turn==1 else ''
            if pressure: entry.update(model_reply=reply,appended_pressure=pressure,text=reply+' '+pressure)
            transcript.append(entry);words.append(runner.worker_word_count(reply))
        return {'turns':turns,'transcript':transcript,'authorised_release_log':logs,'worker_visible_fact_log':views,
                'state_transition_count':sum(log['state_transition'] is not None for log in logs),
                'worker_word_count_version':2,'alan_reply_word_counts':[runner.word_count(question)]*turns,'worker_reply_word_counts':words}

    def test_all_fifty_driver_contracts_validate_without_counting_driver_text_as_hw(self):
        for case in self.cases:
            with self.subTest(case=case['Case']):
                errors=[]
                validate_worker_route(case['Case'],case,self.receipt(case),errors)
                self.assertEqual(errors,[])

    def test_tampered_script_is_rejected(self):
        case=next(c for c in self.cases if test_mode(c)=='Staged check')
        receipt=self.receipt(case)
        scripted=next(m for m in receipt['transcript'] if m.get('scripted_challenge'))
        scripted['text']='Unauthorised test driver text'
        errors=[];validate_worker_route('test',case,receipt,errors)
        self.assertTrue(any('scripted challenge' in e for e in errors))

if __name__=='__main__':unittest.main()
