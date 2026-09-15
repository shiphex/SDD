# 小白如何用 SDD 与 AI 开发软件

AI 可以很快地生成代码，但一次生成无法覆盖完整的开发工作。目标、现状、设计决定和验收证据都会改变实现方向。本文将 SDD（Spec-Driven Development，规格驱动开发）定义为：先把这些信息写成可以检查和更新的规格，再让人和 AI 按小步任务实施，并用实际证据收口。

设想一个完全虚构的场景：一句“帮我做一个个人助理 Agent”的想法，没有说明用户先要解决什么问题，也没有当前系统事实、数据边界、状态归属、失败后的结果和完成证据。AI 可以自行补全这些空白，但补出的产品可能偏离目标。编码前还缺少一组能被核查的中间判断。场景到这里结束，后文只讨论通用方法。

## 零、为什么需要 SDD

让人或 AI 从一句意图直接进入编码，常见风险不是“代码一定写错”，而是中间判断没有被看见：

- 当前实现和限制没有核实，旧文档或猜测被当成事实。
- 目标、方案和文件改动混在一起，局部实现反过来定义需求。
- 状态、所有权、失败恢复和兼容语义没有明确归属。
- 一次任务包含多个结果，修改范围和停止条件持续扩张。
- 测试计划、脚本退出码或文件存在被误当成完整的完成证据。

SDD 在意的不是“先写很多文档”，而是把决定实现方向的信息显式化，并让它们能够被检查、修正和追溯。

## 一、人的思考怎样推进一次开发

一次开发有两条同时存在的主线。人的活动按时间推进，`01 Problem` 至 `09 Feedback` 按信息类型保存当前结论。前者描述活动顺序，后者标记信息位置，两套编号各自承担一种职责。本文同时承担方法总览和系列阅读入口；项目中的长期信息从 `01 Problem` 开始。

**双主线总图：**

```text
人的活动：明确目标 → 核实现状 → 设计边界 → 裁决决定 → 推导任务 → 实施变化 → 验证同步
             ↑        │          │          │         │         │         │
             └────────┴──────────┴──────────┴─────────┴─────────┴─────────┘
                         新证据可以让活动回到受影响的位置

信息地图：   01 Problem       问题、目标与成功标准
             02 Architecture  边界、职责与所有权
             03 Runtime       流程、状态与生命周期
             04 Contracts     模块交互规则
             05 Failures      失败语义与恢复责任
             06 Decisions     设计取舍与决策记录
             07 Test Plan     验证设计与完成条件
             08 Tasks         当前事实、差距、任务与执行证据
             09 Feedback      人工评审、变化路由与学习反馈
```

时间轴回答“现在做什么”，信息地图回答“结论以后去哪里找”。开发者每走一步，先从地图读取当前有效的事实与约束，再把新的判断写回拥有该信息的位置。后续证据一旦推翻前提，活动就沿反馈线返回到受影响的位置，并暂停依赖旧前提的编码。AI 因此能够获得足够上下文，一次聊天也不会直接成为长期事实源。

每一步都可以用“读取、写入、退出门槛”连接两条主线：

| 人的活动 | 此时要回答的问题 | 主要写入 | 同步检查 | 退出门槛 |
| --- | --- | --- | --- | --- |
| 1. 明确目标与验收 | 为什么改变、得到什么结果、什么不做、需要什么证据 | `01 Problem`，初步 `07 Test Plan` | 本文说明的范围与入口 | Goal、Non-goal、SC 足以判断完成 |
| 2. 核实当前状态 | 当前代码实际怎样、哪些是事实、哪些仍未知 | `08 Tasks` 的 Current Facts；问题基线失真时更新 `01 Problem` | `02 Architecture` 至 `07 Test Plan` 中引用的旧事实 | 已能说明 Current State 与 Gap |
| 3. 设计必要边界 | 谁负责状态、怎样协作、怎样交互、失败由谁恢复 | 按风险更新 `02 Architecture` 至 `05 Failures`，同步初步 `07 Test Plan` | `01 Problem` 的 Driver 和 SC | 当前增量所需边界已经明确 |
| 4. 确定关键决定 | 有哪些方案、代价是什么、选择什么、何时重审 | `06 Decisions`；接受后传播到受影响的 `01 Problem` 至 `05 Failures`，以及 `07 Test Plan` | 影响清单与验证方式 | 决定已接受，或标为 Needs Evidence |
| 5. 推导最小增量 | 差距中下一项可独立验证的结果是什么 | `08 Tasks` 的 Phase、Vertical Slice 和 Task | `01 Problem` 至 `07 Test Plan` 的具体条目 | 目标、范围、禁止项和验证完整 |
| 6. 实施并处理变化 | 新发现是局部实现、事实变化，还是 Spec 冲突 | `08 Tasks` 记录实施；Design Delta 路由到 `01 Problem` 至 `07 Test Plan` | 必要时由 `09 Feedback` 组织 Review | 没有未处理的关键 Design Delta |
| 7. 验证并同步 | 证据能否证明承诺、哪些信息需要刷新 | `08 Tasks` 保存实际结果，`09 Feedback` 保存评审和传播结论 | `07 Test Plan` 与受影响的 `01 Problem` 至 `06 Decisions` | 得出 Done、Partial 或 Blocked |

