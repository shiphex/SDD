#!/usr/bin/env python3
"""Transcribe audio with Qwen3-ASR and emit subtitles from forced alignment."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable


DEFAULT_ASR_MODEL = "Qwen/Qwen3-ASR-0.6B"
DEFAULT_ALIGNER_MODEL = "Qwen/Qwen3-ForcedAligner-0.6B"
ALIGNMENT_SAMPLE_RATE = 16_000
MAX_ALIGN_SEGMENT_SECONDS = 180.0
COMMON_CJK_WORDS = (
    "一些",
    "一份",
    "想法",
    "实现",
    "细节",
    "说明书",
    "开发计划",
    "开发形式",
    "规格驱动开发",
    "规格说明",
    "经验分享",
    "经验教训",
    "项目",
    "文档",
    "目标",
    "测试",
    "问题",
    "代码",
    "材料",
    "情况",
    "完整",
    "如何",
    "开始",
    "使用",
    "汇总",
    "驱动",
    "开发",
    "阶段",
    "计划",
    "检验",
    "成果",
    "记录",
    "分享",
    "经验",
    "教训",
)


def enable_windows_hf_cache_fallback() -> None:
    """Use regular cached files if HF's Windows symlink probe cannot write its temp file."""
    if os.name != "nt":
        return

    try:
        import huggingface_hub.file_download as hf_download
    except ImportError:
        return

    original_probe = hf_download.are_symlinks_supported

    def probe_or_copy(cache_dir: str | Path | None = None) -> bool:
        try:
            return original_probe(cache_dir)
        except PermissionError:
            # The probe creates a temporary directory below the cache. Some managed
            # Windows workspaces allow cache writes but deny writes inside that temp
            # directory; ordinary copy-based HF caching still works there.
            from huggingface_hub import constants

            resolved = str(
                Path(cache_dir or constants.HF_HUB_CACHE).expanduser().resolve()
            )
            hf_download._are_symlinks_supported_in_dir[resolved] = False
            return False

    hf_download.are_symlinks_supported = probe_or_copy


def value(item: Any, name: str, fallback: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(name, fallback)
    return getattr(item, name, fallback)


def timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds_part, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds_part:02d},{milliseconds:03d}"


def segment_timestamp(seconds: float) -> str:
    return timestamp(seconds).replace(",", ".")


def seconds_from_timestamp(value: str) -> float:
    match = re.fullmatch(r"(\d{2,}):(\d{2}):(\d{2})\.(\d{3})", value.strip())
    if not match:
        raise ValueError(f"Invalid segment timestamp: {value}")
    hours, minutes, seconds, milliseconds = map(int, match.groups())
    if minutes >= 60 or seconds >= 60:
        raise ValueError(f"Invalid segment timestamp: {value}")
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000


def is_punctuation(text: str) -> bool:
    return bool(text) and all(
        unicodedata.category(char).startswith("P") for char in text
    )


def is_cjk(text: str) -> bool:
    return any(
        "CJK" in unicodedata.name(char, "")
        or "HIRAGANA" in unicodedata.name(char, "")
        or "KATAKANA" in unicodedata.name(char, "")
        for char in text
    )


