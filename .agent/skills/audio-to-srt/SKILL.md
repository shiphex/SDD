---
name: audio-to-srt
description: Use when generating a verbatim transcript or SRT subtitles from local audio with Qwen3-ASR, or when realigning subtitles after an audio edit. Uses Qwen3-ForcedAligner timestamps and UV-managed Python dependencies.
version: 0.3.1
---

# Audio to SRT with Qwen3-ASR

Run local Qwen3-ASR for recognition and Qwen3-ForcedAligner for character or word timestamps. The aligned times become the source for each subtitle cue; never divide a transcript segment evenly across lines.

## Required source files

- Python project and exact dependency versions: `pyproject.toml` and `uv.lock` in this skill directory.
- Converter: `scripts/audio_to_srt.py`.
- Windows entrypoint: `scripts/run-audio-to-srt.ps1`. By default it directs the UV environment, UV cache, and Hugging Face model cache into ignored `.local/video/pilot`. Set `$env:VIDEO_RUN_ID` to use another run directory.

## First run

From the repository root in PowerShell:

```powershell
.\.agent\skills\audio-to-srt\scripts\run-audio-to-srt.ps1 `
  .local\video\pilot\source-first-3m.wav `
  --language Chinese `
  --output .local\video\pilot\source.srt `
  --json-output .local\video\pilot\source.alignment.json
```

The first invocation resolves the locked Python 3.12 environment and downloads the ASR and aligner weights into `.local/video/pilot/models/huggingface`. Keep these files local; do not commit recordings, transcripts, alignment JSON, or model weights.

For a different workflow run, use `prepare-pilot.ps1 -RunId <run-id> -InputAudio <path>`; it stores that run's sample, UV environment, and model cache under `.local/video/<run-id>/`. For direct calls to the transcription wrapper, set `$env:VIDEO_RUN_ID` to the same run ID first. For tracks longer than 180.05 seconds, the CLI asks the workflow PowerShell helper to reconcile hashes and check that the input path and hash match the artifact allowed at the current stage. A longer sample export is permitted only in `sample_final_transcript` when it matches `sample-final-audio`; full source transcription requires `full_transcript` and the registered `source-audio`; final full-audio alignment requires `full_final_transcript` and `full-final-audio`.

The length check is a safeguard for the normal workflow, not proof that a short file came from the authorized sample. Do not split the full recording into short files before `sample_acceptance` is explicitly approved.

To regenerate the lock after intentionally changing dependencies, run `uv lock --project .agent/skills/audio-to-srt`. Normal setup uses `uv sync --project .agent/skills/audio-to-srt --locked` through the PowerShell entrypoint.

## Conversion behavior

- Default ASR model: `Qwen/Qwen3-ASR-0.6B`.
- Default aligner: `Qwen/Qwen3-ForcedAligner-0.6B`.
- Default language: Chinese. Use `--language auto` for language detection.
- CUDA is selected automatically when available; otherwise the script uses CPU. Use `--device cuda:0` or `--device cpu` to select explicitly.
- Timestamped transcription uses the aligner. The pinned Qwen implementation splits long inputs into chunks of at most 180 seconds, aligns each chunk, and restores its offset before combining results. Confirm this behavior against `uv.lock` whenever the Qwen package version changes.
- On Windows, if Hugging Face's cache symlink probe cannot write in its temporary directory, the converter falls back to regular cached files. This can use more disk space; model files still stay under `.local/video/pilot/models/huggingface`.
- The aligner may omit punctuation even when Qwen ASR recognized it. The converter maps punctuation back by character offset only after confirming that ASR and aligned text match with punctuation and whitespace removed. If they do not match, it stops instead of guessing. It also removes clear false full stops before dependent text, without changing recognized words.
- SRT cues end at sentence punctuation. Long sentences split at the last suitable clause mark before the limit, then at an aligned-item boundary if needed. A clause mark followed by a pause of at least 1.5 seconds can end a cue even when it is under the limit. The splitter avoids known common-word interiors and prevents a very short remainder where possible. `--max-chars` (default 22) caps visible non-whitespace characters, including punctuation. Cue times remain the first and last aligned-item times; punctuation inherits the preceding aligned item's time, and the script never invents or redistributes timestamps.
- To change cue grouping without rerunning ASR or the aligner, pass the saved sidecar to `--alignment-input` and explicitly name the SRT output. The sidecar is updated with the new cues and the punctuation-restored aligned items:

```powershell
uv run --project .agent\skills\audio-to-srt --locked --python 3.12 `
  .agent\skills\audio-to-srt\scripts\audio_to_srt.py `
  --alignment-input .local\video\pilot\source.alignment.json `
  --output .local\video\pilot\source.srt `
  --max-chars 22
```
- The JSON sidecar contains the recognized text and aligned items for review. Treat it as private source material.

## Corrected transcript realignment

After editing audio, first run ASR on the exported audio. The default output beside `final.srt` is `final.transcript.md`; it contains contiguous `音频段` sections, each no longer than 180 seconds. Correct the recognized wording while listening to the final audio, retaining the numbered segment headings and time ranges. Do not add instructions or review comments inside those sections.

Align the corrected text without rerunning ASR:

```powershell
& .\.agent\skills\audio-to-srt\scripts\run-audio-to-srt.ps1 `
  .local\video\pilot\final-audio.wav `
  --transcript-input .local\video\pilot\final-transcript.md `
  --language Chinese `
  --output .local\video\pilot\final.srt `
  --json-output .local\video\pilot\final.alignment.json
```

The aligner processes each supplied section against the corresponding audio range and restores the section's absolute offset. Section headings must be consecutive, cover the full final audio from zero without gaps, and end within 50 ms of the audio duration. This stops stale or partial transcripts from being aligned as if they covered the whole track.

## Editing and realignment

For an audio edit, preserve the source transcript and its original timestamps as `source.srt`. Finalize the audio through the route authorized for the current run in `video-workflow` (Shotcut or an expressly authorized AI sample edit). Then run this converter again on the exported final audio and save the output as `final.srt`. Never reuse source timestamps after a cut or pickup recording.

The converter does not remove silence, change recognized words, correct factual claims, or produce pickup instructions. Keep the original recording unchanged. Follow the current run's `video-workflow` authorization for cut review: the default Shotcut route uses the recorder's decisions; an authorized AI sample route may use one consolidated video review. Wording changes and pickup lines still require the recorder's decision.

## Dependencies and sources

- Python 3.12 is managed by UV.
- `qwen-asr==0.0.6` and `torch==2.10.0+cu128` are pinned in `pyproject.toml`; the complete resolution is recorded in `uv.lock`.
- FFmpeg is an external executable used to prepare a short WAV sample. It is not installed by this Python project.
- Model names and the upstream forced-alignment implementation are documented in [讲解视频工作流](../../../docs/视频制作工作流.md) and the internal source index at `docs/公开来源.md`.