**1. 明确目标与验收。** 先写问题，再写 Goal、Non-goal 和 Success Criteria（成功标准，简称 SC）。Goal 应描述完成后可观察的结果，不要提前把某个文件、组件或技术选型当成目标。Non-goal 拦住最容易顺手扩张的相邻工作。SC 则说明将来用什么现象判断结果成立；它可以先在 `07 Test Plan` 中获得一个待细化的证明方向。

这一阶段还要识别授权边界。分析、评审和实施承担不同责任。目标与允许范围明确后，AI 才能区分可以直接推进的工作和必须由人裁决的高影响动作。退出门槛取决于读者能否判断完成条件和明确排除的内容，与需求文字的篇幅无关。

**2. 核实当前状态。** 规格需要同时覆盖目标和真实基线。代码入口、配置、类型、测试和真实接口都是证据来源；文件名、过期文档、历史计划和人的记忆只能提供线索。AI 可以快速搜索和整理，但必须把观察到的事实、仍未知的内容、尚未接受的提案和历史记录分开。

这里有一个容易混淆的边界：`01 Problem` 保存相对稳定的问题基线，例如为什么要改变以及原有问题是什么；`08 Tasks` 的 Current Facts 保存随调查和实施滚动变化的当前事实。某个内部函数换了位置，通常只需刷新 `08 Tasks`；证据表明原先的问题描述失真时，再回到 `01 Problem`。退出前应能明确写出 Current State、Target 和两者的 Gap。

**3. 设计必要边界。** 设计工作先说明会决定当前增量实现方向的内容，再按沟通需要选择图示。谁拥有状态和资源，谁负责创建与清理；运行时由谁触发事件，状态怎样变化；模块之间允许交换什么，调用方可以依赖什么；失败由谁发现、传播和恢复，最终留下什么状态。这些信息按性质写入 `02 Architecture` 至 `05 Failures`，并在 `07 Test Plan` 中留下相应的验证入口。

深度随风险调整。局部、容易回退、没有公开契约的变化，一份短 Spec 也许足够。涉及持久化、跨模块状态、公开接口、复杂失败或外部副作用时，需要补齐生命周期、不变量、兼容、取消、超时、幂等和恢复责任。退出门槛取决于当前增量依赖的边界是否明确，文件数量不参与判断。

**4. 确定关键决定。** 多个方案都能工作时，先找必须保住的不变量，再比较 Option、Trade-off、Reversibility 和 Verification。优先裁决难回退、改变公开行为、移动状态权威或扩大故障范围的问题。低风险且容易替换的局部机制，可以留到实现时决定。

关键决定写入 `06 Decisions`。编号表示文档位置；目标讨论、架构设计、实施调查或验收都可能产生需要记录的决定。退出状态可以是 Accepted，也可以是 Needs Evidence；后者表示还缺事实，不能被悄悄当成已接受方案。决定被接受后，还要把影响传播到拥有相关规则的文档。

**5. 推导最小增量。** Task 从当前事实与目标的差距开始推导：

```text
Current State → Target → Gap → Smallest Delta → Evidence
```

