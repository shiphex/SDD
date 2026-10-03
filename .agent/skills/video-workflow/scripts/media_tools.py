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
import unicodedata
import wave
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


def build_audio(source: Path, edits: Path, output: Path, mapping: Path) -> None:
    """Cut source-time intervals from a mono 16-bit WAV; record every kept span."""
    with wave.open(str(source), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getcomptype() != "NONE":
            raise ValueError("Source must be uncompressed mono 16-bit PCM WAV")
        rate = wav.getframerate()
        samples = array.array("h", wav.readframes(wav.getnframes()))
    if sys.byteorder != "little":
        samples.byteswap()
    count = len(samples)
    duration = count / rate
    if duration > 180.05:
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


def verify(audio: Path, mapping: Path, srt: Path, scenes: Path, video: Path) -> dict:
    duration = _duration(audio)
    edit_map = _read_json(mapping)
    if abs(edit_map["output_duration"] - duration) > 1 / 16000:
        raise ValueError("Cut map duration does not match audio")
    kept = edit_map["kept"]
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
    cues = read_srt(srt)
    if cues and cues[-1]["end"] > duration + .05:
        raise ValueError("SRT extends beyond audio")
    load_scenes(scenes, duration)
    probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams",
                                                "-show_format", "-of", "json", str(video)], text=True))
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
        build_audio(args.source, args.edits, args.audio, args.map)
    elif args.command == "build-srt":
        build_srt(args.alignment, args.lines, args.srt)
    elif args.command == "render":
        render_video(args.audio, args.srt, args.scenes, args.video, args.font)
    else:
        print(json.dumps(verify(args.audio, args.map, args.srt, args.scenes, args.video), ensure_ascii=False))


if __name__ == "__main__":
    main()
