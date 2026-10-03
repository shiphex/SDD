---
name: video-workflow
description: Use when making a narrated video from local audio, including sample editing, captions, visuals, state tracking, and human acceptance.
metadata:
  version: 0.3.0
---

# 音频优先的讲解视频工作流

本技能协调内容、音轨、字幕、画面与验收。转写和强制对齐由 `audio-to-srt` 完成；本技能的脚本处理已决定的剪辑、字幕分行、合成和状态登记。每轮先读项目方案与内容规范，所有内部媒体及文字放在 Git 忽略的 `.local/video/<run-id>/`。

## 选择路径与权限

| 路径 | 适用条件 | 内容与音轨决定 | 交付前反馈 |
| --- | --- | --- | --- |
| Shotcut | 默认，或需要录音者亲自剪辑、补录 | AI 给候选；录音者在 Shotcut 定稿 | 按录音者选择审核 |
| AI 样片 | 当前 run 明确授权 AI 剪辑样片 | AI 按授权和集中反馈试剪、定稿；含糊原话保留 | 先看一条内部 MP4，集中反馈 |

当前 `pilot` 的 AI 授权只覆盖原录音前三分钟。用户对现有 MP4 表示“大体满意”，属于反馈，尚未明确批准 `sample_acceptance`。样片验收前，不转写或剪辑全段录音，也不得把全段切成短片段绕过状态检查。AI 不猜测听不清的词，不自行决定补录或事实更正。机器识别、波形与切点检查不能替代实际听感。

## 最短执行路径

1. 用 `workflow-state.ps1 -Action reconcile/status` 接管现有 run；新 run 才初始化。登记用途、受众、来源和必讲清单。已有产物按路径、哈希与依赖接管，避免重做。
2. 准备开头连续 180 秒样片，转写并形成本轮页面大纲。页面保留 Pnn ID；转写前的 cue 与时间码标暂定。只根据已声明资料判断遗漏和事实问题。
3. 审核内容。默认由录音者决定候选剪辑和补录；获授权的 AI 样片可在 `sample_content_review` 阶段先生成内部 MP4，用下述 `draft` 动作登记，再收一次集中反馈。草样片不批准任何 gate。问题清单可作内部依据，不要求用户逐项批准。修改大纲或来源后重新复审，内容确认才批准 `content_review`。
4. 定稿音轨。Shotcut 路径登记 `shotcut_export`；AI 样片路径使用下列音轨工具和登记入口，记录 `ai_audio_export`。保留原录音及每处源时间码。两条路径都从定稿音轨重新转写、校对和强制对齐，不沿用原录音 SRT 时间。
5. 用校对后的对齐结果制作独立 SRT；图示素材保持无字幕；按页面时间清单把字幕叠加到 MP4。检查文件参数、切点和同步，再让录音者看样片。只有明确验收后登记 `sample_acceptance`，才进入全段流程。

## 可复用媒体入口

`scripts/media_tools.py` 只执行已决定的数据，不自动选切点或改写口播。输入数据保存在 run 目录：

- `edits.json`：`{"cuts":[{"start":0.2,"end":0.5,"reason":"停顿"}]}`。时间始终是样片源 WAV 的时间；切点不得重叠。工具只接受最长 180.05 秒的样片源 WAV，不能用于未获授权的全段剪辑。输出 WAV 与含源时间码、保留段映射的 JSON。
- `caption-lines.txt`：每一非空行生成一个字幕 cue。文字去除空白和标点后必须逐字匹配校对后的对齐 JSON；每行末尾不得有标点。
- `scenes.json`：`{"scenes":[{"start":0,"end":5.2,"image":"P01.png"}]}`。每张 1920×1080 图片是无字幕页面或逐项显示状态；各时间段连续覆盖最终音轨。渲染器在视频合成时用白字和深色描边叠加字幕，不画文本框。

~~~powershell
$media = '.agent/skills/video-workflow/scripts/media_tools.py'
$runDir = '.local/video/lesson-01'
python $media build-audio --source "$runDir/source-first-3m.wav" --edits "$runDir/edits.json" --audio "$runDir/final-audio.wav" --map "$runDir/final-cut-map.json"
python $media build-srt --alignment "$runDir/final.alignment.json" --lines "$runDir/caption-lines.txt" --srt "$runDir/final.srt"
python $media render --audio "$runDir/final-audio.wav" --srt "$runDir/final.srt" --scenes "$runDir/scenes.json" --video "$runDir/sample-final.mp4"
python $media verify --audio "$runDir/final-audio.wav" --map "$runDir/final-cut-map.json" --srt "$runDir/final.srt" --scenes "$runDir/scenes.json" --video "$runDir/sample-final.mp4"
~~~

音轨要求未压缩单声道 16-bit PCM WAV；`render` 需要 FFmpeg、Pillow 和本地中文字幕字体，默认 Windows 微软雅黑，也可用 `--font` 指定。字幕最多两行。命令只做结构、时间和编码检查；同音字、切点听感、画面隐私与语义仍需人工看样片。

## 状态登记与验收

状态助手 `scripts/workflow-state.ps1` 保存产物哈希、依赖和 gate。`scripts/register-sample-output.ps1` 提供三个动作：`draft` 在 `sample_content_review` 阶段登记 `-CutMap`、`-Audio`、临时 `-Srt`、`-ScenePlan`、`-Video`，供录音者集中反馈；`audio` 要求当前 `content_review` 已批准且处于 `sample_ai_edit`，登记定稿 `-CutMap`、`-Audio` 并转入定稿转写；`delivery` 登记 `-Transcript`、`-Alignment`、最终 `-Srt`、`-ScenePlan`、`-Video`、`-QualityReview` 并进入 `sample_quality_review`。三个动作都要求 `-RunId`，会计算产物依赖；`draft` 与 `delivery` 还会登记页面图片的哈希。它们不批准内容或样片验收。Shotcut 路径继续使用状态助手登记导出文件。

质量记录区分自动检查和实际审听。音频变化会使字幕、页面和视频过期；页面或时间线变化会使视频过期。只有录音者明确接受当前样片，才依据状态助手要求登记 `sample_acceptance`。`assert-full-approved` 和转写 CLI 的长音频检查均须继续拒绝未验收的 run。

状态 API、参考流程和页面模板见 [工作流图](references/音频优先讲解视频工作流图.md)、[outline 模板](templates/outline.md)与[项目视频流程](../../../docs/视频制作工作流.md)。
