"""Reusable local editing tools for an authorized narration sample.

Editorial choices live in ignored run files. This module does not choose cuts,
correct words, approve content, or open the full-recording workflow gate.
"""

from __future__ import annotations

import argparse
import array
import json
import math
import re
import subprocess
import sys
import tempfile
import hashlib
import io
import unicodedata
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _normalized(value: str) -> str:
    return "".join(c for c in value if not c.isspace() and not unicodedata.category(c).startswith("P"))


def _stamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def _seconds(stamp: str) -> float:
    match = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", stamp)
    if not match:
        raise ValueError(f"Invalid SRT timestamp: {stamp}")
    h, m, s, ms = map(int, match.groups())
    return h * 3600 + m * 60 + s + ms / 1000


def _duration(audio: Path) -> float:
    with wave.open(str(audio), "rb") as wav:
        return wav.getnframes() / wav.getframerate()


def build_audio(source: Path, edits: Path, output: Path, mapping: Path,
                *, scope: str = "sample", run_id: str | None = None) -> None:
    """Cut source-time intervals from a mono 16-bit WAV; record every kept span."""
    if scope not in ("sample", "full"):
        raise ValueError("Unknown editing scope")
    if scope == "full":
        if not run_id or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", run_id):
            raise ValueError("Full editing requires a valid run ID")
        state = Path(__file__).with_name("workflow-state.ps1")
        check = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                                "-File", str(state), "-Action", "assert-full-edit-approved",
                                "-RunId", run_id, "-InputAudio", str(source.resolve())],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
        if check.returncode:
            raise ValueError("Full editing approval failed: " + check.stderr.strip())
    with wave.open(str(source), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getcomptype() != "NONE":
            raise ValueError("Source must be uncompressed mono 16-bit PCM WAV")
        rate = wav.getframerate()
        samples = array.array("h", wav.readframes(wav.getnframes()))
    if sys.byteorder != "little":
        samples.byteswap()
    count = len(samples)
    duration = count / rate
    if scope == "sample" and duration > 180.05:
        raise ValueError("This AI editing tool accepts only a sample source of at most 180.05 seconds")
    raw_cuts = _read_json(edits).get("cuts")
    if not isinstance(raw_cuts, list):
        raise ValueError("Edit list must contain a cuts array")
    cuts = []
    for entry in raw_cuts:
        start, end = float(entry["start"]), float(entry["end"])
        if not math.isfinite(start) or not math.isfinite(end) or not 0 <= start < end <= duration + 1 / rate:
            raise ValueError("Cut lies outside source audio or has invalid times")
        a, b = round(start * rate), min(count, round(end * rate))
        if a >= b:
            raise ValueError("Cut has zero frames")
        cuts.append({"start": a / rate, "end": b / rate,
                     "reasons": entry.get("reasons", [entry.get("reason", "")])})
    cuts.sort(key=lambda c: c["start"])
    if any(cuts[i]["start"] < cuts[i - 1]["end"] for i in range(1, len(cuts))):
        raise ValueError("Cuts overlap in source time")
    kept = []
    out = array.array("h")
    cursor = 0
    intervals = []
    for cut in cuts:
        end = round(cut["start"] * rate)
        if end > cursor:
            intervals.append((cursor, end))
        cursor = round(cut["end"] * rate)
    if cursor < count:
        intervals.append((cursor, count))
    if not intervals:
        raise ValueError("All audio was removed")
    fade_frames = round(rate * 0.004)
    for index, (a, b) in enumerate(intervals):
        part = samples[a:b]
        fade = min(fade_frames, len(part) // 4)
        if fade and index:
            for j in range(fade):
                part[j] = round(part[j] * j / fade)
        if fade and index + 1 < len(intervals):
            for j in range(fade):
                pos = len(part) - fade + j
                part[pos] = round(part[pos] * (fade - j - 1) / fade)
        offset = len(out)
        out.extend(part)
        kept.append({"source_start": a / rate, "source_end": b / rate,
                     "output_start": offset / rate, "output_end": len(out) / rate})
    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output), "wb") as wav:
        wav.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        if sys.byteorder != "little":
            out.byteswap()
        wav.writeframes(out.tobytes())
    mapping.parent.mkdir(parents=True, exist_ok=True)
    mapping.write_text(json.dumps({"schema_version": 1, "source": str(source.resolve()),
                                   "source_duration": duration, "output": str(output.resolve()),
                                   "output_duration": len(out) / rate, "cuts": cuts, "kept": kept},
                                  ensure_ascii=False, indent=2), encoding="utf-8")


