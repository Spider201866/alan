"""Visual word-count parity and unanswered clarification regressions."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str((Path(__file__).resolve().parents[1] / "runtime")))
import quality_scoring as scoring
import runner


class CountingRegressions(unittest.TestCase):
    def test_worker_numeric_facts_are_not_list_labels(self):
        for text, expected in (
            ("61. Base bleed.", 3),
            ("2. Feeds well.", 3),
            ("1. No fever.", 3),
            ("**61.** Base bleed.", 3),
            ("61.\nBase bleed.", 3),
            ("49.", 1),
            ("6/12. Non-healing sore.", 3),
        ):
            with self.subTest(text=text):
                self.assertEqual(runner.worker_word_count(text), expected)
                self.assertEqual(scoring.word_count(text, strip_list_labels=False), expected)
        self.assertEqual(runner.word_count("1. First diagnosis\n2. Second diagnosis"), 4)

    def test_worker_numeric_fact_counts_towards_word_limit(self):
        reply = "61. " + " ".join(["word"] * 8)
        self.assertEqual(runner.worker_word_count(reply), 9)
        self.assertIn("reply exceeds 8 words", runner.health_worker_style_warnings(reply))

    def test_word_count_matches_display_conventions(self):
        examples = {
            "Non-healing non\u2011healing don’t 6/12 **red** ⚠️ / 1)": 5,
            "pain—blur pain–blur": 4,
            "old man shin sore months keeps growing no heal": 9,
            "⚠️ — /": 0,
            "1) **First diagnosis** 2) _Second diagnosis_ 3) Third diagnosis": 6,
            "Age 53, R+L 6/12, PH 6/9.": 6,
            "49.": 1,
            "Age 49.": 2,
            "1. First diagnosis\n2. Second diagnosis": 4,
        }
        for text, expected in examples.items():
            with self.subTest(text=text):
                self.assertEqual(scoring.word_count(text), expected)

    def test_clarification_does_not_make_question_answered(self):
        for reply in ("Wat dermatoscope mean? Simple please.", "What does fixed mean?", "Simpler words please", "I don't understand", "Not checked"):
            transcript = [
                {"role": "alan", "text": "Is the sore fixed deeply? Are groin nodes enlarged?"},
                {"role": "health_worker", "text": reply},
                {"role": "alan", "text": "Use bright light. Is the sore fixed deeply, and are groin nodes enlarged?"},
            ]
            with self.subTest(reply=reply):
                self.assertEqual(scoring._repeated_answered_question_turns(transcript), [])

    def test_actual_answer_still_triggers_repetition_deduction(self):
        transcript = [
            {"role": "alan", "text": "Are groin nodes enlarged?"},
            {"role": "health_worker", "text": "Groin nodes enlarged."},
            {"role": "alan", "text": "Are groin nodes enlarged?"},
        ]
        self.assertEqual(scoring._repeated_answered_question_turns(transcript), [2])

    def test_partial_hw_answers_do_not_answer_remaining_questions(self):
        examples = [
            ("Are sores around the mouth? Any fever or swollen glands?", "Around mouth. Yellow-gold crust.", "Any fever or swollen glands?"),
            ("Is there pus, fever or rapid spread?", "Low fever. Neck glands enlarged.", "Is there pus or rapid spread?"),
            ("Are foot pulses strong?", "Foot pulses.", "Are foot pulses strong and equal?"),
            ("Any discharge, fever or redness?", "No soft pus pocket.", "Any fever?"),
            ("Any facial weakness, severe vertigo, tinnitus or loud-noise exposure?", "Ringing yes. No loud noise.", "Any facial weakness or severe vertigo?"),
            ("Any tinnitus, imbalance or facial numbness? How old is she?", "37. Canals clear.", "Any tinnitus, imbalance or facial numbness?"),
            ("Any breathing trouble, difficulty swallowing, drooling or neck lump?", "Hard right neck gland. Age 57.", "Any breathing trouble or difficulty swallowing?"),
            ("Are patches wiped off? Is the baby feverish or sleepy?", "Wipe off, red skin. Five days.", "Is the baby feverish or sleepy?"),
            ("Is it hard or bleeding? Any tobacco or betel use?", "Right cheek. Edge hard.", "Any tobacco or betel use?"),
            ("How quickly has it enlarged? Any vision change?", "Left nasal wedge onto cornea. 44.", "How quickly has it enlarged?"),
            ("One eye or both? Any black curtain, flashes or floaters?", "Left eye. RE 6/6, LE 6/18.", "Any flashes, floaters or black curtain?"),
            ("Any staining or clouding? Is tear pH near 7?", "No stain. Cornea clear.", "Is tear pH near 7?"),
            ("Is it tender with a yellow point?", "Small sore spot at lash. No whole-lid swelling.", "Is there a yellow point?"),
        ]
        for prior, worker, repeated in examples:
            with self.subTest(worker=worker):
                transcript = [{"role": "alan", "text": prior}, {"role": "health_worker", "text": worker}, {"role": "alan", "text": repeated}]
                self.assertEqual(scoring._repeated_answered_question_turns(transcript), [])

    def test_answered_part_of_partial_reply_still_counts(self):
        transcript = [
            {"role": "alan", "text": "Are groin nodes enlarged? Is there a yellow point?"},
            {"role": "health_worker", "text": "Groin nodes enlarged. Yellow point not checked."},
            {"role": "alan", "text": "Are groin nodes enlarged?"},
        ]
        self.assertEqual(scoring._repeated_answered_question_turns(transcript), [2])
        transcript[-1]["text"] = "Is there a yellow point?"
        self.assertEqual(scoring._repeated_answered_question_turns(transcript), [])

    def test_yes_no_requires_one_unambiguous_question(self):
        for prior, expected in [
            ("Are groin nodes enlarged?", [2]),
            ("Are groin nodes enlarged? Is vision clear?", []),
            ("Are groin nodes enlarged or tender?", []),
        ]:
            for answer in ("Yes.", "No."):
                with self.subTest(prior=prior, answer=answer):
                    transcript = [{"role": "alan", "text": prior}, {"role": "health_worker", "text": answer}, {"role": "alan", "text": prior}]
                    self.assertEqual(scoring._repeated_answered_question_turns(transcript), expected)

    def test_question_echo_is_not_an_answer(self):
        transcript = [
            {"role": "alan", "text": "Are groin nodes enlarged?"},
            {"role": "health_worker", "text": "Groin nodes enlarged? What does that mean?"},
            {"role": "alan", "text": "Are groin nodes enlarged?"},
        ]
        self.assertEqual(scoring._repeated_answered_question_turns(transcript), [])

    def test_concision_ignores_numbered_list_labels(self):
        reply = "1) " + "word " * 10 + "2) " + "word " * 10 + "3) " + "word " * 11
        self.assertEqual(scoring.word_count(reply), 31)
        self.assertEqual(scoring._concision_score([reply]), 20)
        self.assertEqual(scoring._concision_score(["word " * 34]), 10)
        self.assertEqual(scoring._concision_score(["word " * 37]), 0)


if __name__ == "__main__":
    unittest.main()