一个 Vertical Slice（纵向切片）最好只交付一个主要、可独立观察的结果，同时覆盖完成它所需的最小上下游路径。`08 Tasks` 中的 Task 通过 References 引用 `01 Problem` 至 `07 Test Plan` 的具体条目，完整设计继续由原文档维护。任务还要写 Preconditions、Allowed scope、Must、Must not 和 Verify。调查型 Task 的产物是事实或裁决，实施型 Task 的产物是行为变化；将两者混在一起，会让未核实的假设直接进入代码。

**6. 实施并处理变化。** AI 在 Allowed scope 和已接受约束内修改、测试和报告，不因实现方便而移动边界或改变目标。常规、可回退、已获授权的工作可以连续推进；需要新权限、高风险外部动作或产品取舍时才停下。

实现过程会检验设计假设。新发现可能只影响私有算法，也可能改变 Current Facts。新证据使已接受 Spec 无法继续成立时，应记录 Design Delta，随后由 `09 Feedback` 组织 Accept、Reject、Deferred 或 Needs Evidence 的裁决。未经裁决的代码差异不能成为新的架构规则。

**7. 验证并同步。** 验收从 SC 出发，检查目标行为、失败路径、契约和架构约束。Test Plan 说明准备怎样证明；执行证据记录实际运行的命令、结果、适用基线和限制；Done、Partial 或 Blocked 则是基于证据作出的完成结论。三者不能互相替代。

同步也要定向进行：目标和范围变化回 `01 Problem`，边界或 owner 变化回 `02 Architecture`，流程和状态回 `03 Runtime`，交互规则回 `04 Contracts`，失败恢复回 `05 Failures`，关键取舍回 `06 Decisions`，证明方式回 `07 Test Plan`，当前事实和下一项任务回 `08 Tasks`。`09 Feedback` 记录评审和传播结论，但不覆盖这些权威位置。七步可以向前推进，也可以被证据带回受影响的地方。

一次验收还需要明确停止条件。关键证据不足、必需的 Design Delta 尚未裁决，或验证只能覆盖局部行为时，结论应是 Partial 或 Blocked，并写清继续工作的前提。把这些状态提前写成 Done 会把未知项交给下一次修改；准确状态能让后续 Task 从实际差距开始。

## 二、每个判断应该写进哪份文档

长期维护时，一个知识点最好只有一个主要归属。其他位置只引用编号和当前任务需要的摘要，避免同一规则出现多个版本。下面九篇文章构成 `01 Problem` 至 `09 Feedback` 的阅读目录，并分别回答四个问题：它唯一负责什么，形成结论前读什么，向下游提供什么，哪些变化会触发更新。每篇标题旁都给出可复制模板。

