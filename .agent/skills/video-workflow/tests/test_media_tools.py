import json
import math
import tempfile
import unittest
import wave
from pathlib import Path
import sys
import shutil
import subprocess
import hashlib
from unittest.mock import patch
import array

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

    def test_full_edit_requires_run_id_even_for_short_input(self):
        edits = self.root / "edits.json"
        edits.write_text('{"cuts": []}')
        with self.assertRaisesRegex(ValueError, "run ID"):
            media_tools.build_audio(self.source, edits, self.root / "edited.wav",
                                    self.root / "map.json", scope="full")

    def test_assembly_keeps_multisource_provenance_and_pcm(self):
        pickup = self.root / 'pickup.wav'
        with wave.open(str(pickup), 'wb') as wav:
            wav.setparams((1, 2, 16000, 0, 'NONE', ''))
            wav.writeframes(array.array('h', [2000] * 16000).tobytes())
        sources = {key: {'artifact_id': aid, 'path': str(path),
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                   for key, aid, path in [('baseline', 'full-preview-baseline-audio', self.source),
                                          ('pickup', 'full-pickup-wav', pickup)]}
        plan = self.root / 'timeline.json'
        plan.write_text(json.dumps({'sources': sources, 'segments': [
            {'source_id': 'baseline', 'start': 0, 'end': .5},
            {'source_id': 'pickup', 'start': .1, 'end': .6, 'gain_db': -6.0206,
             'issue_id': 'I-101', 'reason': 'correction'},
            {'source_id': 'baseline', 'start': 1, 'end': 2}]}))
        audio, mapping = self.root / 'assembled.wav', self.root / 'maps' / 'assembled.json'
        with patch.object(media_tools.subprocess, 'run') as gate:
            gate.return_value.returncode = 0
            media_tools.assemble_audio(plan, audio, mapping, run_id='fixture')
        data = json.loads(mapping.read_text())
        self.assertEqual(data['schema_version'], 2)
        self.assertEqual(data['kept'][1]['issue_id'], 'I-101')
        self.assertEqual(data['kept'][1]['source_id'], 'pickup')
        self.assertEqual(data['output_duration'], 2)
        with wave.open(str(audio)) as wav:
            pcm = array.array('h', wav.readframes(wav.getnframes()))
        self.assertEqual(pcm[12000], 1000)
        media_tools.validate_cut_map(data, 2)
        data['kept'][1]['output_start'] += .01
        with self.assertRaisesRegex(ValueError, 'gap|continuous'):
            media_tools.validate_cut_map(data, 2)
        sources['pickup']['sha256'] = '0' * 64
        plan.write_text(json.dumps({'sources': sources, 'segments': [
            {'source_id': 'pickup', 'start': 0, 'end': 1}]}))
        with patch.object(media_tools.subprocess, 'run') as gate:
            gate.return_value.returncode = 0
            with self.assertRaisesRegex(ValueError, 'hash'):
                media_tools.assemble_audio(plan, audio, mapping, run_id='fixture')

    def test_assembly_rejects_unapproved_run(self):
        with patch.object(media_tools.subprocess, 'run') as gate:
            gate.return_value.returncode = 1
            gate.return_value.stderr = 'not approved'
            with self.assertRaisesRegex(ValueError, 'approval'):
                media_tools.assemble_audio(self.root / 'missing.json', self.root / 'out.wav',
                                           self.root / 'map.json', run_id='fixture')

    def test_composite_map_rejects_nonfinite_duration(self):
        data = {'schema_version': 2, 'output_duration': float('nan'), 'sample_rate': 16000,
                'sources': {'a': {'duration': 1}}, 'kept': [
                    {'source_id': 'a', 'source_start': 0, 'source_end': 1,
                     'output_start': 0, 'output_end': 1}]}
        with self.assertRaisesRegex(ValueError, 'duration'):
            media_tools.validate_cut_map(data, 1)

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

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg is required')
    def test_verify_handles_utf8_probe_metadata_and_chinese_filename(self):
        video = self.root / '讲解预览.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        'color=size=1920x1080:rate=30:duration=2', '-i', str(self.source),
                        '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac',
                        '-metadata', 'title=中文字幕检查', str(video)], check=True)
        edits = self.root / 'edits.json'
        edits.write_text('{"cuts": []}')
        audio, mapping = self.root / 'copy.wav', self.root / 'map.json'
        media_tools.build_audio(self.source, edits, audio, mapping)
        srt = self.root / 'captions.srt'
        srt.write_text('1\n00:00:00,000 --> 00:00:01,000\n字幕\n', encoding='utf-8')
        scene = self.root / 'scene.png'
        scene.write_bytes(b'fixture: image existence only')
        scenes = self.root / 'scenes.json'
        scenes.write_text(json.dumps({'scenes':[{'start':0,'end':2,'image':str(scene)}]}))
        result = media_tools.verify(audio, mapping, srt, scenes, video)
        self.assertEqual(result['video'], '1920x1080 30fps H.264/AAC')


if __name__ == "__main__":
    unittest.main()
