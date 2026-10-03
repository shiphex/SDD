import json
import math
import tempfile
import unittest
import wave
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import media_tools


class MediaToolsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source.wav"
        with wave.open(str(self.source), "wb") as out:
            out.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            out.writeframes(b"\0\0" * 32000)

    def test_audio_map_uses_source_times_and_rejects_overlap(self):
        edits = self.root / "edits.json"
        edits.write_text(json.dumps({"cuts": [{"start": 0.2, "end": 0.5, "reason": "pause"},
                                               {"start": 1.0, "end": 1.2, "reason": "repeat"}]}))
        output = self.root / "edited.wav"
        mapping = self.root / "map.json"
        media_tools.build_audio(self.source, edits, output, mapping)
        data = json.loads(mapping.read_text())
        self.assertAlmostEqual(data["output_duration"], 1.5, places=3)
        self.assertEqual(len(data["kept"]), 3)
        self.assertEqual(data["cuts"][0]["start"], 0.2)
        edits.write_text(json.dumps({"cuts": [{"start": 0.2, "end": 0.5},
                                               {"start": 0.4, "end": 0.7}]}))
        with self.assertRaisesRegex(ValueError, "overlap"):
            media_tools.build_audio(self.source, edits, output, mapping)

    def test_audio_tool_rejects_a_full_recording(self):
        long_source = self.root / "long.wav"
        with wave.open(str(long_source), "wb") as out:
            out.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            out.writeframes(b"\0\0" * (181 * 16000))
        edits = self.root / "edits.json"
        edits.write_text('{"cuts": []}')
        with self.assertRaisesRegex(ValueError, "only a sample"):
            media_tools.build_audio(long_source, edits, self.root / "edited.wav", self.root / "map.json")

    def test_srt_requires_exact_spoken_text_and_clean_line_ends(self):
        alignment = self.root / "alignment.json"
        alignment.write_text(json.dumps({"items": [
            {"text": "你", "start": 0.0, "end": 0.2},
            {"text": "好", "start": 0.2, "end": 0.4},
            {"text": "世界", "start": 0.6, "end": 1.0},
        ]}), encoding="utf-8")
        lines = self.root / "lines.txt"
        lines.write_text("你好\n世界\n", encoding="utf-8")
        srt = self.root / "final.srt"
        media_tools.build_srt(alignment, lines, srt)
        self.assertIn("00:00:00,600 --> 00:00:01,000\n世界", srt.read_text(encoding="utf-8"))
        lines.write_text("你好。\n世界\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "punctuation"):
            media_tools.build_srt(alignment, lines, srt)
        lines.write_text("你好\n世人\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "mismatch"):
            media_tools.build_srt(alignment, lines, srt)

    def test_scene_and_srt_timing_checks(self):
        scene = self.root / "scene.png"
        scene.write_bytes(b"x")
        scenes = self.root / "scenes.json"
        scenes.write_text(json.dumps({"scenes": [{"start": 0, "end": 1, "image": str(scene)},
                                                 {"start": 1.2, "end": 2, "image": str(scene)}]}))
        with self.assertRaisesRegex(ValueError, "gap"):
            media_tools.load_scenes(scenes, 2)


if __name__ == "__main__":
    unittest.main()