def build_srt(alignment: Path, lines: Path, output: Path) -> None:
    items = _read_json(alignment)["items"]
    phrases = [line.strip() for line in lines.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if not phrases:
        raise ValueError("Caption lines are empty")
    for line in phrases:
        if unicodedata.category(line[-1]).startswith("P"):
            raise ValueError("Caption line ends with punctuation")
    chars = [(char, float(item["start"]), float(item["end"]))
             for item in items for char in _normalized(item["text"])]
    if "".join(c for c, _, _ in chars) != "".join(_normalized(p) for p in phrases):
        raise ValueError("Caption wording mismatch with corrected alignment")
    cursor = 0
    blocks = []
    previous_end = 0.0
    for number, phrase in enumerate(phrases, 1):
        size = len(_normalized(phrase))
        if not size:
            raise ValueError("Caption line has no spoken characters")
        group = chars[cursor:cursor + size]
        start, end = group[0][1], group[-1][2]
        if not 0 <= start < end or start < previous_end - .001:
            raise ValueError("Caption cues overlap or have invalid times")
        blocks.append(f"{number}\n{_stamp(start)} --> {_stamp(end)}\n{phrase}")
        previous_end, cursor = end, cursor + size
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def read_srt(path: Path) -> list[dict]:
    cues = []
    for block in re.split(r"\r?\n\s*\r?\n", path.read_text(encoding="utf-8-sig").strip()):
        lines = block.splitlines()
        if len(lines) < 3 or " --> " not in lines[1]:
            raise ValueError("Invalid SRT cue")
        a, b = lines[1].split(" --> ", 1)
        start, end = _seconds(a), _seconds(b)
        if not start < end or (cues and start < cues[-1]["end"] - .001):
            raise ValueError("SRT cues overlap or have invalid times")
        text = "\n".join(lines[2:])
        if any(unicodedata.category(line.rstrip()[-1]).startswith("P") for line in lines[2:] if line.rstrip()):
            raise ValueError("SRT line ends with punctuation")
        cues.append({"start": start, "end": end, "text": text})
    return cues


def load_scenes(path: Path, duration: float) -> list[dict]:
    scenes = _read_json(path).get("scenes", [])
    if not scenes:
        raise ValueError("Scene list is empty")
    previous = 0.0
    for scene in scenes:
        start, end = float(scene["start"]), float(scene["end"])
        if abs(start - previous) > .001:
            raise ValueError("Scene timeline has a gap or overlap")
        if not start < end or end > duration + .05:
            raise ValueError("Scene times are invalid")
        image = Path(scene["image"])
        if not image.is_absolute():
            image = path.parent / image
        if not image.is_file():
            raise ValueError(f"Missing scene image: {image}")
        scene["image"] = str(image)
        previous = end
    if abs(previous - duration) > .05:
        raise ValueError("Scene timeline has a gap at the end")
    return scenes


def render_video(audio: Path, srt: Path, scene_file: Path, output: Path,
                 font_file: Path | None = None) -> None:
    from PIL import Image, ImageDraw, ImageFont

    duration = _duration(audio)
    scenes = load_scenes(scene_file, duration)
    cues = read_srt(srt)
    if cues and cues[-1]["end"] > duration + .05:
        raise ValueError("Caption extends beyond audio")
    font_file = font_file or Path("C:/Windows/Fonts/msyh.ttc")
    if not font_file.is_file():
        raise ValueError(f"Missing subtitle font: {font_file}")
    font = ImageFont.truetype(str(font_file), 46)
    breaks = sorted({0.0, duration, *(float(s[x]) for s in scenes for x in ("start", "end")),
                     *(c[x] for c in cues for x in ("start", "end"))})
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="video-workflow-") as temporary:
        temp = Path(temporary)
        concat = temp / "frames.ffconcat"
        records = ["ffconcat version 1.0"]
        for index, (start, end) in enumerate(zip(breaks, breaks[1:])):
            if end - start < .001:
                continue
            midpoint = (start + end) / 2
            scene = next(s for s in scenes if s["start"] <= midpoint < s["end"] + .001)
            with Image.open(scene["image"]) as base:
                if base.size != (1920, 1080):
                    raise ValueError("Scene images must be 1920x1080")
                frame = base.convert("RGB")
            caption = next((c["text"] for c in cues if c["start"] <= midpoint < c["end"]), "")
            if caption:
                draw = ImageDraw.Draw(frame)
                rows = caption.splitlines()
                if len(rows) > 2:
                    raise ValueError("A caption may contain at most two lines")
                for row_number, row in enumerate(rows):
                    if draw.textbbox((0, 0), row, font=font, stroke_width=3)[2] > 1800:
                        raise ValueError("Caption exceeds the video safe width")
                    y = 960 if len(rows) == 1 else 925 + row_number * 63
                    draw.text((960, y), row, font=font, anchor="mm", fill="white",
                              stroke_width=3, stroke_fill="#06111f")
            frame_path = temp / f"frame-{index:05}.png"
            frame.save(frame_path)
            records.extend((f"file '{frame_path.as_posix()}'", f"duration {end - start:.6f}"))
        records.append(records[-2])
        concat.write_text("\n".join(records) + "\n", encoding="utf-8")
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat",
                   "-safe", "0", "-i", str(concat), "-i", str(audio), "-map", "0:v:0",
                   "-map", "1:a:0", "-r", "30", "-t", str(duration), "-c:v", "libx264",
                   "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(output)]
        subprocess.run(command, check=True)


