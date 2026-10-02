---
name: video-workflow
description: 协调讲解视频的音频优先制作流程，包括转写、大纲、内容审核、Shotcut 定稿、字幕、网页演示与样片验收。
metadata:
  version: 0.1.0
---

# 音频优先的讲解视频工作流

本技能负责协调整体流程，并调用 audio-to-srt、cli-anything-shotcut 和 web-video-presentation。录音者负责校对转写、处理内容问题、在 Shotcut 中审听和剪辑，并作出各阶段的人工验收决定。

## 基本规则

- 样片默认取录音开头连续三分钟。样片通过人工验收前，不处理完整录音。
- 已有样片产物时，先检查路径和哈希并接管现有文件；不要为了初始化而重跑转写或重新制作粗剪。
- 录音、转写、审核记录、字幕、模型权重和工程文件均放在 Git 忽略目录 .local/video/<run-id>/ 下。workflow.json 只保存路径、哈希、依赖、阶段、问题处理状态和审批状态，不保存录音或转写正文。
- 识别稿、校对稿、补录稿、最终字幕和页面大纲分别保存。识别结果不等于已批准口播稿。
- 不得自行删音频、改写口播、判定事实真伪或替用户决定补录。
- 事实准确性和内容遗漏只能对照本轮明确登记的参考资料或必讲清单。未声明参考资料时，只报告内部含糊、重复或衔接问题，不推断事实错误或外部遗漏。
- 输入变更后，依赖产物和相关审批会过期。恢复流程前先对账，只重建过期产物的下游。
- 登记产物前，其依赖必须处于有效状态。内容未变化的过期产物不能靠重复登记恢复；只有在明确重建或重新审核后，才使用 -ConfirmRebuilt，且其下游和审批仍须重新检查。
- 审核轮次使用递增编号，例如 sample-content-review-01。状态助手记录最新轮次；内容 gate 只能使用最新审核文件，登记旧轮次会被拒绝。
- CLI-Anything Shotcut 工具只创建或检查 MLT 工程文件，不操作 Shotcut 图形界面。用户在 Shotcut 中审听、剪辑、录入获批补录并导出定稿音轨。

## 建立或恢复工作流

使用简短且稳定的 run ID，例如 pilot。在仓库根目录打开 PowerShell：

~~~powershell
$state = '.agent/skills/video-workflow/scripts/workflow-state.ps1'
$sourceAudio = Read-Host '录音文件路径'
& $state -Action initialize -RunId pilot -SourceAudio $sourceAudio
~~~

若 workflow.json 已存在，不要重新初始化，使用以下命令恢复：

~~~powershell
& $state -Action reconcile -RunId pilot
& $state -Action status -RunId pilot
~~~

接管已有样片时，按依赖顺序登记已有文件，再登记大纲与审核文件。示例中的产物 ID 用于标识文件，不包含文件正文：

~~~powershell
& $state -Action register-artifact -RunId pilot -ArtifactId sample-audio -Path '.local/video/pilot/source-first-3m.wav' -DependsOn source-audio
& $state -Action register-artifact -RunId pilot -ArtifactId sample-transcript -Path '.local/video/pilot/source.srt' -DependsOn sample-audio
& $state -Action register-artifact -RunId pilot -ArtifactId sample-alignment -Path '.local/video/pilot/source.alignment.json' -DependsOn sample-audio
& $state -Action register-artifact -RunId pilot -ArtifactId silence-timeline -Path '.local/video/pilot/roughcut.v2' -DependsOn sample-audio
& $state -Action register-artifact -RunId pilot -ArtifactId roughcut-project -Path '.local/video/pilot/roughcut-candidate.mlt' -DependsOn sample-audio,silence-timeline
& $state -Action register-artifact -RunId pilot -ArtifactId edit-review -Path '.local/video/pilot/edit-review.md' -DependsOn sample-audio,sample-transcript,silence-timeline
~~~

新 run 可使用 audio-to-srt 的 PowerShell 入口以及 Auto-Editor、Shotcut 工具准备开头三分钟样片。保留原始录音，不要把现有粗剪候选当作人工批准。

例如，运行 prepare-pilot.ps1 -RunId lesson-01 -InputAudio <audio-path> 会把样片、UV 环境和模型缓存放在 .local/video/lesson-01/。脚本名为兼容旧入口而保留；-RunId 决定实际目录。音频和 Shotcut 包装脚本使用 VIDEO_RUN_ID 选择 run，默认值为 pilot。

## 第 0 阶段：登记用途与受众

先填写 templates/brief.md，记录受众、用途、必讲清单、已声明参考资料和制作限制。未知信息明确写“待提供”或“未声明”，不要自行推断。将 brief 登记为 run-brief，并把它加入大纲及内容审核产物的依赖，后续修改才能使下游审核过期。

