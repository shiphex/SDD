---
name: cli-anything-shotcut
description: Use when creating, editing, or inspecting Shotcut MLT timeline projects from the command line. It writes project files and inspects media; a person opens Shotcut to review and export them.
version: 1.0.0
---

# CLI-Anything for Shotcut

Use the pinned `cli-anything-shotcut==1.0.0` package from this skill's UV project. It creates and edits Shotcut/MLT project data. It does not operate Shotcut's graphical interface. The human opens the generated `.mlt` project in Shotcut for review and export.

## Setup on Windows

The isolated Python 3.12 environment and lock are `pyproject.toml` and `uv.lock`. From the repository root, invoke the wrapper:

```powershell
.\.agent\skills\cli-anything-shotcut\scripts\run-shotcut.ps1 --help
```

Shotcut, `melt.exe`, `ffmpeg.exe`, and `ffprobe.exe` are external tools. Their local installation directory may be supplied in the ignored `.local/video/pilot/tool-paths.json`; do not add machine-specific paths to tracked docs. `melt` is needed for rendering; FFmpeg tools are used for media probing.

## Build a timeline

Create a Shotcut project:

```powershell
.\.agent\skills\cli-anything-shotcut\scripts\run-shotcut.ps1 project new `
  --profile hd1080p30 `
  -o .local\video\pilot\roughcut.mlt
```

The pinned package adds a media resource directly to the timeline. It does not have the `media import` command shown in some upstream skill revisions. Check the installed command help before relying on changed CLI syntax.

```powershell
.\.agent\skills\cli-anything-shotcut\scripts\run-shotcut.ps1 timeline --help
.\.agent\skills\cli-anything-shotcut\scripts\run-shotcut.ps1 timeline add-track --help
.\.agent\skills\cli-anything-shotcut\scripts\run-shotcut.ps1 timeline add-clip --help
```

Use absolute media paths and explicit in/out points. `--position` is a clip index; this version does not expose the `--at` absolute-time option described in later skill text. Use sequential additions when constructing a silence-trimmed audio track.

```powershell
.\.agent\skills\cli-anything-shotcut\scripts\run-shotcut.ps1 `
  --project .local\video\pilot\roughcut.mlt --save `
  timeline add-track --type audio --name Voice

.\.agent\skills\cli-anything-shotcut\scripts\run-shotcut.ps1 `
  --project .local\video\pilot\roughcut.mlt --save `
  timeline add-clip <absolute-audio-path> --track <track-index> `
  --in 00:00:03.000 --out 00:00:08.500
```

Use `--json` when consuming output programmatically. The global `--save` option saves each mutation in one-shot mode. Query `project info`, `timeline tracks`, and `timeline show` before assuming track indices or current edit state.

## Review and render

The CLI can inspect the project and, when MLT is available, request a render:

```powershell
.\.agent\skills\cli-anything-shotcut\scripts\run-shotcut.ps1 `
  --project .local\video\pilot\roughcut.mlt project info

.\.agent\skills\cli-anything-shotcut\scripts\run-shotcut.ps1 `
  --project .local\video\pilot\roughcut.mlt export render `
  .local\video\pilot\roughcut-preview.mp4
```

For an audio rough cut, first listen to the source and all proposed transitions in Shotcut. Do not treat a successful project write or render command as approval of the cut.

## Upstream

- Skill source: `https://github.com/HKUDS/CLI-Anything/blob/main/skills/cli-anything-shotcut/SKILL.md`
- Package: `https://pypi.org/project/cli-anything-shotcut/`
- Package version: 1.0.0
- Package license metadata: MIT; the upstream CLI-Anything repository is Apache-2.0, and its license file is retained alongside this adapted skill.
