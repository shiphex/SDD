---
name: video-workflow
description: Use when making or revising a narrated video from local audio, including editing, captions, visuals, human acceptance, release finalization, and local submission packages.
metadata:
  version: 0.7.0
---

# 音频优先的讲解视频工作流

本技能协调内容、音轨、字幕、画面与验收。转写和强制对齐由 `audio-to-srt` 完成；本技能的脚本处理已决定的剪辑、字幕分行、合成和状态登记。每轮先读项目方案与内容规范，所有内部媒体及文字放在 Git 忽略的 `.local/video/<run-id>/`。

## 选择路径与权限

| 路径 | 适用条件 | 内容与音轨决定 | 交付前反馈 |
| --- | --- | --- | --- |
| Shotcut | 默认，或需要录音者亲自剪辑、补录 | AI 给候选；录音者在 Shotcut 定稿 | 按录音者选择审核 |
| AI 样片 | 当前 run 明确授权 AI 剪辑样片 | AI 按授权和集中反馈试剪、定稿；含糊原话保留 | 先看一条内部 MP4，集中反馈 |
| AI 全片 | 样片已明确验收，当前 run 另有全片 AI 授权 | 先精修原声并制作内部完整预览；内容问题与补录另列 | 完整 MP4 集中反馈后再定稿 |

当前 `pilot` 的 61 秒样片已由录音者明确验收，且全片 AI 精修已获授权；全片经补录、语速与图示修订后，用户已接受现有内容与听感，发布版及本地投稿包已交付，尚未上传。其他 run 不继承此授权或验收。样片验收前，不转写或剪辑全段录音，也不得把全段切成短片段绕过状态检查。AI 不猜测听不清的词，不自行决定补录或事实更正。机器识别、波形与切点检查不能替代实际听感。

## 最短执行路径

1. 用 `workflow-state.ps1 -Action reconcile/status` 接管现有 run；新 run 才初始化。登记用途、受众、来源和必讲清单。已有产物按路径、哈希与依赖接管，避免重做。
2. 准备开头连续 180 秒样片，转写并形成本轮页面大纲。页面保留 Pnn ID；转写前的 cue 与时间码标暂定。只根据已声明资料判断遗漏和事实问题。
3. 审核内容。默认由录音者决定候选剪辑和补录；获授权的 AI 样片可在 `sample_content_review` 阶段先生成内部 MP4，用下述 `draft` 动作登记，再收一次集中反馈。草样片不批准任何 gate。问题清单可作内部依据，不要求用户逐项批准。修改大纲或来源后重新复审，内容确认才批准 `content_review`。
4. 定稿音轨。Shotcut 路径登记 `shotcut_export`；AI 样片路径使用下列音轨工具和登记入口，记录 `ai_audio_export`。保留原录音及每处源时间码。音轨剪辑、补录或变速后，从定稿音轨重新转写、校对和强制对齐，不沿用原录音 SRT 时间；纯视觉修改且最终 WAV 哈希不变时复用已核对的字幕与对齐。
5. 用校对后的对齐结果制作独立 SRT；图示素材保持无字幕；按页面时间清单把字幕叠加到 MP4。检查文件参数、切点和同步，再让录音者看样片。只有明确验收后登记 `sample_acceptance`，才进入全段流程。
6. 用户要求定稿、去除预览标记或准备投稿材料时，读取[发布定稿与投稿准备](references/发布定稿与投稿准备.md)。复用未变的音轨与字幕，检查全部独立画面状态，按明确清单生成公开包；记录“可投稿”及实际上传状态。

## 可复用媒体入口

`scripts/media_tools.py` 只执行已决定的数据，不自动选切点或改写口播。输入数据保存在 run 目录：

- `edits.json`：`{"cuts":[{"start":0.2,"end":0.5,"reason":"停顿"}]}`。时间始终是源 WAV 的时间；切点不得重叠。默认只接受最长 180.05 秒的样片源 WAV。全片使用 `build-audio --scope full --run-id <run-id>`，须核验当前样片验收、`full_ai_edit_authorization`、阶段和已登记的 `full-source-wav` 路径/哈希。输出 WAV 与含源时间码、保留段映射的 JSON。
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

页面依实际关系选择布局和工程图示：组件依赖、反馈回路、接口边界、失败分支、测试层级、证据追踪和任务时间线各自表达相应内容。保持样片配色、字体与字幕样式；避免全片统一套用横排三个文本框。图示不暗示真实系统截图或未经执行的验证结果。

## 状态登记与验收

### 已授权全片的真实补录修订

沿用当前 run，将上一版音轨和映射分别登记为 `full-preview-baseline-audio` 与 `full-preview-baseline-cut-map`，基线音轨依赖基线映射，映射依赖原 `full-source-wav`。保留原文件，新版输出使用独立修订目录，避免重新登记草剪后形成自身依赖。

补录登记为 `full-pickup-source-audio`，本轮明确授权文件登记为 `full-pickup-authorization` 并依赖补录源。解码后的 `full-pickup-wav` 依赖两者。在 `full_content_review` 阶段，只允许当前样片验收、全片 AI 授权有效且路径/哈希匹配的登记补录转写；登记文件存在不能代替明确授权。

