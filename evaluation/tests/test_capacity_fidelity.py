import json, tempfile, unittest, sys, subprocess
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str((Path(__file__).resolve().parents[1] / "runtime")))
import runner
class RecoveryTests(unittest.TestCase):
    def test_capacity_rejection_only(self):
        e=json.dumps({'type':'turn.failed','error':{'message':'Selected model is at capacity'}})
        self.assertTrue(runner.safe_capacity_failure(e))
        self.assertFalse(runner.safe_capacity_failure(e+'\n'+json.dumps({'type':'item.started'})))
        self.assertFalse(runner.safe_capacity_failure('timeout'))
    def test_bounded_retry_records_and_preserves_prompt(self):
        with tempfile.TemporaryDirectory() as d:
            inv=object.__new__(runner.CodexInvoker);inv.codex='codex';inv.timeout=1;inv.retries=0
            def failed(*a,**kw): return subprocess.CompletedProcess(a,1,json.dumps({'type':'error','message':'Selected model is at capacity'}),'')
            with patch.object(runner.subprocess,'run',side_effect=failed) as call,patch.object(runner.time,'sleep') as sleep:
                with self.assertRaises(runner.CodexError): inv._run(['exec'],'same prompt',Path(d))
                self.assertEqual(call.call_count,4)
                self.assertEqual([x.args[0] for x in sleep.call_args_list],[5,15,30])
                self.assertTrue(all(x.kwargs['input']=='same prompt' for x in call.call_args_list))
                self.assertEqual(len(list(Path(d).glob('capacity_retry_*.json'))),3)
    def test_hw_failure_does_not_fail_alan(self):
        j=runner.finalise_judgement({'diagnosis_correct':True,'worker_protocol_difference':'material','urgency_difference':'none','management_difference':'none','serious_unsafe_advice':False},'terminal_closing')
        self.assertTrue(j['deployable_pass']);self.assertFalse(j['test_fidelity_valid'])
        self.assertFalse(runner.finalise_judgement(j,'hard_cap')['deployable_pass'])

    def test_timeout_does_not_retry_uncertain_session(self):
        with tempfile.TemporaryDirectory() as d:
            inv=object.__new__(runner.CodexInvoker);inv.codex='codex';inv.timeout=1;inv.retries=0
            with patch.object(runner.subprocess,'run',side_effect=subprocess.TimeoutExpired('codex',1)) as call:
                with self.assertRaises(runner.CodexError):inv._run(['exec','resume'],'message',Path(d),retries=0)
                self.assertEqual(call.call_count,1)
    def test_capacity_then_success_has_single_reply(self):
        with tempfile.TemporaryDirectory() as d:
            inv=object.__new__(runner.CodexInvoker);inv.codex='codex';inv.timeout=1;inv.retries=0
            count=0
            def run(command,**kw):
                nonlocal count
                count+=1
                if count==1:return subprocess.CompletedProcess(command,1,'{"type":"error","message":"Selected model is at capacity"}','')
                Path(command[command.index('--output-last-message')+1]).write_text('One answer')
                return subprocess.CompletedProcess(command,0,'{"type":"turn.completed","usage":{}}','')
            with patch.object(runner.subprocess,'run',side_effect=run),patch.object(runner.time,'sleep'):
                result=inv._run(['exec','resume'],'message',Path(d),retries=0)
                self.assertEqual(result['reply'],'One answer');self.assertEqual(result['attempts'],2)
