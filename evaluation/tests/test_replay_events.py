import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str((Path(__file__).resolve().parents[1] / "runtime")))
from replay_events import ReplayRecorder, read_events, recover_completion


class ReplayTests(unittest.TestCase):
    def test_restart_preserves_old_attempt_and_starts_clean(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'replay.jsonl'
            ReplayRecorder(path, 'DER-042').append({'phase': 'alan'}, [{'role': 'worker', 'text': 'old'}])
            old = path.read_bytes()
            ReplayRecorder(path, 'DER-042').append({'phase': 'alan'}, [{'role': 'worker', 'text': 'new'}])
            self.assertEqual([e['sequence'] for e in read_events(path)], [0])
            archives = list(path.parent.glob('replay.attempt-*.jsonl'))
            self.assertEqual(len(archives), 1)
            self.assertEqual(archives[0].read_bytes(), old)
            self.assertEqual(read_events(path)[0]['messages'][0]['text'], 'new')

    def test_completion_recovered_without_modifying_log_or_result(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'replay.jsonl'
            transcript = [{'role': 'alan', 'text': 'Good luck!'}]
            ReplayRecorder(path, 'DER-042').append({'phase': 'judge'}, transcript)
            before = path.read_bytes()
            result = {'status': 'complete', 'transcript': transcript, 'quality': {'alan_index': {'score': 91}},
                      'judgement': {'diagnosis_correct': True}, 'elapsed_ms': 2000}
            events = recover_completion(read_events(path), result)
            self.assertEqual(events[-1]['phase'], 'complete')
            self.assertTrue(events[-1]['recovered'])
            self.assertEqual(events[-1]['quality'], result['quality'])
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(len(recover_completion(events, result)), 2)
            result['transcript'] = []
            self.assertEqual(len(recover_completion(read_events(path), result)), 1)
            self.assertEqual(recover_completion([], result), [])

    def test_partial_utf8_tail_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'replay.jsonl'
            ReplayRecorder(path, 'DER-042').append({'phase': 'alan'}, [])
            with path.open('ab') as handle:
                handle.write(b'{"text":"\xe2\x9c')
            self.assertEqual(len(read_events(path)), 1)

    def test_events_are_durable_ordered_snapshots(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'replay.jsonl'
            recorder = ReplayRecorder(path, 'DER-042')
            transcript = [{'role': 'health_worker', 'text': 'sore'}]
            recorder.append({'phase': 'alan'}, transcript)
            transcript.append({'role': 'alan', 'text': 'How long?'})
            recorder.append({'phase': 'worker'}, transcript)
            events = read_events(path)
            self.assertEqual([e['sequence'] for e in events], [0, 1])
            self.assertEqual([len(e['messages']) for e in events], [1, 2])
            self.assertGreaterEqual(events[1]['elapsed_ms'], events[0]['elapsed_ms'])
            self.assertNotIn('judge', events[0])
            self.assertNotIn('quality', events[1])

    def test_partial_tail_is_not_replayed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'replay.jsonl'
            recorder = ReplayRecorder(path, 'DER-042')
            recorder.append({'phase': 'alan'}, [])
            with path.open('a', encoding='utf-8') as handle:
                handle.write('{"version":')
            self.assertEqual(len(read_events(path)), 1)

    def test_corrupt_sequence_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'replay.jsonl'
            path.write_text(json.dumps({'version': 1, 'sequence': 3}) + '\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                read_events(path)
