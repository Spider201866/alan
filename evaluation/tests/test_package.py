"""Portable package and data-boundary regressions. No model calls."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
sys.path.insert(0,str(ROOT/'viewer'))
sys.path.insert(0,str(ROOT))
import runner, case_bank, release_config, monitor_server, harness
from extra50_support import behaviour_payload, dialogue_stop


class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.cases=case_bank.load_cases()

    def test_case_bank_counts_and_challenge_designs(self):
        from collections import Counter
        self.assertEqual(len(self.cases),250)
        self.assertEqual(len({c['Case'] for c in self.cases}),250)
        extra=[c for c in self.cases if c.get('extra_test')]
        self.assertEqual(Counter(c['extra_test']['planned_mode'] for c in extra),{'Opening check':8,'Staged check':20,'Whole dialogue':7,'Emergency short':15})
        self.assertEqual(sum(bool(c.get('assessment')) for c in self.cases),1)

    def test_no_original_file_is_needed_for_challenges(self):
        extra=[c for c in self.cases if c.get('extra_test')]
        for case in extra:
            self.assertNotIn('source',case['extra_test'])
            self.assertNotIn('source_sha256',case['extra_test'])
            self.assertTrue(json.loads(behaviour_payload(case,[]))['assessment_guidance'])
        self.assertFalse((ROOT/'data/challenge_references.json').exists())

    def test_repeats_keep_rounds_and_source_identity(self):
        repeated=case_bank.select_cases(self.cases,'EYE-025,DER-045',4)
        self.assertEqual([c['Case'] for c in repeated],['EYE-025-R1','DER-045-R1','EYE-025-R2','DER-045-R2','EYE-025-R3','DER-045-R3','EYE-025-R4','DER-045-R4'])
        for i,case in enumerate(repeated):
            self.assertEqual(case['repeat_position'],i%2+1)
            self.assertEqual(case['repeat'],i//2+1)
        self.assertEqual(next(c for c in self.cases if c['Case']=='DER-045')['Case'],'DER-045')

    def test_bad_selections_rejected(self):
        for selection,repeat in [('EYE-999',1),('EYE-001,EYE-001',1),('EYE-001',0),('EYE-001',101)]:
            with self.subTest(selection=selection,repeat=repeat),self.assertRaises(ValueError):
                case_bank.select_cases(self.cases,selection,repeat)

    def test_worker_cannot_see_gold_fields(self):
        for original in self.cases:
            case=copy.deepcopy(original)
            for field in runner.GOLD_FIELDS: case[field]='PRIVATE_GOLD_SENTINEL'
            facts=runner.CaseFilter(case).visible_facts()
            self.assertNotIn('PRIVATE_GOLD_SENTINEL',json.dumps(facts))

    def test_replay_follows_manifest_order(self):
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)
            runner.write_json(dest/'run_manifest.json',{'case_ids':['ENT-003','EYE-002','DER-001'],'finished_at':'2026-09-08'})
            replay=monitor_server.build_replay_payload(dest)
            self.assertEqual([c['case_id'] for c in replay['cases']],['ENT-003','EYE-002','DER-001'])
            self.assertEqual(replay['coverage']['missing'],3)
            self.assertFalse(any(c['complete'] for c in replay['cases']))

    def test_run_names_cannot_escape_directory(self):
        config=release_config.load_config()
        for name in ['../outside','..','a/b','a\\b','C:temp','']:
            with self.subTest(name=name),self.assertRaises(ValueError): harness.run_path(config,name)

    def test_resume_rejects_changed_runtime_before_models(self):
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)
            runner.write_json(dest/'run_manifest.json',{'runner_version':runner.RUNNER_VERSION,'quality_scoring_version':runner.QUALITY_SCORING_VERSION,'runtime_code_sha256':{'runner.py':'changed'}})
            args=runner.make_parser().parse_args(['run','--run-dir',str(dest),'--resume'])
            with patch.object(runner,'CodexInvoker') as invoker,self.assertRaisesRegex(ValueError,'runtime code changed'):
                runner.command_run(args)
            invoker.assert_not_called()

    def test_check_from_an_unrelated_directory_without_codex(self):
        with tempfile.TemporaryDirectory() as temp:
            env=os.environ.copy();env['PATH']=''
            result=subprocess.run([sys.executable,'-X','utf8',str(ROOT/'harness.py'),'check'],cwd=temp,env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('250 unique cases',result.stdout)
            self.assertIn('not installed',result.stdout)

    def test_version_display_is_explicit(self):
        displayed=release_config.display_config(release_config.load_config())
        self.assertEqual(displayed['versions']['alan'],'v0.2.0')
        self.assertTrue(all(v=='v1' for k,v in displayed['versions'].items() if k!='alan'))


if __name__=='__main__':unittest.main()