~~~powershell
& $state -Action register-artifact -RunId pilot -ArtifactId run-brief -Path '.local/video/pilot/brief.md'
~~~

## 第 1 阶段：生成页面大纲初稿

根据当前转写稿和已声明资料填写 templates/outline.md。这是较早生成、可编辑的 Markdown 页面计划，不是 .pptx 或最终视觉稿。

每页使用稳定的 Pnn 编号，写明一个核心信息、少量要点和画面构想，并关联转写版本、SRT cue 编号和音频时间范围。还要记录关联的问题 ID 和补录 ID。调整页面措辞或顺序时尽量保留页面 ID；只有页面的教学目的发生变化时才新建 ID。最终音轨对齐完成前，cue 与时间范围都标为暂定。

登记大纲并进入大纲/内容审核阶段：

~~~powershell
& $state -Action register-artifact -RunId pilot -ArtifactId sample-outline -Path '.local/video/pilot/outline.md' -DependsOn sample-transcript,run-brief
& $state -Action set-stage -RunId pilot -Stage sample_content_review
~~~

## 第 2 阶段：内容反馈回路

每轮都检查最新大纲、转写稿、本轮声明的资料或清单，以及上一轮问题记录。每轮新建审核文件，例如 content-review-round-01.md，不覆盖历史文件。为每个问题分配稳定的 I-nnn 编号，并记录：

- 状态：new、still-open、resolved 或 accepted-no-change；
- 类别和简要发现；
- 关联页面 ID、SRT cue 编号和时间范围；
- 证据：参考资料/清单链接，或具体的内部含糊之处；
- 明确的问题或建议的下一步；
- 相关的 PK-nnn 补录 ID（如有）。

区分已解决、仍待处理和新出现的问题。持续存在的问题保留原编号。页面修改后必须由 AI 重新审核，人工之前的决定不能自动批准新版本。AI 可以建议页面顺序、措辞、删改或补录问题，但不能静默地代为修改。

若本轮声明了参考资料或必讲清单，逐项登记为产物，并把这些 ID 加入本轮内容审核产物的依赖。资料变化会使审核和相关审批过期。没有声明参考资料时，在审核记录中说明这一点，不推断事实覆盖情况。

人工逐项决定修订、接受不改、删改、重写或补录，并将决定记入最新审核记录和状态助手。只有人工明确接受当前处理方式时，问题状态才能设为 accepted；约定的修订、删改或补录方案已反映在当前大纲/审核记录中时，才能设为 resolved。pending 或 needs_revision 会阻止内容 gate 放行。

~~~powershell
& $state -Action set-item -RunId pilot -ItemId I-001 -ItemStatus resolved -Decision revise
& $state -Action register-artifact -RunId pilot -ArtifactId sample-outline -Path '.local/video/pilot/outline.md' -DependsOn sample-transcript,run-brief
$declaredReviewInputs = @() # 仅加入本轮已登记并明确声明的参考资料或清单 ID。
$reviewDependencies = @('sample-outline','sample-transcript','run-brief') + $declaredReviewInputs
& $state -Action register-artifact -RunId pilot -ArtifactId sample-content-review-01 -Path '.local/video/pilot/content-review-round-01.md' -DependsOn $reviewDependencies
~~~

每次 AI 复审都使用递增的审核轮次 ID。放行前确认最新审核文件里的每个问题都已登记，且没有问题仍为 pending 或 needs_revision。之后由人工明确批准当前大纲与审核轮次：

~~~powershell
$declaredReviewInputs = @() # 与上一条命令保持一致。
$contentReviewDependencies = @('sample-outline','sample-content-review-01','run-brief') + $declaredReviewInputs
& $state -Action set-gate -RunId pilot -Gate content_review -Decision approved -DependsOn $contentReviewDependencies
& $state -Action set-stage -RunId pilot -Stage sample_shotcut
~~~

如果问题仍未处理、最新审核文件中有尚未登记的问题，或大纲/审核/来源产物缺失或过期，状态助手会拒绝批准。人工批准 gate 才表示大纲获批，不能仅凭文件存在推断审批完成。登记新一轮 sample-content-review-* 或 full-content-review-* 会使对应审批及下游 gate 过期，旧审核不能重复使用。

## 第 3 阶段：Shotcut 音轨剪辑与补录

只有人工批准的补录台词才能写入 pickup-script.md。每项使用 PK-nnn 编号，写明插入位置、前后 cue 或时间参考和获批台词。用户在 Shotcut 中试听并编辑候选音轨，加入获批补录，检查每个切点和衔接，然后导出新的定稿音轨。保留原样片候选与其源时间码。

登记定稿音轨，并将 Shotcut 审核关联到内容决定与导出文件：

