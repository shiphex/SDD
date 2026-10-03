"""Optional local regression against the ignored pilot assets; writes only to temp."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import media_tools


repo = Path(__file__).resolve().parents[4]
pilot = repo / ".local/video/pilot"
source = pilot / "source-first-3m.wav"
reference_map = pilot / "final-cut-map.json"
reference_srt = pilot / "final.srt"
alignment = pilot / "final.alignment.json"
slides = pilot / "final-build/slides"
if not all(p.is_file() for p in (source, reference_map, reference_srt, alignment)):
    raise SystemExit("Pilot regression assets are unavailable")

original = json.loads(reference_map.read_text(encoding="utf-8"))


def mapped(source_time):
    for part in original["kept"]:
        if part["source_start"] <= source_time <= part["source_end"]:
            return part["output_start"] + source_time - part["source_start"]
    preceding = [p for p in original["kept"] if p["source_end"] < source_time]
    return preceding[-1]["output_end"] if preceding else 0.0


with tempfile.TemporaryDirectory(prefix="pilot-regression-", dir=pilot) as temporary:
    temp = Path(temporary)
    edits = temp / "edits.json"
    edits.write_text(json.dumps({"cuts": original["cuts"]}, ensure_ascii=False), encoding="utf-8")
    audio, mapping = temp / "audio.wav", temp / "map.json"
    media_tools.build_audio(source, edits, audio, mapping)
    rebuilt = json.loads(mapping.read_text(encoding="utf-8"))
    assert abs(rebuilt["output_duration"] - original["output_duration"]) < .001
    assert len(rebuilt["cuts"]) == len(original["cuts"])

    lines = temp / "lines.txt"
    lines.write_text("\n".join(c["text"] for c in media_tools.read_srt(reference_srt)) + "\n", encoding="utf-8")
    srt = temp / "final.srt"
    media_tools.build_srt(alignment, lines, srt)
    assert srt.read_text(encoding="utf-8") == reference_srt.read_text(encoding="utf-8-sig")

    boundaries = [0, mapped(76.72), mapped(122.24), mapped(157.20), rebuilt["output_duration"]]
    scenes = temp / "scenes.json"
    scenes.write_text(json.dumps({"scenes": [
        {"start": boundaries[i], "end": boundaries[i + 1], "image": str(slides / f"P{i + 1:02}.png")}
        for i in range(4)]}, ensure_ascii=False), encoding="utf-8")
    video = temp / "sample.mp4"
    media_tools.render_video(audio, srt, scenes, video)
    print(json.dumps(media_tools.verify(audio, mapping, srt, scenes, video), ensure_ascii=False))