def aligned_items(raw_items: Iterable[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in raw_items:
        text = str(value(raw, "text", "")).strip()
        if not text:
            continue
        start = float(value(raw, "start_time", value(raw, "start", 0.0)))
        end = float(value(raw, "end_time", value(raw, "end", start)))
        if not math.isfinite(start) or not math.isfinite(end) or end < start:
            continue
        result.append({"text": text, "start": max(0.0, start), "end": max(0.0, end)})
    return result


def normalized_characters(text: str) -> str:
    return "".join(
        char
        for char in text
        if not char.isspace() and not unicodedata.category(char).startswith("P")
    )


def restore_punctuation(
    recognized_text: str, items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Restore ASR punctuation onto aligned text without changing any times."""
    expected = normalized_characters(recognized_text)
    actual = normalized_characters("".join(item["text"] for item in items))
    if expected != actual:
        raise ValueError(
            "ASR text and aligned text differ after punctuation and whitespace are "
            "removed; refusing to guess punctuation positions."
        )
    if not items:
        return items

    punctuation_at: dict[int, list[str]] = {}
    offset = 0
    for char in recognized_text:
        if char.isspace():
            continue
        if unicodedata.category(char).startswith("P"):
            punctuation_at.setdefault(offset, []).append(char)
        else:
            offset += 1

    restored = []
    offset = 0
    for item in items:
        parts: list[str] = []
        for char in item["text"]:
            if unicodedata.category(char).startswith("P"):
                continue
            parts.append(char)
            if not char.isspace():
                offset += 1
                parts.extend(punctuation_at.get(offset, []))
        restored_text = "".join(parts)
        if restored_text.strip():
            restored.append({**item, "text": restored_text})

    # Leading punctuation has no preceding aligned character; attach it to the
    # first aligned item. Trailing punctuation is normally attached in the loop.
    if punctuation_at.get(0):
        restored[0]["text"] = "".join(punctuation_at[0]) + restored[0]["text"]
    if offset < len(expected):
        raise ValueError("Could not map all ASR punctuation to aligned items.")
    return restored


def soften_continuing_full_stops(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove obvious false full stops before dependent continuations."""
    result = [dict(item) for item in items]
    dependent_starts = ("的", "地", "得")
    closing_marks = "）)]}】》」』’”\"'"

    for index, item in enumerate(result[:-1]):
        text = item["text"].rstrip()
        mark_index = len(text) - 1
        while mark_index >= 0 and text[mark_index] in closing_marks:
            mark_index -= 1
        if mark_index < 0 or text[mark_index] != "。":
            continue

        following = normalized_characters(
            "".join(later["text"] for later in result[index + 1 :])
        )
        preceding = normalized_characters(
            "".join(earlier["text"] for earlier in result[: index + 1])
        )
        if not following:
            continue
        is_dependent_start = following.startswith(dependent_starts)
        continues_with_verb = following.startswith("来")
        is_restarted_continuation = preceding.endswith("先") and following.startswith("先")
        if is_dependent_start:
            item["text"] = text[:mark_index] + text[mark_index + 1 :]
            if preceding.endswith("是") and following.startswith("的"):
                for later in result[index + 1 :]:
                    char_index = next(
                        (
                            char_index
                            for char_index, char in enumerate(later["text"])
                            if not char.isspace()
                            and not unicodedata.category(char).startswith("P")
                        ),
                        None,
                    )
                    if char_index is None:
                        continue
                    if later["text"][char_index] == "的":
                        later["text"] = (
                            later["text"][: char_index + 1]
                            + "，"
                            + later["text"][char_index + 1 :]
                        )
                    break
        elif continues_with_verb or is_restarted_continuation:
            item["text"] = text[:mark_index] + "，" + text[mark_index + 1 :]
    return result


def visible_length(items: list[dict[str, Any]]) -> int:
    return sum(sum(not char.isspace() for char in item["text"]) for item in items)


def rendered_text(items: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    previous_lexical_item_cjk: bool | None = None
    for item in items:
        token = item["text"]
        if is_punctuation(token):
            parts.append(token)
            continue
        token_cjk = is_cjk(token)
        if parts and not token_cjk and previous_lexical_item_cjk is False:
            parts.append(" ")
        parts.append(token)
        previous_lexical_item_cjk = token_cjk
    return "".join(parts).strip()


def transcript_segments_from_items(
    items: list[dict[str, Any]], duration: float
) -> list[dict[str, Any]]:
    """Group aligned ASR text into the same maximum-sized blocks as Qwen alignment."""
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Audio duration must be a positive finite number.")

    sections: list[dict[str, Any]] = []
    section_count = math.ceil(duration / MAX_ALIGN_SEGMENT_SECONDS)
    for index in range(section_count):
        start = index * MAX_ALIGN_SEGMENT_SECONDS
        end = min(start + MAX_ALIGN_SEGMENT_SECONDS, duration)
        section_items = [
            item
            for item in items
            if start - 0.001 <= item["start"] < end
        ]
        for item in section_items:
            if item["end"] > end + 0.05:
                raise ValueError(
                    "An aligned item crosses a 180-second transcript boundary; "
                    "inspect the Qwen alignment output."
                )
        sections.append(
            {"start": start, "end": end, "text": rendered_text(section_items)}
        )
    return sections


def transcript_markdown(
    sections: list[dict[str, Any]], language: str = "Chinese"
) -> str:
    lines = [
        "# ASR 转写校对稿",
        "",
        f"<!-- language: {language} -->",
        "<!-- 校对正文即可；保留每个音频段标题和时间范围。 -->",
        "",
    ]
    for index, section in enumerate(sections, start=1):
        lines.extend(
            [
                f"## 音频段 {index:03d} | {segment_timestamp(section['start'])} - {segment_timestamp(section['end'])}",
                str(section["text"]),
                "",
            ]
        )
    return "\n".join(lines)


def parse_transcript_sections(markdown: str, duration: float) -> list[dict[str, Any]]:
    """Parse the editable transcript sections used for chunk-limited realignment."""
    header = re.compile(
        r"^## 音频段 (\d{3,}) \| (\d{2,}:\d{2}:\d{2}\.\d{3}) - (\d{2,}:\d{2}:\d{2}\.\d{3})\s*$",
        re.MULTILINE,
    )
    matches = list(header.finditer(markdown))
    if not matches:
        raise ValueError("No 音频段 headings were found in the corrected transcript.")
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Audio duration must be a positive finite number.")

    sections: list[dict[str, Any]] = []
    expected_start = 0.0
    for index, match in enumerate(matches, start=1):
        number = int(match.group(1))
        if number != index:
            raise ValueError("Audio segment headings must be numbered consecutively.")
        start = seconds_from_timestamp(match.group(2))
        end = seconds_from_timestamp(match.group(3))
        if abs(start - expected_start) > 0.001:
            raise ValueError("Audio segment ranges must be contiguous from 00:00:00.000.")
        if end <= start:
            raise ValueError("Audio segment end must follow its start.")
        if end - start > MAX_ALIGN_SEGMENT_SECONDS + 0.0005:
            raise ValueError("Each audio segment must be no longer than 180 seconds.")

        body_start = match.end()
        body_end = matches[index].start() if index < len(matches) else len(markdown)
        body = markdown[body_start:body_end].strip()
        body_lines = [
            line.rstrip()
            for line in body.splitlines()
            if line.strip() and not line.strip().startswith("<!--")
        ]
        sections.append({"start": start, "end": end, "text": "\n".join(body_lines)})
        expected_start = end

    if abs(expected_start - duration) > 0.05:
        raise ValueError(
            "Transcript segment ranges must cover the complete audio duration "
            "(within 50 ms)."
        )
    return sections


def align_transcript_sections(
    sections: list[dict[str, Any]], waveform: Any, aligner: Any, language: str
) -> list[dict[str, Any]]:
    """Align corrected text against each section and restore absolute audio offsets."""
    items: list[dict[str, Any]] = []
    sample_count = len(waveform)
    audio_duration = sample_count / ALIGNMENT_SAMPLE_RATE
    for section in sections:
        text = str(section["text"]).strip()
        if not normalized_characters(text):
            continue
        start = float(section["start"])
        end = float(section["end"])
        start_sample = round(start * ALIGNMENT_SAMPLE_RATE)
        end_sample = round(end * ALIGNMENT_SAMPLE_RATE)
        if start < 0 or end <= start or end > audio_duration + 0.05:
            raise ValueError("Transcript section lies outside the decoded audio.")
        audio_chunk = waveform[start_sample:min(end_sample, sample_count)]
        if len(audio_chunk) == 0:
            raise ValueError("Transcript section contains text but no audio samples.")

        result = aligner.align(
            audio=(audio_chunk, ALIGNMENT_SAMPLE_RATE), text=text, language=language
        )[0]
        section_items = aligned_items(value(result, "items", []))
        section_items = restore_punctuation(text, section_items)
        for item in section_items:
            items.append(
                {
                    "text": item["text"],
                    "start": round(item["start"] + start, 3),
                    "end": round(item["end"] + start, 3),
                }
            )
    return soften_continuing_full_stops(items)


def audio_duration_seconds(audio_file: Path) -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(audio_file.resolve()),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        duration = float(result.stdout.strip())
    except FileNotFoundError as error:
        raise ValueError("ffprobe is required to write a segmented transcript.") from error
    except (subprocess.CalledProcessError, ValueError) as error:
        raise ValueError(f"Could not read audio duration with ffprobe: {audio_file}") from error
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError(f"Audio duration is invalid: {audio_file}")
    return duration


def validate_full_recording_gate(
    duration: float, workflow_state: dict[str, Any] | None, run_id: str | None
) -> None:
    """Require an approved sample before this CLI handles long workflow audio."""
    if duration <= 180.05:
        return
    if not run_id:
        raise ValueError(
            "Audio longer than 180 seconds requires VIDEO_RUN_ID and a current "
            "sample_acceptance approval. Use the workflow PowerShell entrypoint."
        )
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", run_id):
        raise ValueError("VIDEO_RUN_ID must be a short filename-safe run ID.")
    if workflow_state is None:
        raise ValueError(
            f"Audio longer than 180 seconds requires .local/video/{run_id}/workflow.json."
        )
    gates = workflow_state.get("gates")
    sample_gate = gates.get("sample_acceptance") if isinstance(gates, dict) else None
    if not isinstance(sample_gate, dict) or sample_gate.get("status") != "approved":
        raise ValueError("Full recording work requires a current sample_acceptance approval.")
    stage = workflow_state.get("stage")
    if stage not in {"full_transcript", "full_final_transcript"}:
        raise ValueError(
            "Set full_transcript or full_final_transcript before processing long audio."
        )


def verify_audio_workflow_gate(audio_file: Path) -> float:
    """Reconcile and verify approved audio identity before model inference."""
    duration = audio_duration_seconds(audio_file)
    if duration <= 180.05:
        return duration
    run_id = os.environ.get("VIDEO_RUN_ID")
    if not run_id:
        raise ValueError(
            "Audio longer than 180 seconds requires VIDEO_RUN_ID and current workflow approval."
        )
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", run_id):
        raise ValueError("VIDEO_RUN_ID must be a short filename-safe run ID.")

    powershell = shutil.which("pwsh") or shutil.which("powershell") or shutil.which("powershell.exe")
    if not powershell:
        raise ValueError(
            "PowerShell is required to reconcile workflow hashes and verify long-audio approval."
        )
    repo_root = Path(__file__).resolve().parents[4]
    state_script = repo_root / ".agent" / "skills" / "video-workflow" / "scripts" / "workflow-state.ps1"
    try:
        result = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-File",
                str(state_script),
                "-Action",
                "assert-audio-approved",
                "-RunId",
                run_id,
                "-InputAudio",
                str(audio_file),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise ValueError("Could not start PowerShell to verify long-audio workflow approval.") from error
    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        raise ValueError(f"Workflow approval check failed for long audio: {details}")
    return duration


def ends_with_mark(text: str, marks: str) -> bool:
    closing_marks = "）)]}】》」』’”\"'"
    for char in reversed(text.rstrip()):
        if char in marks:
            return True
        if char in closing_marks:
            continue
        return False
    return False


def sentence_ending(text: str) -> bool:
    return ends_with_mark(text, "。！？!?．.")


def clause_ending(text: str) -> bool:
    return ends_with_mark(text, "，,；;、：:")


def boundaries_inside_common_words(items: list[dict[str, Any]]) -> set[int]:
    text = normalized_characters("".join(item["text"] for item in items))
    unsafe: set[int] = set()
    for word in COMMON_CJK_WORDS:
        start = 0
        while True:
            start = text.find(word, start)
            if start < 0:
                break
            unsafe.update(range(start + 1, start + len(word)))
            start += 1
    return unsafe


def split_long_sentence(
    sentence: list[dict[str, Any]], max_chars: int
) -> list[list[dict[str, Any]]]:
    chunks: list[list[dict[str, Any]]] = []
    remaining = sentence
    minimum_natural_chunk = max(4, max_chars // 3)

    if any(
        sum(not char.isspace() for char in item["text"]) > max_chars
        for item in sentence
    ):
        raise ValueError(
            "An aligned item is longer than --max-chars; adjust the limit or "
            "inspect the aligner output."
        )

    while visible_length(remaining) > max_chars:
        lengths = []
        total = 0
        for item in remaining:
            total += sum(not char.isspace() for char in item["text"])
            lengths.append(total)
        unsafe_boundaries = boundaries_inside_common_words(remaining)
        lexical_lengths = []
        lexical_total = 0
        for item in remaining:
            lexical_total += len(normalized_characters(item["text"]))
            lexical_lengths.append(lexical_total)

        def safe_boundary(index: int) -> bool:
            return lexical_lengths[index - 1] not in unsafe_boundaries

        def follows_audible_pause(index: int) -> bool:
            if index >= len(remaining):
                return False
            return remaining[index]["start"] - remaining[index - 1]["end"] >= 1.5

        if lengths and lengths[0] > max_chars:
            raise ValueError(
                "An aligned item is longer than --max-chars; adjust the limit or "
                "inspect the aligner output."
            )

        natural_breaks = [
            index + 1
            for index, item in enumerate(remaining)
            if minimum_natural_chunk <= lengths[index] <= max_chars
            and (
                not 0 < visible_length(remaining[index + 1 :]) < minimum_natural_chunk
                or follows_audible_pause(index + 1)
            )
            and clause_ending(item["text"])
            and safe_boundary(index + 1)
        ]
        if natural_breaks:
            break_at = natural_breaks[-1]
        else:
            target_length = max_chars
            if visible_length(remaining) <= max_chars + minimum_natural_chunk:
                target_length = visible_length(remaining) - minimum_natural_chunk
            candidates = [
                index + 1
                for index, length in enumerate(lengths)
                if length <= target_length
            ]
            safe_candidates = [index for index in candidates if safe_boundary(index)]
            break_at = max(safe_candidates or candidates, default=0)
        if break_at == 0:
            raise ValueError("Could not split an aligned sentence under --max-chars.")
        chunks.append(remaining[:break_at])
        remaining = remaining[break_at:]

    if remaining:
        chunks.append(remaining)
    return chunks


def split_at_long_pauses(
    sentence: list[dict[str, Any]], max_chars: int
) -> list[list[dict[str, Any]]]:
    chunks: list[list[dict[str, Any]]] = []
    start = 0
    minimum_chunk = max(4, max_chars // 3)
    for index, item in enumerate(sentence[:-1]):
        pause = sentence[index + 1]["start"] - item["end"]
        if (
            pause >= 1.5
            and clause_ending(item["text"])
            and visible_length(sentence[start : index + 1]) >= minimum_chunk
        ):
            chunks.append(sentence[start : index + 1])
            start = index + 1
    if start < len(sentence):
        chunks.append(sentence[start:])
    return chunks


def subtitle_cues(items: list[dict[str, Any]], max_chars: int) -> list[dict[str, Any]]:
    """Split on sentence marks, then clause marks or the hard visible-length cap."""
    sentences: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for item in items:
        current.append(item)
        if sentence_ending(item["text"]):
            sentences.append(current)
            current = []
    if current:
        sentences.append(current)

    cues: list[dict[str, Any]] = []
    for sentence in sentences:
        for pause_chunk in split_at_long_pauses(sentence, max_chars):
            for chunk in split_long_sentence(pause_chunk, max_chars):
                text = rendered_text(chunk)
                if text:
                    cues.append(
                        {
                            "start": chunk[0]["start"],
                            "end": chunk[-1]["end"],
                            "text": text,
                        }
                    )
    return cues


def srt_text(cues: list[dict[str, Any]]) -> str:
    blocks = []
    for index, cue in enumerate(cues, start=1):
        blocks.append(
            f"{index}\n{timestamp(cue['start'])} --> {timestamp(cue['end'])}\n{cue['text']}"
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create an SRT using Qwen3-ASR and Qwen3-ForcedAligner timestamps."
    )
    parser.add_argument("audio_file", type=Path, nargs="?", help="Input audio file")
    parser.add_argument(
        "--alignment-input",
        type=Path,
        help="Resegment an existing alignment JSON without rerunning either model",
    )
    parser.add_argument(
        "--transcript-input",
        type=Path,
        help="Align a human-corrected, sectioned Markdown transcript to the input audio",
    )
    parser.add_argument(
        "--transcript-output",
        type=Path,
        help="Write the ASR transcript in editable audio sections (default: alongside SRT)",
    )
    parser.add_argument("--output", type=Path, help="SRT output path")
    parser.add_argument("--json-output", type=Path, help="Aligned transcript JSON path")
    parser.add_argument("--language", default="Chinese", help="Qwen language name or auto")
    parser.add_argument("--max-chars", type=int, default=22)
    parser.add_argument("--asr-model", default=DEFAULT_ASR_MODEL)
    parser.add_argument("--aligner-model", default=DEFAULT_ALIGNER_MODEL)
    parser.add_argument("--device", default="auto", help="auto, cpu, or cuda:N")
    parser.add_argument("--dtype", choices=("auto", "bf16", "fp16", "fp32"), default="auto")
    parser.add_argument("--max-new-tokens", type=int, default=2048)
    return parser.parse_args()


def model_device_config(args: argparse.Namespace, torch: Any) -> tuple[str, Any]:
    use_cuda = args.device == "auto" and torch.cuda.is_available()
    if args.device.startswith("cuda"):
        if not torch.cuda.is_available():
            raise ValueError("CUDA was requested, but PyTorch cannot access a CUDA device.")
        if args.device != "cuda" and not re.fullmatch(r"cuda:\d+", args.device):
            raise ValueError("--device must be auto, cpu, cuda, or cuda:N")
        device_map = args.device if ":" in args.device else "cuda:0"
        use_cuda = True
    elif args.device == "cpu":
        device_map = "cpu"
    elif args.device == "auto":
        device_map = "cuda:0" if use_cuda else "cpu"
    else:
        raise ValueError("--device must be auto, cpu, cuda, or cuda:N")

    if args.dtype == "auto":
        if not use_cuda:
            dtype = torch.float32
        elif torch.cuda.is_bf16_supported():
            dtype = torch.bfloat16
        else:
            dtype = torch.float16
    else:
        dtype = {
            "bf16": torch.bfloat16,
            "fp16": torch.float16,
            "fp32": torch.float32,
        }[args.dtype]
    return device_map, dtype


def write_alignment_files(
    output: Path, json_output: Path, payload: dict[str, Any], items: list[dict[str, Any]], cues: list[dict[str, Any]], max_chars: int
) -> None:
    payload["items"] = items
    payload["subtitles"] = cues
    payload["subtitle_max_chars"] = max_chars
    output.parent.mkdir(parents=True, exist_ok=True)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(srt_text(cues), encoding="utf-8")
    json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(cues)} subtitle cues and {len(items)} aligned items.")
    print(f"SRT: {output}")
    print(f"Aligned JSON: {json_output}")


def main() -> int:
    args = parse_args()
    if args.max_chars < 4:
        print("--max-chars must be at least 4", file=sys.stderr)
        return 2

    if args.alignment_input and args.transcript_input:
        print("Pass only one of --alignment-input and --transcript-input.", file=sys.stderr)
        return 2

    if args.alignment_input:
        if args.audio_file or args.transcript_output:
            print("Pass either audio_file or --alignment-input, not both.", file=sys.stderr)
            return 2
        if not args.alignment_input.is_file():
            print(f"Alignment JSON does not exist: {args.alignment_input}", file=sys.stderr)
            return 2
        if not args.output:
            print("--output is required with --alignment-input.", file=sys.stderr)
            return 2
        output = args.output
        json_output = args.json_output or args.alignment_input
        try:
            payload = json.loads(args.alignment_input.read_text(encoding="utf-8"))
            items = aligned_items(payload.get("items", []))
            items = restore_punctuation(str(payload.get("text", "")), items)
            items = soften_continuing_full_stops(items)
            cues = subtitle_cues(items, args.max_chars)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            print(f"Could not resegment alignment JSON: {error}", file=sys.stderr)
            return 2
        write_alignment_files(output, json_output, payload, items, cues, args.max_chars)
        return 0

    if args.transcript_input:
        if not args.audio_file:
            print("Pass an audio_file with --transcript-input.", file=sys.stderr)
            return 2
        if not args.audio_file.is_file():
            print(f"Input audio does not exist: {args.audio_file}", file=sys.stderr)
            return 2
        if not args.transcript_input.is_file():
            print(f"Corrected transcript does not exist: {args.transcript_input}", file=sys.stderr)
            return 2
        if args.transcript_output:
            print("--transcript-output is only used when running ASR.", file=sys.stderr)
            return 2
        if args.language.lower() == "auto":
            print("Choose an explicit --language for forced alignment.", file=sys.stderr)
            return 2
        try:
            verify_audio_workflow_gate(args.audio_file)
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 2

        output = args.output or args.audio_file.with_suffix(".srt")
        json_output = args.json_output or output.with_suffix(".json")
        try:
            import torch

            enable_windows_hf_cache_fallback()
            from qwen_asr import Qwen3ForcedAligner
            from qwen_asr.inference.utils import normalize_audios

            device_map, dtype = model_device_config(args, torch)
            waveform = normalize_audios(str(args.audio_file.resolve()))[0]
            duration = len(waveform) / ALIGNMENT_SAMPLE_RATE
            transcript_text = args.transcript_input.read_text(encoding="utf-8")
            sections = parse_transcript_sections(transcript_text, duration)
            aligner = Qwen3ForcedAligner.from_pretrained(
                args.aligner_model, dtype=dtype, device_map=device_map
            )
            items = align_transcript_sections(sections, waveform, aligner, args.language)
            cues = subtitle_cues(items, args.max_chars)
        except ImportError as error:
            print(
                "Qwen dependencies are missing. Run the PowerShell entrypoint or "
                "`uv sync --project .agent/skills/audio-to-srt` first.",
                file=sys.stderr,
            )
            raise error
        except (OSError, ValueError, TypeError) as error:
            print(f"Could not align the corrected transcript: {error}", file=sys.stderr)
            return 2

        write_alignment_files(
            output,
            json_output,
            {
                "schema_version": 2,
                "language": args.language,
                "text": "\n".join(section["text"] for section in sections),
                "aligner_model": args.aligner_model,
                "alignment_unit": "Qwen3-ForcedAligner; human-corrected transcript; section offsets restored",
                "transcript_sections": sections,
            },
            items,
            cues,
            args.max_chars,
        )
        return 0

    if not args.audio_file:
        print("Pass an audio_file, --alignment-input, or --transcript-input.", file=sys.stderr)
        return 2
    if not args.audio_file.is_file():
        print(f"Input audio does not exist: {args.audio_file}", file=sys.stderr)
        return 2

    output = args.output or args.audio_file.with_suffix(".srt")
    json_output = args.json_output or output.with_suffix(".json")
    transcript_output = args.transcript_output or output.with_suffix(".transcript.md")

    try:
        verified_duration = verify_audio_workflow_gate(args.audio_file)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    try:
        import torch

        enable_windows_hf_cache_fallback()
        from qwen_asr import Qwen3ASRModel
    except ImportError as error:
        print(
            "Qwen dependencies are missing. Run the PowerShell entrypoint or "
            "`uv sync --project .agent/skills/audio-to-srt` first.",
            file=sys.stderr,
        )
        raise error

    try:
        device_map, dtype = model_device_config(args, torch)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    print(f"Loading Qwen3-ASR with {device_map}; timestamps use the forced aligner.")
    model = Qwen3ASRModel.from_pretrained(
        args.asr_model,
        dtype=dtype,
        device_map=device_map,
        max_inference_batch_size=1,
        max_new_tokens=args.max_new_tokens,
        forced_aligner=args.aligner_model,
        forced_aligner_kwargs={"dtype": dtype, "device_map": device_map},
    )
    language = None if args.language.lower() == "auto" else args.language
    transcription = model.transcribe(
        audio=str(args.audio_file.resolve()),
        language=language,
        return_time_stamps=True,
    )[0]

    items = aligned_items(transcription.time_stamps or [])
    items = restore_punctuation(transcription.text, items)
    items = soften_continuing_full_stops(items)
    cues = subtitle_cues(items, args.max_chars)
    try:
        sections = transcript_segments_from_items(items, verified_duration)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    write_alignment_files(
        output,
        json_output,
        {
            "schema_version": 2,
            "language": transcription.language,
            "text": transcription.text,
            "asr_model": args.asr_model,
            "aligner_model": args.aligner_model,
            "alignment_unit": (
                "Qwen3-ForcedAligner output; original timings preserved; "
                "ASR punctuation restored by character offset"
            ),
            "transcript_sections": sections,
        },
        items,
        cues,
        args.max_chars,
    )
    transcript_output.parent.mkdir(parents=True, exist_ok=True)
    transcript_output.write_text(
        transcript_markdown(sections, transcription.language), encoding="utf-8"
    )
    print(f"Transcript for proofreading: {transcript_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
