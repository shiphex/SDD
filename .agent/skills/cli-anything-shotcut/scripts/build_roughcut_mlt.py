#!/usr/bin/env python3
"""Build a Shotcut MLT audio rough cut from an Auto-Editor v2 timeline."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def seconds(frame: float, timebase: str) -> float:
    numerator, denominator = timebase.split("/", 1)
    return float(frame) * int(denominator) / int(numerator)


def timecode(value: float) -> str:
    millis = round(max(0.0, value) * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    whole_seconds, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{millis:03d}"


def keep_ranges(timeline: dict) -> list[tuple[float, float]]:
    timebase = timeline.get("tb") or timeline.get("timebase")
    if not timebase:
        raise ValueError("Auto-Editor timeline has no timebase")
    effects = timeline.get("effects", [[]])
    clips = timeline.get("clips")
    if clips is None:
        raise ValueError("Expected Auto-Editor v2 timeline with a 'clips' array")
    ranges = []
    for clip in clips:
        start, end, effect_index = clip[:3]
        effect = effects[int(effect_index)] if int(effect_index) < len(effects) else []
        if "cut" in effect:
            continue
        start_seconds = seconds(start, timebase)
        end_seconds = seconds(end, timebase)
        if end_seconds <= start_seconds:
            continue
        ranges.append((start_seconds, end_seconds))
    return sorted(ranges)


def cli(args: list[str]) -> str:
    executable = shutil.which("cli-anything-shotcut")
    if executable is None:
        raise RuntimeError("cli-anything-shotcut is not available in the current UV environment")
    result = subprocess.run(
        [executable, *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Shotcut CLI failed")
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("timeline", type=Path)
    parser.add_argument("audio", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    timeline_path = args.timeline.resolve()
    audio_path = args.audio.resolve()
    output_path = args.output.resolve()
    if not timeline_path.is_file() or not audio_path.is_file():
        parser.error("timeline and source audio must both exist")
    if output_path.exists():
        parser.error(f"refusing to overwrite an existing project: {output_path}")

    data = json.loads(timeline_path.read_text(encoding="utf-8"))
    ranges = keep_ranges(data)
    if not ranges:
        parser.error("the rough-cut timeline has no kept ranges")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        cli(["project", "new", "--profile", "hd1080p30", "-o", output_path.as_posix()])
        track_output = cli(
            [
                "--project",
                output_path.as_posix(),
                "--save",
                "timeline",
                "add-track",
                "--type",
                "audio",
                "--name",
                "Voice",
            ]
        )
        match = re.search(r"(?:track_index:\s*|track at index\s+)(\d+)", track_output)
        if not match:
            raise RuntimeError("Shotcut CLI did not report the new audio track index")
        track_index = match.group(1)
        resource = audio_path.as_posix()

        for start, end in ranges:
            cli(
                [
                    "--project",
                    output_path.as_posix(),
                    "--save",
                    "timeline",
                    "add-clip",
                    resource,
                    "--track",
                    track_index,
                    "--in",
                    timecode(start),
                    "--out",
                    timecode(end),
                ]
            )
    except Exception:
        output_path.unlink(missing_ok=True)
        raise

    print(f"Created a Shotcut audio rough cut with {len(ranges)} kept ranges.")
    print(f"Project: {output_path}")
    print("The MLT project references the unchanged source sample; all silence edits remain reversible.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Could not create Shotcut rough cut: {error}", file=sys.stderr)
        raise SystemExit(1)
