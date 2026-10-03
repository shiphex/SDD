from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "scripts" / "audio_to_srt.py"
SPEC = importlib.util.spec_from_file_location("audio_to_srt", SCRIPT)
assert SPEC and SPEC.loader
audio_to_srt = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audio_to_srt)


class TranscriptSegmentTests(unittest.TestCase):
    def test_full_draft_transcription_needs_explicit_full_ai_authorization(self) -> None:
        state = {"stage": "full_content_review", "gates": {
            "sample_acceptance": {"status": "approved"},
            "full_ai_edit_authorization": {"status": "approved"},
            "full_content_review": {"status": "pending"},
        }}
        audio_to_srt.validate_full_recording_gate(300.0, state, "pilot")
        state["gates"]["full_ai_edit_authorization"]["status"] = "pending"
        with self.assertRaisesRegex(ValueError, "authorization"):
            audio_to_srt.validate_full_recording_gate(300.0, state, "pilot")

    def test_transcript_boundary_moves_before_a_crossing_word(self) -> None:
        items = [
            {"text": "开始", "start": 1.0, "end": 1.5},
            {"text": "边界", "start": 179.9, "end": 180.08},
            {"text": "结束", "start": 200.0, "end": 200.5},
        ]
        sections = audio_to_srt.transcript_segments_from_items(items, 210.0)
        self.assertEqual([(s["start"], s["end"]) for s in sections], [(0.0, 179.9), (179.9, 210.0)])
        self.assertIn("边界", sections[1]["text"])
        self.assertNotIn("边界", sections[0]["text"])

    def test_short_sample_does_not_need_full_recording_gate(self) -> None:
        audio_to_srt.validate_full_recording_gate(180.0, None, None)

    def test_long_audio_requires_run_and_current_sample_acceptance(self) -> None:
        approved_state = {
            "stage": "full_transcript",
            "gates": {"sample_acceptance": {"status": "approved"}},
        }
        audio_to_srt.validate_full_recording_gate(181.0, approved_state, "pilot")

        with self.assertRaisesRegex(ValueError, "VIDEO_RUN_ID"):
            audio_to_srt.validate_full_recording_gate(181.0, approved_state, None)
        with self.assertRaisesRegex(ValueError, "sample_acceptance"):
            audio_to_srt.validate_full_recording_gate(
                181.0,
                {"stage": "full_transcript", "gates": {"sample_acceptance": {"status": "pending"}}},
                "pilot",
            )
        with self.assertRaisesRegex(ValueError, "full_transcript"):
            audio_to_srt.validate_full_recording_gate(
                181.0,
                {"stage": "sample_quality_review", "gates": {"sample_acceptance": {"status": "approved"}}},
                "pilot",
            )
        with self.assertRaisesRegex(ValueError, "full_transcript"):
            audio_to_srt.validate_full_recording_gate(
                181.0,
                {"stage": "full_outline", "gates": {"sample_acceptance": {"status": "approved"}}},
                "pilot",
            )

    def test_direct_long_audio_call_reconciles_workflow_state_through_powershell(self) -> None:
        completed = subprocess.CompletedProcess([], 0, "Audio approved\n", "")
        with (
            patch.dict("os.environ", {"VIDEO_RUN_ID": "pilot"}),
            patch.object(audio_to_srt, "audio_duration_seconds", return_value=181.0),
            patch("shutil.which", return_value="pwsh"),
            patch.object(audio_to_srt.subprocess, "run", return_value=completed) as run,
        ):
            duration = audio_to_srt.verify_audio_workflow_gate(Path("full.wav"))

        self.assertEqual(duration, 181.0)
        command = run.call_args.args[0]
        self.assertIn("assert-audio-approved", command)
        self.assertIn("-InputAudio", command)
        self.assertIn("full.wav", command)

    def test_direct_long_audio_call_fails_closed_without_powershell(self) -> None:
        with (
            patch.dict("os.environ", {"VIDEO_RUN_ID": "pilot"}),
            patch.object(audio_to_srt, "audio_duration_seconds", return_value=181.0),
            patch("shutil.which", return_value=None),
        ):
            with self.assertRaisesRegex(ValueError, "PowerShell"):
                audio_to_srt.verify_audio_workflow_gate(Path("full.wav"))

    def test_direct_long_audio_call_rejects_stale_or_mismatched_manifest(self) -> None:
        failed = subprocess.CompletedProcess([], 1, "", "Input audio does not match")
        with (
            patch.dict("os.environ", {"VIDEO_RUN_ID": "pilot"}),
            patch.object(audio_to_srt, "audio_duration_seconds", return_value=181.0),
            patch("shutil.which", return_value="pwsh"),
            patch.object(audio_to_srt.subprocess, "run", return_value=failed),
        ):
            with self.assertRaisesRegex(ValueError, "(?i)workflow approval"):
                audio_to_srt.verify_audio_workflow_gate(Path("other.wav"))

    def test_transcript_alignment_api_exists(self) -> None:
        self.assertTrue(callable(getattr(audio_to_srt, "parse_transcript_sections", None)))
        self.assertTrue(callable(getattr(audio_to_srt, "transcript_markdown", None)))
        self.assertTrue(callable(getattr(audio_to_srt, "transcript_segments_from_items", None)))
        self.assertTrue(callable(getattr(audio_to_srt, "align_transcript_sections", None)))

    def test_cli_exposes_corrected_transcript_alignment(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("--transcript-input", result.stdout)
        self.assertIn("--transcript-output", result.stdout)

    @unittest.skipUnless(hasattr(audio_to_srt, "parse_transcript_sections"), "parser not implemented yet")
    def test_parses_contiguous_segments_and_preserves_text(self) -> None:
        markdown = """# 转写校对稿

## 音频段 001 | 00:00:00.000 - 00:03:00.000
第一段口播。

## 音频段 002 | 00:03:00.000 - 00:04:00.000
第二段口播。
"""

        segments = audio_to_srt.parse_transcript_sections(markdown, 240.0)

        self.assertEqual(
            segments,
            [
                {"start": 0.0, "end": 180.0, "text": "第一段口播。"},
                {"start": 180.0, "end": 240.0, "text": "第二段口播。"},
            ],
        )

    @unittest.skipUnless(hasattr(audio_to_srt, "parse_transcript_sections"), "parser not implemented yet")
    def test_rejects_segments_longer_than_forced_aligner_limit(self) -> None:
        markdown = """## 音频段 001 | 00:00:00.000 - 00:03:00.001
正文
"""

        with self.assertRaisesRegex(ValueError, "180"):
            audio_to_srt.parse_transcript_sections(markdown, 180.001)

    @unittest.skipUnless(hasattr(audio_to_srt, "parse_transcript_sections"), "parser not implemented yet")
    def test_rejects_gaps_between_audio_segments(self) -> None:
        markdown = """## 音频段 001 | 00:00:00.000 - 00:01:00.000
第一段
## 音频段 002 | 00:01:01.000 - 00:02:00.000
第二段
"""

        with self.assertRaisesRegex(ValueError, "contiguous|连续"):
            audio_to_srt.parse_transcript_sections(markdown, 120.0)

    @unittest.skipUnless(hasattr(audio_to_srt, "transcript_segments_from_items"), "transcript export not implemented yet")
    def test_exports_transcript_in_aligner_sized_segments(self) -> None:
        items = [
            {"text": "开场。", "start": 0.2, "end": 1.0},
            {"text": "后续。", "start": 180.2, "end": 180.8},
        ]

        segments = audio_to_srt.transcript_segments_from_items(items, 181.0)
        markdown = audio_to_srt.transcript_markdown(segments, "Chinese")

        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0]["text"], "开场。")
        self.assertEqual(segments[1]["text"], "后续。")
        self.assertEqual(
            audio_to_srt.parse_transcript_sections(markdown, 181.0), segments
        )

    @unittest.skipUnless(hasattr(audio_to_srt, "align_transcript_sections"), "aligner entrypoint not implemented yet")
    def test_realigns_text_in_segment_and_restores_absolute_offset(self) -> None:
        class FakeAligner:
            def __init__(self) -> None:
                self.calls = []

            def align(self, *, audio, text, language):
                self.calls.append((len(audio[0]), text, language))
                return [
                    SimpleNamespace(
                        items=[SimpleNamespace(text="好", start_time=0.1, end_time=0.5)]
                    )
                ]

        aligner = FakeAligner()
        waveform = range(181 * 16_000)
        segments = [
            {"start": 0.0, "end": 180.0, "text": ""},
            {"start": 180.0, "end": 181.0, "text": "好。"},
        ]

        items = audio_to_srt.align_transcript_sections(
            segments, waveform, aligner, "Chinese"
        )

        self.assertEqual(aligner.calls, [(16_000, "好。", "Chinese")])
        self.assertEqual(items, [{"text": "好。", "start": 180.1, "end": 180.5}])


if __name__ == "__main__":
    unittest.main()