def assemble_audio(timeline: Path, output: Path, mapping: Path, *, run_id: str) -> None:
    """Assemble approved source spans without making editorial decisions."""
    if not run_id or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", run_id):
        raise ValueError("Assembly requires a valid run ID")
    state = Path(__file__).with_name("workflow-state.ps1")
    check = subprocess.run(["powershell.exe", "-NoProfile", "-File", str(state),
                            "-Action", "assert-assembly-approved", "-RunId", run_id,
                            "-Path", str(timeline.resolve())], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
    if check.returncode:
        raise ValueError("Assembly approval failed: " + check.stderr.strip())
    plan = _read_json(timeline)
    if not plan.get("sources") or not plan.get("segments"):
        raise ValueError("Assembly requires sources and segments")
    sources, pcm, rate = {}, {}, None
    for sid, entry in plan["sources"].items():
        path = Path(entry["path"])
        if not path.is_absolute():
            path = timeline.parent / path
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != entry["sha256"]:
            raise ValueError("Assembly source hash mismatch: " + sid)
        with wave.open(io.BytesIO(raw)) as wav:
            if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getcomptype() != "NONE":
                raise ValueError("Assembly source must be mono 16-bit PCM WAV")
            if rate is not None and rate != wav.getframerate():
                raise ValueError("Assembly sources must have the same sample rate")
            rate = wav.getframerate()
            values = array.array("h", wav.readframes(wav.getnframes()))
        if sys.byteorder != "little":
            values.byteswap()
        pcm[sid] = values
        sources[sid] = dict(entry, path=str(path.resolve()), duration=len(values) / rate)
    if output.resolve() in {Path(s["path"]).resolve() for s in sources.values()}:
        raise ValueError("Assembly cannot overwrite a source")
    out, kept = array.array("h"), []
    for index, segment in enumerate(plan["segments"]):
        sid = segment["source_id"]
        if sid not in pcm:
            raise ValueError("Unknown assembly source: " + sid)
        start, end = float(segment["start"]), float(segment["end"])
        gain = float(segment.get("gain_db", 0))
        if not all(math.isfinite(x) for x in (start, end, gain)) or not 0 <= start < end <= sources[sid]["duration"]:
            raise ValueError("Invalid assembly source range or gain")
        a, b = round(start * rate), round(end * rate)
        if a >= b:
            raise ValueError("Assembly segment has zero frames")
        part = pcm[sid][a:b]
        factor = 10 ** (gain / 20)
        if factor != 1:
            scaled = [round(v * factor) for v in part]
            if any(v < -32768 or v > 32767 for v in scaled):
                raise ValueError("Assembly gain would clip audio")
            part = array.array("h", scaled)
        fade = min(round(rate * .004), len(part) // 4)
        if index:
            for j in range(fade):
                part[j] = round(part[j] * j / fade)
        if index + 1 < len(plan["segments"]):
            for j in range(fade):
                part[len(part)-fade+j] = round(part[len(part)-fade+j] * (fade-j-1) / fade)
        offset = len(out)
        out.extend(part)
        kept.append({"source_id": sid, "source_start": a / rate, "source_end": b / rate,
                     "output_start": offset / rate, "output_end": len(out) / rate,
                     "gain_db": gain, "issue_id": segment.get("issue_id"),
                     "reason": segment.get("reason", "retained baseline")})
    data = {"schema_version": 2, "sources": sources, "sample_rate": rate,
            "timeline": str(timeline.resolve()), "output": str(output.resolve()),
            "output_duration": len(out) / rate, "kept": kept, "cuts": []}
    validate_cut_map(data, len(out) / rate)
    output.parent.mkdir(parents=True, exist_ok=True)
    mapping.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output), "wb") as wav:
        wav.setparams((1, 2, rate, 0, "NONE", ""))
        if sys.byteorder != "little":
            out.byteswap()
        wav.writeframes(out.tobytes())
    mapping.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _assert_retime_approved(timeline: Path, run_id: str) -> None:
    if not run_id or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", run_id):
        raise ValueError("Retime requires a valid run ID")
    check = subprocess.run(["powershell.exe", "-NoProfile", "-File",
        str(Path(__file__).with_name("workflow-state.ps1")), "-Action", "assert-retime-approved",
        "-RunId", run_id, "-Path", str(timeline.resolve())],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check.returncode:
        raise ValueError("Retime approval failed: " + check.stderr.strip())


def retime_audio(timeline: Path, output: Path, mapping: Path, *, run_id: str) -> None:
    """Execute explicit speech/pause/cut spans, retaining fixed-baseline provenance."""
    _assert_retime_approved(timeline, run_id)
    plan = _read_json(timeline)
    inputs = {}
    for key in ("source", "source_map"):
        entry = plan[key]
        path = Path(entry["path"])
        if not path.is_absolute(): path = timeline.parent / path
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("Retime source hash mismatch")
        inputs[key] = dict(entry, path=str(path.resolve()))
    source = Path(inputs["source"]["path"])
    if output.resolve() in {source.resolve(), Path(inputs["source_map"]["path"]), timeline.resolve()} or mapping.resolve() in {
            source.resolve(), Path(inputs["source_map"]["path"]), output.resolve(), timeline.resolve()}:
        raise ValueError("Retime outputs cannot overwrite inputs or each other")
    with wave.open(str(source)) as w:
        if w.getnchannels()!=1 or w.getsampwidth()!=2 or w.getcomptype()!="NONE":
            raise ValueError("Retime source must be mono 16-bit PCM WAV")
        rate=w.getframerate(); count=w.getnframes(); pcm=w.readframes(count)
    validate_cut_map(_read_json(Path(inputs["source_map"]["path"])), count/rate)
    inputs["source"]["duration"]=count/rate
    spans=[]; cursor=0
    for s in plan["segments"]:
        a,b,tempo=float(s["start"]),float(s["end"]),float(s.get("tempo",1))
        if not all(math.isfinite(v) for v in (a,b,tempo)) or not 0<=a<b<=count/rate:
            raise ValueError("Invalid retime range or tempo")
        a,b=round(a*rate),round(b*rate); kind=s["kind"]
        if a!=cursor or b<=a: raise ValueError("Retime source timeline must be continuous")
        if kind not in ("speech","pause","cut") or (kind!="speech" and tempo!=1) or not .5<=tempo<=2:
            raise ValueError("Invalid retime segment kind or tempo")
        spans.append((s,a,b,tempo)); cursor=b
    if not spans or cursor!=count: raise ValueError("Retime timeline must cover source")
    def process(entry):
        s,a,b,tempo=entry
        if s["kind"]=="cut": return b""
        part=pcm[a*2:b*2]
        if tempo==1: return part
        # Silent context lets WSOLA settle and flush word tails before cropping.
        pad=round(rate*.12); skip=round(pad/tempo); length=round((b-a)/tempo)
        command=["ffmpeg","-v","error","-threads","1","-f","s16le","-ar",str(rate),
            "-ac","1","-i","pipe:0","-af",f"atempo={tempo},apad,atrim=start_sample={skip}:end_sample={skip+length}",
            "-f","s16le","-acodec","pcm_s16le","pipe:1"]
        result=subprocess.run(command,input=b"\0\0"*pad+part+b"\0\0"*pad,capture_output=True,check=True)
        if len(result.stdout)!=length*2: raise ValueError("Unexpected retimed sample count")
        return result.stdout
    with ThreadPoolExecutor(max_workers=4) as pool: parts=list(pool.map(process,spans))
    kept=[]; cuts=[]; frames=0
    for (s,a,b,tempo),part in zip(spans,parts):
        if s["kind"]=="cut":
            cuts.append({"start":a/rate,"end":b/rate,"reason":s.get("reason","")}); continue
        n=len(part)//2
        kept.append({"source_id":"baseline","source_start":a/rate,"source_end":b/rate,
            "output_start":frames/rate,"output_end":(frames+n)/rate,"tempo":tempo,
            "kind":s["kind"],"issue_id":s.get("issue_id"),"reason":s.get("reason","")})
        frames+=n
    data={"schema_version":3,"sources":{"baseline":inputs["source"]},
          "source_map":inputs["source_map"],"sample_rate":rate,"timeline":str(timeline.resolve()),
          "output":str(output.resolve()),"output_duration":frames/rate,"kept":kept,"cuts":cuts}
    validate_cut_map(data,frames/rate)
    output.parent.mkdir(parents=True,exist_ok=True); mapping.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(output),"wb") as w:
        w.setparams((1,2,rate,0,"NONE","")); w.writeframes(b"".join(parts))
    mapping.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")