| 文档 | Owns：唯一负责 | Reads / Emits | Update trigger |
| --- | --- | --- | --- |
| [01 Problem](05_SDD博客系列文章/01_Problem_问题目标与成功标准.md)（[模板](05_SDD博客系列文章/templates/01-problem模板.md)） | 问题基线、Goal、Non-goal、Driver、SC、Unknown、Stop Condition | 读取用户目标和业务证据；输出目标约束 | 问题、范围或成功标准变化 |
| [02 Architecture](05_SDD博客系列文章/02_Architecture_边界职责与所有权.md)（[模板](05_SDD博客系列文章/templates/02-architecture模板.md)） | 术语、系统边界、职责、owner、依赖、不变量、质量驱动 | 读取 `01 Problem` 与系统证据；输出静态架构约束 | 边界、owner、依赖或质量驱动变化 |
| [03 Runtime](05_SDD博客系列文章/03_Runtime_运行流程状态与生命周期.md)（[模板](05_SDD博客系列文章/templates/03-runtime模板.md)） | 流程、状态机、事件权限、生命周期、提交点、可观测性 | 读取 `01 Problem` 与 `02 Architecture`；输出运行与状态约束 | 流程、状态、事件或生命周期变化 |
| [04 Contracts](05_SDD博客系列文章/04_Contracts_模块交互规则.md)（[模板](05_SDD博客系列文章/templates/04-contracts模板.md)） | 输入输出、前后置条件、状态效果、并发、取消、超时、兼容 | 读取 `02 Architecture` 与 `03 Runtime`；输出可依赖的交互规则 | 公开操作、状态效果或兼容承诺变化 |
| [05 Failures](05_SDD博客系列文章/05_Failures_失败语义与恢复责任.md)（[模板](05_SDD博客系列文章/templates/05-failures模板.md)） | 失败分类、检测、传播、恢复 owner、清理、最终状态、Unknown Result | 读取 `03 Runtime` 与 `04 Contracts`；输出失败与恢复约束 | 失败路径、恢复责任或最终状态变化 |
| [06 Decisions](05_SDD博客系列文章/06_Decisions_设计取舍与决策记录.md)（[模板](05_SDD博客系列文章/templates/06-decisions模板.md)） | 关键决定、后果、取舍、可逆性、验证、逃生口、重审条件 | 读取关键冲突和证据；输出决定与传播清单 | 上下文、证据或重审条件变化 |
| [07 Test Plan](05_SDD博客系列文章/07_Test_Plan_验证设计与完成条件.md)（[模板](05_SDD博客系列文章/templates/07-test-plan模板.md)） | 测试层级、反例、追踪矩阵、Done Gate | 读取 `01 Problem` 至 `06 Decisions` 的承诺；输出证明方式 | 承诺、风险或可验证性变化 |
| [08 Tasks](05_SDD博客系列文章/08_Tasks_从差距到可验证增量.md)（[模板](05_SDD博客系列文章/templates/08-tasks模板.md)） | Current Facts、Gap、Phase、Vertical Slice、Task、Preflight、Completion | 读取 `01 Problem` 至 `07 Test Plan` 与当前实现；输出近期任务和实际证据 | 事实、差距、顺序或执行结果变化 |
| [09 Feedback](05_SDD博客系列文章/09_Feedback_Human_Review与思维内化.md)（[Human Review](05_SDD博客系列文章/templates/Human_Review模板.md) / [Learning Review](05_SDD博客系列文章/templates/Learning_Review_Card模板.md)） | Human Review、Design Delta 裁决、传播计划和学习反馈 | 读取规格与实施证据；输出裁决和回写路径 | 新反馈需要裁决、传播或沉淀 |

可以按目的选择阅读路径。第一次学习按 `01 Problem → 02 Architecture → 03 Runtime → 04 Contracts → 05 Failures → 06 Decisions → 07 Test Plan → 08 Tasks → 09 Feedback` 顺序阅读；开始设计一项功能时先读 `01 Problem`，再按风险进入 `02 Architecture` 至 `07 Test Plan`；拆分和维护任务时从 `08 Tasks` 开始，并回看它引用的上游条目；审核实施报告或设计变化时先读 `09 Feedback`，再进入发生冲突的文档。模板用于开始书写，任务所需文件数量由风险和信息范围决定。

`02 Architecture` 至 `05 Failures` 共同构成当前方法中的 Architecture Baseline（架构基线）。`02 Architecture` 回答系统静态上由什么组成、边界在哪里、谁拥有状态和资源；`03 Runtime` 回答系统运行后如何协作和变化；`04 Contracts` 把跨边界交互写成调用方可依赖的规则；`05 Failures` 定义失败传播、恢复责任与最终状态。单独的组件列表无法指导涉及状态或失败的修改。