~~~powershell
& $state -Action register-artifact -RunId pilot -ArtifactId sample-final-audio -Path '.local/video/pilot/final-audio.wav' -DependsOn source-audio,sample-outline
$manifest = Get-Content -Raw -Encoding utf8 '.local/video/pilot/workflow.json' | ConvertFrom-Json
$shotcutDependencies = @($manifest.gates.content_review.depends_on) + @('sample-final-audio')
$shotcutDependencies = @($shotcutDependencies | Select-Object -Unique)
& $state -Action set-gate -RunId pilot -Gate shotcut_export -Decision approved -DependsOn $shotcutDependencies
& $state -Action set-stage -RunId pilot -Stage sample_final_transcript
~~~

Shotcut 导出 gate 必须带上当前 content_review gate 的所有依赖，再加入 sample-final-audio。这样，大纲、审核、转写或声明资料变更都会使导出审批过期。

## 第 4 阶段：定稿转写、字幕与页面映射

对 Shotcut 导出的音轨重新运行 Qwen ASR，生成新的识别稿。用户一边听定稿音轨一边校对。将校对稿单独保存为 final-transcript.md，并按 audio-to-srt 规定分成连续音频段，每段不超过 180 秒。再用 Qwen3-ForcedAligner 对校对稿对齐，生成最终 SRT 和对齐 JSON。不得沿用源录音的时间戳。

音轨超过 180.05 秒时，CLI 会调用工作流 PowerShell 状态助手，先对账文件哈希，再核对输入路径和哈希是否匹配当前阶段允许处理的登记音频。获批补录可能使样片长于三分钟：sample_final_transcript 阶段只接受 sample-final-audio；full_transcript 只接受 source-audio；full_final_transcript 只接受完成相应审批的 full-final-audio。

将获批大纲映射到最终 SRT cue 编号和音频时间范围。登记每个输出时，依赖定稿音轨及其直接输入。定稿音轨变化会使转写、对齐、SRT、页面映射、时间线和演示过期；保留旧文件用于比较，但不要继续使用。

## 第 5 阶段：同步网页演示与质量反馈回路

依据获批大纲和最终音轨页面映射准备 timeline.json，然后在本 run 目录中生成网页演示。最终音轨是播放时钟。检查播放、暂停、拖动定位、场景切换、可读性、口播与页面对应，以及切点和补录衔接。网页不得改写口播或替换为合成音轨。

质量审核按问题类型分流：

- 纯时间、画面、转场或可读性问题：修改演示/时间线、重新生成，再做质量审核。
- 音轨未变，但最终 SRT 对齐或 cue 时间有误：回到校对稿重新对齐，再刷新页面映射和演示。
- 口播内容、措辞、遗漏要点或补录问题：带着新问题回到内容反馈回路。若必须修改获批音轨，则返回 Shotcut，并基于新音轨重新转写、对齐、生成 SRT、页面映射和演示。

只有人工确认样片验收后，才可进入 full_transcript 或其他全片阶段。之后处理完整录音、生成全片大纲并重复内容审核，再继续全片音轨与演示阶段。不得把完整录音当作样片准备输入。

全片音轨剪辑前先批准 full_content_review。full_shotcut 的导出 gate 必须依赖当前全片内容审核 gate 的所有输入及 full-final-audio；进入 full_final_transcript 还要求全片内容审核和 Shotcut 导出审批均有效。

## 状态助手参考

~~~powershell
# 记录一个问题的人工决定
& $state -Action set-item -RunId pilot -ItemId I-001 -ItemStatus accepted -Decision accept_no_change

# 记录样片验收。自动带上内容审核和 Shotcut gate 的全部依赖。
$manifest = Get-Content -Raw -Encoding utf8 '.local/video/pilot/workflow.json' | ConvertFrom-Json
$acceptanceDependencies = @('sample-outline','sample-final-audio','sample-srt','sample-presentation','sample-quality-review') + @($manifest.gates.content_review.depends_on) + @($manifest.gates.shotcut_export.depends_on)
$acceptanceDependencies = @($acceptanceDependencies | Select-Object -Unique)
& $state -Action set-gate -RunId pilot -Gate sample_acceptance -Decision approved -DependsOn $acceptanceDependencies

# 设置全片转写阶段，并核验输入音频确实是当前登记的全量录音
& $state -Action set-stage -RunId pilot -Stage full_transcript
& $state -Action assert-audio-approved -RunId pilot -InputAudio '<已登记音频路径>'

# 检查哈希、过期下游、审批与当前阶段
& $state -Action reconcile -RunId pilot
& $state -Action status -RunId pilot
~~~

gate 决定支持 approved、rejected 和 pending。新建或变更产物时保留原文件，但会使依赖产物和审批过期；继续之前先检查 status 并遵守阶段 gate。

完整流程图见 [音频优先讲解视频工作流图](references/音频优先讲解视频工作流图.md)。