def validate_cut_map(edit_map: dict, duration: float) -> None:
    if not math.isfinite(duration) or duration <= 0 or not math.isfinite(edit_map["output_duration"]):
        raise ValueError("Cut map duration must be finite and positive")
    if abs(edit_map["output_duration"] - duration) > 1 / 16000:
        raise ValueError("Cut map duration does not match audio")
    kept = edit_map["kept"]
    if edit_map.get("schema_version", 1) in (2, 3):
        rate = edit_map["sample_rate"]
        cursor = 0.0
        if not kept:
            raise ValueError("Cut map has no kept spans")
        for part in kept:
            source = edit_map["sources"].get(part["source_id"])
            values = [part[k] for k in ("source_start", "source_end", "output_start", "output_end")]
            if not source or not math.isfinite(source["duration"]) or not all(math.isfinite(v) for v in values):
                raise ValueError("Invalid source or times in cut map")
            a, b, x, y = values
            if not 0 <= a < b <= source["duration"] + 1 / rate:
                raise ValueError("Cut map source range is invalid")
            tempo = part.get("tempo", 1) if edit_map["schema_version"] == 3 else 1
            if not math.isfinite(tempo) or not .5 <= tempo <= 2:
                raise ValueError("Invalid cut map tempo")
            if edit_map["schema_version"] == 3 and (part.get("kind") not in ("speech", "pause") or
                    (part["kind"] == "pause" and tempo != 1)):
                raise ValueError("Pause must retain original duration")
            if abs(x - cursor) > 1 / rate or y <= x or abs((b-a)/tempo-(y-x)) > 1.01 / rate:
                raise ValueError("Cut map output is not continuous or has gaps")
            cursor = y
        if abs(cursor - duration) > 1 / rate:
            raise ValueError("Cut map does not cover audio")
        if edit_map["schema_version"] == 3:
            if set(edit_map["sources"]) != {"baseline"} or any(p["source_id"] != "baseline" for p in kept):
                raise ValueError("Retime source must be a single fixed baseline")
            if any(kept[i]["source_start"] < kept[i-1]["source_end"]-1/rate for i in range(1,len(kept))):
                raise ValueError("Retime source spans overlap or change order")
            source_duration=edit_map["sources"]["baseline"]["duration"]
            intervals=[(p["source_start"],p["source_end"]) for p in kept]
            for cut in edit_map["cuts"]:
                a,b=cut["start"],cut["end"]
                if not all(math.isfinite(v) for v in (a,b)) or not 0<=a<b<=source_duration+1/rate:
                    raise ValueError("Invalid retime source cut")
                intervals.append((a,b))
            position=0
            for a,b in sorted(intervals):
                if abs(a-position)>1/rate: raise ValueError("Retime source partition has gaps or overlaps")
                position=b
            if abs(position-source_duration)>1/rate: raise ValueError("Retime source partition is incomplete")
        return
    if edit_map.get("schema_version", 1) != 1:
        raise ValueError("Unknown cut map schema")
    cuts = edit_map["cuts"]
    source_duration = float(edit_map["source_duration"])
    if any(not 0 <= c["start"] < c["end"] <= source_duration + .001 for c in cuts):
        raise ValueError("Cut map contains invalid source times")
    if any(cuts[i]["start"] < cuts[i - 1]["end"] for i in range(1, len(cuts))):
        raise ValueError("Cut map cuts overlap")
    if not kept or any(kept[i]["source_start"] < kept[i - 1]["source_end"] for i in range(1, len(kept))):
        raise ValueError("Cut map kept spans overlap")
    if any(abs(kept[i]["output_start"] - kept[i - 1]["output_end"]) > .001 for i in range(1, len(kept))):
        raise ValueError("Cut map output has gaps")