选择完整纠正后编写 `assembly-timeline.json`：`sources` 按素材标识记录 `artifact_id`、`path`、`sha256`，`segments` 按输出顺序记录 `source_id`、源 `start/end`、可选 `gain_db`、`issue_id` 与 `reason`。当前来源仅支持上述固定基线与补录。将清单登记为 `full-assembly-timeline`，依赖清单使用的来源；运行 `media_tools.py assemble-audio --run-id <run-id> --timeline <清单> --audio <WAV> --map <映射>`。入口核验阶段、授权和全部输入；不选择切点、不猜测纠正、不生成旁白。

多源映射采用 `schema_version: 2`，包含来源、逐段源时间与输出时间，基线通过旧映射追溯原录音。全片登记入口自动保留来源与清单依赖；旧单源映射继续可用。来源、清单或补录授权变化使新音轨及下游过期。修订音轨重新识别、校对、对齐后，仍用 `-Scope full -Action draft` 登记内部预览，不自动批准内容、正式音轨或听感。

### 保留停顿的语音变速

已有内部预览获授权调整语速时，将其映射和音轨固定登记为 `full-retime-baseline-map`、`full-retime-baseline-audio`，后者依赖前者；映射保留 `full-assembly-timeline`、基线与补录来源依赖，避免依赖被替换的草片音轨。另登记 `full-retime-timeline`，依赖两个固定基线。当前入口只接受上述多源预览的固定基线。

变速清单记录 `source`、`source_map` 的登记 ID、路径与 SHA256，以及连续覆盖源音轨的 `segments`（`start/end`、`kind`、`tempo`、理由）。`kind` 为 `speech`、`pause` 或 `cut`；只有语音可变速，停顿逐采样保留，删除须明确列出。调用 `media_tools.py retime-audio --run-id <run-id> --timeline <清单> --audio <WAV> --map <映射>`；状态入口 `assert-retime-approved` 检查全片授权、阶段、路径、哈希及固定来源。

语音使用 FFmpeg `atempo` 保持音高，边界增加静音上下文后裁回所需范围。映射 `schema_version: 3` 保存每段速度与实际输出区间，允许源长度与输出长度不同；兼容 schema 1、2。普通停顿的采样和长度必须验证与基线一致。新音轨重新识别、校对和强制对齐，再重建字幕、页面与章节时间；不整体缩放旧字幕或视频时间。新版仍以内部 `draft` 登记，不批准最终听感。

全片 AI 路径先登记 `full-source-wav`（依赖原录音）及本轮授权文件；原始 M4A 需先由 FFmpeg 解码为单声道 PCM WAV。`full_transcript` 阶段可转写登记的原录音或源 WAV。在 `full_content_review` 阶段按授权精修并登记 `full-draft-audio` 后，长音频转写只允许该登记音轨或上述已授权补录。调用 `register-sample-output.ps1 -Scope full -Action draft` 登记完整预览、字幕和页面图片依赖，不批准内容或最终音轨。

集中反馈确认内容后，批准 `full_content_review`，进入 `full_ai_edit`，以 `-Scope full -Action audio` 登记 `full_ai_audio_export`。`full_final_transcript` 要求当前样片验收、全片内容确认及 AI 或 Shotcut 音轨导出批准，并只处理 `full-final-audio`。`-Scope full -Action delivery` 登记正式产物并进入 `full_quality_review`。源、音轨、页面及审核变化按依赖使下游过期；不以草片或自动检查代替人工验收。

状态助手 `scripts/workflow-state.ps1` 保存产物哈希、依赖和 gate。`scripts/register-sample-output.ps1` 提供三个动作：`draft` 在 `sample_content_review` 阶段登记 `-CutMap`、`-Audio`、临时 `-Srt`、`-ScenePlan`、`-Video`，供录音者集中反馈；`audio` 要求当前 `content_review` 已批准且处于 `sample_ai_edit`，登记定稿 `-CutMap`、`-Audio` 并转入定稿转写；`delivery` 登记 `-Transcript`、`-Alignment`、最终 `-Srt`、`-ScenePlan`、`-Video`、`-QualityReview` 并进入 `sample_quality_review`。三个动作都要求 `-RunId`，会计算产物依赖；`draft` 与 `delivery` 还会登记页面图片的哈希。它们不批准内容或样片验收。Shotcut 路径继续使用状态助手登记导出文件。

质量记录区分自动检查和实际审听。音频变化会使字幕、页面和视频过期；页面或时间线变化会使视频过期。只有录音者明确接受当前样片，才依据状态助手要求登记 `sample_acceptance`。`assert-full-approved` 和转写 CLI 的长音频检查均须继续拒绝未验收的 run。

用户明确接受当前内容与听感，或批准写明接受范围的计划时，将集中反馈关联到当前版本并登记接受结论；无需重复逐项确认已接受的细节。单独“大致满意”或仅提供补录不自动批准内容和听感。用户反馈、自动检查、画面查看与逐段人耳听审分别记录，不补写未执行的检查。制作发布版和本地投稿包不授权登录、上传或公开发布。

维护已交付视频引用的文档状态时，可先用 `snapshot-reference` 固化已批准的项目方案或内容参考文档，保存当时版本与哈希；随后视频内容使用新资料须重新登记与复审。用法见发布参考，不对媒体或审批记录采用此入口。

状态 API、参考流程和页面模板见 [工作流图](references/音频优先讲解视频工作流图.md)、[outline 模板](templates/outline.md)与[项目视频流程](../../../docs/视频制作工作流.md)。
