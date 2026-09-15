# 发布专用工作底稿

这份工作底稿用于展示一项边界清楚的近期变化如何被规格、任务和实际证据共同控制。它不替代完整知识库，也不要求低风险任务分别创建多份文件。

使用前先核实目标、当前事实和验收方式。涉及跨模块、公开契约、持久化、复杂状态、外部副作用或难回退决定时，应补充相应的边界、运行、契约、失败、决策和验证设计。

状态需要分别记录：

- `Draft`：当前内容仍是提案。
- `Accepted`：人已经接受目标或决定。
- `Propagated`：接受的决定已经写入受影响的权威规格。
- `Implemented`：代码或系统变化已经完成。
- `Verified`：指定基线上的必要检查已经获得实际证据。

接受不等于传播，传播不等于实现，实现不等于验证。

```text
Task：{结果式名称}
状态：Draft / Accepted / Propagated / Implemented / Verified

一、Task Contract

Goal：
{本次只交付一个主要、可观察的结果}

References：
{引用与当前任务有关的 SC、ARCH/INV、ST、API、Failure、ADR、TEST；
这里只写编号和必要摘要，不复制整份设计}

Preconditions：
{动手前必须成立的事实、已经接受的决定和所需授权}

Allowed scope：
{允许改变的职责区域、模块或公开行为}

Must：
- {必须实现的行为}
- {必须保持的不变量或兼容承诺}

Must not：
- {不得顺手扩张的相邻范围}
- {不得破坏的边界、状态所有权或外部行为}

Verify：
- {需要执行的检查}
- {预期取得的证据及适用基线}

Design Delta：
{哪些“已接受 Spec 与新证据的冲突”必须停止实施并进入评审；
普通编码困难或私有实现调整不使用这个名称}

Handoff：
{完成后必须交付的修改说明、证据、限制和回写记录}

二、Preflight Brief

Baseline：
{当前版本、已核实的事实及证据位置}

Planned changes：
{本次准备改变的行为，不把计划写成已经完成}

Target files/modules：
{预计涉及的职责区域；调查后可以定向修正}

Relevant constraints：
{当前任务实际引用的边界、不变量、契约、失败和决策}

Open blockers/Design Deltas：
{无，或列出需要裁决、补证据或重新授权的项目}

Readiness：Ready / Blocked

三、Completion Report

Implemented：
{实际完成的行为变化}

Files changed：
{实际修改范围}

Tests：
{实际执行的检查、结果、适用基线和未覆盖限制；
不使用测试计划、文件存在或 AI 自评代替证据}

Boundary checks：
{Must not、状态所有权、公开契约和架构边界是否保持}

Design Deltas：
{实际发现的冲突、裁决结果及 Propagated 状态；没有则写“无”}

Remaining risks：
{尚未验证的限制、Unknown Result 和后续风险}

Result：Done / Partial / Blocked

Write-back：
{需要刷新哪些 Current Facts、权威 Spec、测试设计或任务状态}
```

Human Review 单独记录，不塞进 Task 正文。需要评审时至少写明：

```text
Objective：{本次评审要裁决什么}
Evidence Spot Checks：{独立抽查了哪些关键事实}
Decision Cards：{Conflict、Options、Decision、Why、Trade-off、Reversibility}
Adjudication：Accept / Reject / Deferred / Needs Evidence
Go/No-go：GO / Conditional GO / NO-GO，以及允许继续的具体范围
Propagation Plan：{接受后需要更新哪些权威规格，并怎样验证传播完成}
```

若外部动作的响应丢失，动作可能已经发生。缺少接收端幂等键或结果查询能力时，把结果记录为 Unknown Result，不推断为失败，也不自动重试。
