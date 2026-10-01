#!/usr/bin/env python3
"""Turn an Auto-Editor v2 timeline into a private, review-only silence report."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def seconds_from_frames(value: float, timebase: str) -> float:
    numerator, denominator = timebase.split("/", 1)
    return float(value) * int(denominator) / int(numerator)


def clock(seconds: float) -> str:
    millis = round(max(0.0, seconds) * 1000)
    minutes, millis = divmod(millis, 60_000)
    whole_seconds, millis = divmod(millis, 1000)
    return f"{minutes:02d}:{whole_seconds:02d}.{millis:03d}"


def read_kept_ranges(timeline: dict) -> list[tuple[float, float]]:
    timebase = timeline.get("tb") or timeline.get("timebase")
    if not timebase:
        raise ValueError("Auto-Editor timeline has no timebase")
    effects = timeline.get("effects", [[]])
    clips = timeline.get("clips")
    if clips is None:
        raise ValueError("Expected an Auto-Editor v2 timeline with a 'clips' array")

    kept = []
    for clip in clips:
        start, end, effect_index = clip[:3]
        effect = effects[int(effect_index)] if int(effect_index) < len(effects) else []
        if "cut" in effect:
            continue
        kept.append(
            (
                seconds_from_frames(start, timebase),
                seconds_from_frames(end, timebase),
            )
        )
    return sorted(kept)


def removed_ranges(kept: list[tuple[float, float]], duration: float) -> list[tuple[float, float]]:
    removed = []
    cursor = 0.0
    for start, end in kept:
        start = min(max(0.0, start), duration)
        end = min(max(start, end), duration)
        if start - cursor >= 0.25:
            removed.append((cursor, start))
        cursor = max(cursor, end)
    if duration - cursor >= 0.25:
        removed.append((cursor, duration))
    return removed


def time_candidates(alignment: dict, duration: float) -> tuple[list[str], str]:
    """Flag transcript spans for human review without judging their correctness."""
    subtitle_cues = alignment.get("subtitles", [])
    term_candidates: list[str] = []
    token_pattern = re.compile(r"[A-Za-z][A-Za-z0-9._+-]*|\d+(?:[.,]\d+)?%?")
    for cue in subtitle_cues:
        terms = sorted(set(token_pattern.findall(str(cue.get("text", "")))))
        if not terms:
            continue
        start = float(cue.get("start", 0.0))
        end = float(cue.get("end", start))
        term_candidates.append(
            f"- `{clock(start)}–{clock(end)}`：识别稿包含 `{', '.join(terms)}`；"
            "对照录音核对专有名词、缩写或数值的读法和写法，机器不判断事实是否正确。"
        )

    if subtitle_cues:
        last_cue = subtitle_cues[-1]
        end = min(duration, float(last_cue.get("end", duration)))
        start = max(0.0, min(float(last_cue.get("start", end)), end - 5.0))
        tail = (
            f"`{clock(start)}–{clock(end)}`（样片结尾附近）：试听最后一句是否在固定样片边界前自然收束；"
            "若句意仍未完成，再补录收尾或延长样片。"
        )
    else:
        tail = f"`{clock(max(0.0, duration - 5.0))}–{clock(duration)}`：检查样片末尾是否截断句子。"
    return term_candidates, tail


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("timeline", type=Path)
    parser.add_argument("duration", type=float, help="Source sample duration in seconds")
    parser.add_argument("output", type=Path)
    parser.add_argument("--alignment", type=Path, help="Optional private Qwen alignment JSON")
    args = parser.parse_args()

    timeline = json.loads(args.timeline.read_text(encoding="utf-8"))
    gaps = removed_ranges(read_kept_ranges(timeline), args.duration)
    term_candidates: list[str] = []
    tail_candidate = (
        f"`{clock(max(0.0, args.duration - 5.0))}–{clock(args.duration)}`：试听样片末尾是否在固定边界前自然收束；"
        "若句意仍未完成，再补录收尾或延长样片。"
    )
    if args.alignment:
        alignment = json.loads(args.alignment.read_text(encoding="utf-8"))
        term_candidates, tail_candidate = time_candidates(alignment, args.duration)
    lines = [
        "# 样片剪辑审阅清单",
        "",
        f"素材范围：录音开头连续 {args.duration / 60:.0f} 分钟。时间码均对应未剪辑样片。",
        "",
        "此表记录机器候选。它不修改音频、不判定事实；每项都需在 Shotcut 中试听后由你决定。",
        "",
        "## A｜可考虑删改：静音粗剪候选",
        "",
        "Auto-Editor 按音频响度生成候选，切点余量设为 0.2 秒。请检查停顿、呼吸和句间节奏，再决定是否采用。",
        "",
    ]
    if gaps:
        for start, end in gaps:
            lines.append(
                f"- `{clock(start)}–{clock(end)}`（{end - start:.2f} 秒）：静音检测候选；试听后确认是否删除或保留。"
            )
    else:
        lines.append("- 没有达到 0.25 秒的静音删除区间。")

    lines.extend(
        [
            "",
            "## B｜需要你判断：表达、术语与内容顺序",
            "",
            "机器流程不判定事实正确性，也不自动改写口播。以下项目只提示复核位置：",
            "",
            "## C｜建议补录",
            "",
            f"- {tail_candidate} 若试听发现听不清、句子不完整或改稿后缺少承接，再填写需要补录的内容和衔接方式。",
            "",
            "## Shotcut 审阅记录",
            "",
            "- 采用的 A 候选：",
            "- 保留但调整的切点：",
            "- 需要改稿或补录的 B/C 项：",
            "- 人工抽听：术语、切点、补录衔接：待审阅",
            "",
        ]
    )
    c_index = lines.index("## C｜建议补录")
    review_lines = term_candidates or [
        "- 未自动检出拉丁字母或数字片段；仍需对照录音核对术语、数字、重复起句和句意。"
    ]
    lines[c_index:c_index] = [*review_lines, ""]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(gaps)} silence candidates to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