def verify(audio: Path, mapping: Path, srt: Path, scenes: Path, video: Path) -> dict:
    duration = _duration(audio)
    edit_map = _read_json(mapping)
    validate_cut_map(edit_map, duration)
    cues = read_srt(srt)
    if cues and cues[-1]["end"] > duration + .05:
        raise ValueError("SRT extends beyond audio")
    load_scenes(scenes, duration)
    probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams",
                                                "-show_format", "-of", "json", str(video)], text=True, encoding="utf-8"))
    streams = probe["streams"]
    picture = next(s for s in streams if s["codec_type"] == "video")
    sound = next(s for s in streams if s["codec_type"] == "audio")
    if (picture["codec_name"], picture["width"], picture["height"], picture["r_frame_rate"],
            sound["codec_name"]) != ("h264", 1920, 1080, "30/1", "aac"):
        raise ValueError("MP4 codec, dimensions, or frame rate are incorrect")
    video_duration = float(probe["format"]["duration"])
    if abs(video_duration - duration) > .2:
        raise ValueError("MP4 duration does not match audio")
    return {"audio_seconds": duration, "video_seconds": video_duration,
            "cuts": len(edit_map["cuts"]), "cues": len(cues), "scenes": len(_read_json(scenes)["scenes"]),
            "video": "1920x1080 30fps H.264/AAC", "human_listening": "pending"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    audio = commands.add_parser("build-audio")
    for flag in ("source", "edits", "audio", "map"):
        audio.add_argument(f"--{flag}", type=Path, required=True)
    audio.add_argument("--scope", choices=("sample", "full"), default="sample")
    audio.add_argument("--run-id")
    assembly = commands.add_parser("assemble-audio")
    for flag in ("timeline", "audio", "map"):
        assembly.add_argument(f"--{flag}", type=Path, required=True)
    assembly.add_argument("--run-id", required=True)
    retime = commands.add_parser("retime-audio")
    for flag in ("timeline", "audio", "map"):
        retime.add_argument(f"--{flag}", type=Path, required=True)
    retime.add_argument("--run-id", required=True)
    captions = commands.add_parser("build-srt")
    for flag in ("alignment", "lines", "srt"):
        captions.add_argument(f"--{flag}", type=Path, required=True)
    video = commands.add_parser("render")
    for flag in ("audio", "srt", "scenes", "video"):
        video.add_argument(f"--{flag}", type=Path, required=True)
    video.add_argument("--font", type=Path)
    check = commands.add_parser("verify")
    for flag in ("audio", "map", "srt", "scenes", "video"):
        check.add_argument(f"--{flag}", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build-audio":
        build_audio(args.source, args.edits, args.audio, args.map, scope=args.scope, run_id=args.run_id)
    elif args.command == "assemble-audio":
        assemble_audio(args.timeline, args.audio, args.map, run_id=args.run_id)
    elif args.command == "retime-audio":
        retime_audio(args.timeline, args.audio, args.map, run_id=args.run_id)
    elif args.command == "build-srt":
        build_srt(args.alignment, args.lines, args.srt)
    elif args.command == "render":
        render_video(args.audio, args.srt, args.scenes, args.video, args.font)
    else:
        print(json.dumps(verify(args.audio, args.map, args.srt, args.scenes, args.video), ensure_ascii=False))


if __name__ == "__main__":
    main()