表达边界时，可以借用 [C4 model](https://c4model.com/diagrams) 的分层视图：按沟通目的选择系统上下文、容器或组件层次，不必为了“完整”画满全部视图。需要组织更完整的架构说明时，[arc42](https://docs.arc42.org/) 提供了从目标、约束、上下文到运行、决定和质量要求等分区。本文根据当前工作流独立整理了 `01 Problem` 至 `09 Feedback` 的信息地图，与上述模板不存在换名关系。

`06 Decisions` 中的重要取舍可以写成 ADR（Architecture Decision Record，架构决策记录）。[ADR 资料站](https://adr.github.io/) 将它概括为记录单个架构决定及其理由、取舍和后果。风险高时，还可以借用 [SEI 的 ATAM](https://www.sei.cmu.edu/library/architecture-tradeoff-analysis-method-collection/) 对质量目标、风险、敏感点和取舍点的分析思路，做范围更小的 mini-ATAM。这里的“mini”表示轻量借用，不能据此宣称已经完成正式 ATAM 评估。

`07 Test Plan` 负责把抽象承诺变成证明方式。Quality Attribute Scenario（质量属性场景，QAS）可把某种刺激、发生环境和期望响应写成可检查场景；SEI 的 ATAM 资料也使用场景分析质量目标和架构决定。Architecture Fitness Functions（架构适应度函数）则把部分架构特征转成可重复、持续运行的检查；这个用法可参见 Thoughtworks 的[《Building Evolutionary Architectures》节选](https://www.thoughtworks.com/content/dam/thoughtworks/documents/books/bk_building_evolutionary_architectures_second_edition_free_chapter.pdf)。两者都需要落实到当前系统可获得的证据，术语本身不能充当验证。

信息最终通过一条追踪链进入任务和证据：

```text
SC
  → ARCH / INV / ST / API / Failure / ADR
  → TEST
  → TASK References
  → 实际证据
  → Human Review 与定向回写
```

两大支柱与反馈方向：

```text
支柱 A：Spec 编写（01–07）          支柱 B：Spec 执行（08）
┌──────────────────────────┐       ┌────────────────────┐
│ 目标 → 边界 → 流程 → 契约 │ ───→ │ 当前事实 → Gap → Task │
│      → 失败 → 决策 → 验证 │       │       → 实现 → 证据 │
└──────────────────────────┘       └─────────┬──────────┘
        ↑                                    │
        └──（08）Feedback / Design Delta ────┘
```

- 支柱 A 决定“做什么、做到哪里、不得破坏什么、怎样证明”。
- 支柱 B 把这些约束与当前实现对照，形成可以执行和验收的增量。
- 实现证据推翻设计时，通过 Design Delta（设计变化请求）回到正确层级，而不是在任务里暗改规则。


`01 Problem` 至 `06 Decisions` 定义承诺、边界和取舍，`07 Test Plan` 用 Traceability Matrix（追踪矩阵）检查每项承诺是否有证明方式，`08 Tasks` 的 Task 引用相关条目，实施后再保存实际证据。AI 协作流程也可以参考 [GitHub Spec Kit](https://github.com/github/spec-kit) 以 Spec、Plan、Tasks、Implement 组织产物的做法；本文独立整理了七步活动与 `01 Problem` 至 `09 Feedback` 的信息地图，工具命令顺序不构成通用标准。

低风险任务可以把实际相关的信息合并在一份短 Spec 中，中等以上风险再分别维护需要的专题。是否完成取决于承诺与证据能否对应，不取决于创建了多少文件。

信息地图会随结论变化。被新决定替代的内容应保留必要历史并标明已失效，当前入口只指向仍有效的结论；一次性、强上下文的实现记录留在 Task 或内部复盘，跨任务反复成立并经过核查的原则才上升到长期笔记。这种维护方式可以控制重复，并阻止未经裁决的 AI 建议进入团队规则。

## 三、AI 怎样读取、执行和回写

人的责任集中在问题、架构、裁决、授权和验收。人要确认 Goal 与 Non-goal，接受高影响边界和取舍，决定新的 Design Delta 是否进入规格，并根据证据作出完成结论。AI 可以承担代码调查、证据整理、候选方案、影响分析、Task 草拟、范围内实现、测试编写和审查。

要让这种分工可执行，一项近期变化至少需要 Task Contract、Preflight Brief 和 Completion Report 三个接口。

**1. Task Contract：定义本次允许范围。** Goal 只写一个主要结果；References 指向相关 SC、架构不变量、状态、契约、失败、ADR 和 TEST；Preconditions 列出动手前必须成立的事实、决定与授权；Allowed scope 指定可改变的职责区域；Must 与 Must not 分别说明要实现和不能破坏的内容；Verify 写计划执行的检查；Design Delta 定义什么冲突必须停止；Handoff 规定最后交付哪些记录。

References 让 AI 读取权威信息，同时避免把 `01 Problem` 至 `07 Test Plan` 复制成第二份完整 Spec。引用失效时，应回到拥有信息的文档修正，再刷新 Task；只改任务摘要会让两个版本继续漂移。

**2. Preflight Brief：确认能否开始实施。** Baseline 写当前版本和已核实事实；Planned changes 写准备改变什么；Target files/modules 记录调查后的预计范围，后续仍可根据证据调整；Relevant constraints 只列当前 Task 引用的约束；Open blockers/Design Deltas 公开尚未解决的问题；Readiness 只有 Ready 或 Blocked。Preflight 把实施前的事实、范围与门槛集中在一个可查位置，不额外增加形式审批。

**3. 实施与 Design Delta：处理新证据。** 私有算法需要调整，且外部行为和已接受约束保持不变时，可以在 Code 与当前 Task 内处理。运行结果改变了当前认识，则刷新 `08 Tasks` 的 Current Facts。证据推翻已接受的目标、边界、状态、契约、失败或验证设计时，形成 Design Delta，并由 Human Review 裁决后定向回写。

外部动作尤其要克制。调用响应丢失时，动作可能成功，也可能未发生。若接收端没有幂等键或结果查询能力，状态应保持 Unknown Result；当前证据不足以判定失败，也不支持自动重试。AI 可以报告证据缺口和候选处理方式，但不能用常见经验填补未知结果。

**4. Completion Report：用事实结束任务。** Implemented 记录实际行为变化；Files changed 记录真实修改范围；Tests 写执行了什么、结果如何、适用哪个基线和哪些限制未覆盖；Boundary checks 核对 Must not、状态所有权、契约与架构边界；Design Deltas 写发现、裁决和传播状态；Remaining risks 保存未验证限制；Result 给出 Done、Partial 或 Blocked；Write-back 指向要刷新的 Current Facts、Spec 或状态。

工作中常见的五种状态也必须分开：

| 状态 | 含义 |
| --- | --- |
| `Draft` | 当前内容仍是提案，尚未被接受 |
| `Accepted` | 人已经接受目标或决定 |
| `Propagated` | 被接受的决定已经写入受影响的权威文档 |
| `Implemented` | 代码或系统变化已经完成 |
| `Verified` | 指定基线上的必要检查已经取得实际证据 |

接受决定不表示规范已经传播，传播不表示代码已经实现，实现也不表示验证已经通过。Human Review 是这些状态之间的裁决点：它抽查关键事实，比较 Conflict、Options、Decision、Why、Trade-off 与 Reversibility，给出 Accept、Reject、Deferred 或 Needs Evidence，并明确 GO、Conditional GO 或 NO-GO 及传播计划。评审记录单独保存，不塞进 Task 正文。

抽查无需复现 AI 的全部搜索过程，应聚焦决定链上最容易改变结论的证据：真实入口是否一致，状态 owner 是否唯一，外部能力是否存在，失败后是否可查询，验证是否覆盖了关键反例。若这些事实无法独立复查，评审应要求补充证据；输出篇幅无法证明可信度。

下面是一份可以直接复制的公开工作底稿。低风险任务可以删去不适用的字段，具体删减范围由风险决定。

```text
Task：{结果式名称}
状态：Draft / Accepted / Propagated / Implemented / Verified

一、Task Contract
Goal：{本次只交付一个主要结果}
References：{SC、ARCH/INV、ST、API、Failure、ADR、TEST}
Preconditions：{动手前必须成立的事实、决定和授权}
Allowed scope：{允许改变的职责区域}
Must：{必须保持或实现的行为}
Must not：{不得扩张和不得破坏的边界}
Verify：{计划执行的检查和预期证据}
Design Delta：{哪些已接受 Spec 冲突必须停止并评审}
Handoff：{完成后必须交付的记录}

二、Preflight Brief
Baseline：{当前版本和已核实事实}
Planned changes：{本次准备改变什么}
Target files/modules：{预计涉及的区域}
Relevant constraints：{当前任务引用的约束}
Open blockers/Design Deltas：{无，或列出待裁决项}
Readiness：Ready / Blocked

三、Completion Report
Implemented：{实际完成的行为变化}
Files changed：{实际修改范围}
Tests：{实际执行的检查、结果、基线和限制}
Boundary checks：{Must not 与架构边界是否保持}
Design Deltas：{发现、裁决和 Propagated 状态}
Remaining risks：{未验证限制与 Unknown Result}
Result：Done / Partial / Blocked
Write-back：{需要刷新哪些 Current Facts、Spec 或状态}
```

实际使用时，先写 Goal 和 Current Facts，再从 Gap 选择一项最小可验证变化。实施获得新证据后，只更新拥有受影响信息的位置，并让下一项 Task 从刷新后的事实开始。
