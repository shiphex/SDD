#!/usr/bin/env python3
"""Transcribe audio with Qwen3-ASR and emit subtitles from forced alignment."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable


DEFAULT_ASR_MODEL = "Qwen/Qwen3-ASR-0.6B"
DEFAULT_ALIGNER_MODEL = "Qwen/Qwen3-ForcedAligner-0.6B"
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


def main() -> int:
    args = parse_args()
    if args.max_chars < 4:
        print("--max-chars must be at least 4", file=sys.stderr)
        return 2

    if args.alignment_input:
        if args.audio_file:
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
        payload["items"] = items
        payload["subtitles"] = cues
        payload["subtitle_max_chars"] = args.max_chars
        output.parent.mkdir(parents=True, exist_ok=True)
        json_output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(srt_text(cues), encoding="utf-8")
        json_output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Wrote {len(cues)} subtitle cues and {len(items)} aligned items.")
        print(f"SRT: {output}")
        print(f"Aligned JSON: {json_output}")
        return 0

    if not args.audio_file:
        print("Pass an audio_file or --alignment-input.", file=sys.stderr)
        return 2
    if not args.audio_file.is_file():
        print(f"Input audio does not exist: {args.audio_file}", file=sys.stderr)
        return 2

    output = args.output or args.audio_file.with_suffix(".srt")
    json_output = args.json_output or output.with_suffix(".json")

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

    use_cuda = args.device == "auto" and torch.cuda.is_available()
    if args.device.startswith("cuda"):
        if not torch.cuda.is_available():
            print("CUDA was requested, but PyTorch cannot access a CUDA device.", file=sys.stderr)
            return 2
        device_map = args.device if ":" in args.device else "cuda:0"
        use_cuda = True
    elif args.device == "cpu":
        device_map = "cpu"
    elif args.device == "auto":
        device_map = "cuda:0" if use_cuda else "cpu"
    else:
        print("--device must be auto, cpu, or cuda:N", file=sys.stderr)
        return 2

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
    output.parent.mkdir(parents=True, exist_ok=True)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(srt_text(cues), encoding="utf-8")
    json_output.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "language": transcription.language,
                "text": transcription.text,
                "asr_model": args.asr_model,
                "aligner_model": args.aligner_model,
                "alignment_unit": (
                    "Qwen3-ForcedAligner output; original timings preserved; "
                    "ASR punctuation restored by character offset"
                ),
                "items": items,
                "subtitles": cues,
                "subtitle_max_chars": args.max_chars,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(cues)} subtitle cues and {len(items)} aligned items.")
    print(f"SRT: {output}")
    print(f"Aligned JSON: {json_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
