# SDD 学习实战笔记

本文整理一套面向 AI 协作开发的个人 SDD（Spec-Driven Development，规格驱动开发）实践。它把目标、当前事实、设计约束、任务和验证证据连接起来，使实现能够按小步推进，并在新证据出现时回到正确层级修正规格。这是一套可裁剪的个人工作流，不是统一的行业标准。

使用建议：先通读总览和速查索引建立全景，再选一个中等以上变化，按第 1、2、3 章走完一次 `01 Problem` 至 `09 Feedback`，最后用[实战自检清单](#practice-checklist)复查。低风险、容易回退的局部修改可以缩短记录；涉及公开契约、持久化、跨模块状态、复杂失败或外部副作用时，再补足相应设计。

<a id="toc"></a>

## 目录

- [0. SDD 总览与速查](#overview)
- [1. 支柱 A：01–07 Spec 编写](#spec-writing)
- [2. 支柱 B：08 Tasks 执行](#task-execution)
- [3. 09 Feedback 与闭环](#feedback-loop)
- [4. 实战方法与训练](#practice)
- [附录 A：术语、方法与学习指导](#appendix)

<a id="overview"></a>

# 0. SDD 总览与速查

<a id="why-sdd"></a>

## 0.1 为什么 AI 协作开发需要 SDD

让 AI 直接按“想到功能 → 写代码 → 再改”的循环工作，在范围小、边界清楚时可以很快得到结果。系统一旦出现多个状态、模块、并发路径或外部副作用，缺失的中间判断就会逐步放大：当前实现没有核实，目标与方案混在一起，状态和恢复责任没有归属，完成也缺少可检查的证据。

增加上下文本身不能解决这些问题；无关、过期或互相冲突的信息还会干扰判断。SDD 的做法是把决定实现方向的信息写成可检查、可更新的规格，再让人和 AI 在明确范围内实施，用实际证据收口。

<a id="mindset"></a>

## 0.2 认知转变

流程可以概括为从：

```
Prompt → Code
```

变成:

```
Problem → Requirements → Architecture → Runtime → Contracts
       → Failure model → Decisions → Tests → Tasks
       → Code → Review → Feedback
```

先定义问题与需求，再按风险设计静态结构与运行时行为，把必要的契约、失败模型、决策与验证方式写清楚，最后拆成小任务实施，并在实现与评审中持续反馈回规格。

<a id="mainline"></a>

## 0.3 七步活动主线

整条流程可以压缩成一条主线:

```
Intent → Specification → Design → tasks → Implementation → Verification
```

这条主线展开为七项可以回退的活动：

1. 明确目标、非目标和成功标准。
2. 核实当前实现与已有约束。
3. 设计当前增量需要的职责、边界、契约和失败语义。
4. 裁决会影响当前增量的关键问题。
5. 从现状与目标的差距推导最小可验证任务。
6. 在授权范围内实施，并处理新证据带来的变化。
7. 用实际证据验收，同步受影响的规格并刷新当前事实。

活动顺序回答“现在做什么”，下一节的信息地图回答“结论保存在哪里”。步骤可以被新证据带回前面，不应被理解成只能前进的瀑布流程。

<a id="document-map"></a>

## 0.4 `01–09` 信息地图

项目可以用九个逻辑位置保存不同类型的信息。它们不要求永远拆成九个物理文件；小项目可以合并，但每类信息仍应有明确归属。

```text
docs/architecture/
    01-problem.md
    02-architecture.md
    03-runtime.md
    04-contracts.md
    05-failures.md
    06-decisions.md
    07-test-plan.md
    08-tasks.md
    09-feedback.md
```

文档数量不是目标。局部变化可以用一份短 Spec 合并记录；高风险变化再按职责拆分，避免同一规则在多个位置出现不同版本。

<a id="workflow-network"></a>

## 0.5 有主方向的反馈网络

```
01 → 02 → 03 → 04 → 05 → 07 → 08 → Code → Evidence
      ↑    ↑    ↑    ↑         │                │
      │    │    │    └─────────┘                │
      │    │    └───────────────────────────────┤
      │    └────────────────────────────────────┤
      └────── 06 Decisions ← 09 Feedback ───────┘
```

`06 Decisions` 的编号表示信息位置，不表示到第六步才允许决策。目标讨论、架构设计、实施调查和验收都可能产生决定。`09 Feedback` 接收实施证据、评审意见和 Design Delta，裁决后再把变化传播到负责对应规则的 `01–08`；它不取代这些权威位置。

<a id="two-pillars"></a>

## 0.6 两大支柱与反馈层

- **支柱 A：Spec 编写（01–07）**。把意图变成互相咬合的规格，回答做什么、边界在哪里、怎样运行和失败、为什么这样选择、怎样证明。
- **支柱 B：Spec 执行（08）**。把规格与当前代码之间的差距拆成可验证增量，通过调查、预检、实现和证据记录逐步落地。
- **反馈层：Human Review 与变化路由（09）**。裁决新证据是否需要改变设计，记录传播范围，并推动下一轮任务。

```text
支柱 A：Spec 编写（01–07）          支柱 B：Spec 执行（08）
┌──────────────────────────┐       ┌────────────────────┐
│ 目标 → 边界 → 流程 → 契约 │  ───→ │ 当前事实 → Gap → Task│
│      → 失败 → 决策 → 验证 │       │       → 实现 → 证据 │
└──────────────────────────┘       └─────────┬──────────┘
        ↑                                    │
        └──── Feedback / Design Delta ───────┘
```

- 支柱 A 决定“做什么、做到哪里、不得破坏什么、怎样证明”。
- 支柱 B 把这些约束与当前实现对照，形成可以执行和验收的增量。
- 实现证据推翻设计时，通过 Design Delta（设计变化请求）回到正确层级，而不是在任务里暗改规则。

支柱 A 约束支柱 B：任务从规格派生，规格限定任务能做什么、不能做什么。支柱 B 反馈支柱 A：实现中发现已接受的规格无法成立时，通过 `09 Feedback` 裁决 Design Delta，再回到对应文档修改。

<a id="core-principles"></a>

## 0.7 三条核心原则

1. **架构能力体现为约束复杂性的能力。** 要能说明什么在哪里、由谁负责、什么不允许发生，不以抽象层数量衡量。
2. **Spec 是可验证的假设模型，当前实现是证据。** 规格与代码事实冲突时，先判断事实是否可靠，再修正规格或实现。
3. **变化发生在哪一层，就从该层向下检查影响。** 目标错误回到 01，边界错误回到 02，流程错误回到 03；局部私有实现错误才只改代码。

<a id="quick-index"></a>

## 0.8 文档定位速览

| 文件 | 核心问题 | 承载的方法 |
| --- | --- | --- |
| 01-problem.md | 为什么做、做到什么算成功 | Goal、Non-goal、Architecture Drivers、可验证场景 |
| 02-architecture.md | 系统静态结构是什么 | 边界、所有权、职责、禁止事项、不变量 |
| 03-runtime.md | 系统运行时怎么变化 | 状态机、生命周期、时序、数据流 |
| 04-contracts.md | 模块之间允许怎么交互 | 协议、类型、前置/后置条件 |
| 05-failures.md | 出错以后怎么办 | 失败模型、恢复、重试、幂等、清理 |
| 06-decisions.md | 为什么选 A 而不是 B | ADR、权衡、mini-ATAM 决策证据 |
| 07-test-plan.md | 如何证明设计真的成立 | 可验证场景、架构测试、集成/端到端、故障注入 |
| 08-tasks.md | 怎么让人/AI 按设计实施 | 增量任务、允许范围、完成定义 |
| 09-feedback.md | 新证据推翻设计时怎么办 | Design Delta、Human Review、传播与学习反馈 |

<a id="start-checklist"></a>

## 0.9 开始一个中等以上变化

- [ ] 请求类型和授权范围明确。
- [ ] 问题、Goal、Non-goal 和 Success Criteria 足以判断完成。
- [ ] 关键当前事实已核实，假设与未知项已标记。
- [ ] 系统边界、状态 owner 和生命周期 owner 唯一且清楚。
- [ ] 成功主链与关键失败分支都能说明。
- [ ] 公开契约覆盖输入、输出、状态效果和领域失败。
- [ ] 外部副作用的超时、幂等和结果未知已经裁决。
- [ ] 重大取舍有 ADR、验证方式和退出机制。
- [ ] Current State 与 Target 的 Gap 已明确。
- [ ] 当前 Task 只有一个主要可验证结果。

---

<a id="spec-writing"></a>

# 1. 支柱 A：Spec 编写——01–07 架构文档

写规格用于在编码前明确会改变实现方向的判断。本章依次说明 `01 Problem` 至 `07 Test Plan` 的职责、写法、常见缺口，以及它们与 08 Tasks 的关系。

本章中的业务名称、状态、接口和数值均为独立构造的虚构教学示例，只用于说明写法。

<a id="problem"></a>

## 1.1 01 Problem——为什么做、做到什么算成功

problem 文档先记录背景与当前状态：遇到了什么问题、代码和流程现状是什么、为什么需要变化。随后写三个核心栏目。

**Goal 与阶段目标。**目标可以从两个角度表达：

1. **Architecture 约束**：这个阶段要引入哪些结构安排。
2. **Capability 能力**：用户或程序在阶段结束后能够完成什么。

个人学习项目还可以补充三类目标：产品目标、学习目标和流程目标。Architecture 与 Capability 仍是实现和验收的主要依据；学习与流程目标用于记录训练和方法沉淀。

**Non-goal 控制范围。**明确列出当前不做的相邻能力。没有 Non-goal 时，AI 或开发者容易把相关重构、后续阶段能力和额外抽象一起纳入当前任务，导致范围持续扩大。

**Success Criteria 是停止条件。**用 SC 编号逐条列出可观察结果；适合行为验证的条目可以使用 Given / When / Then。以下是虚构示例：

```
SC-01 下单成功
Given: 用户已登录,购物车中有商品
When:  用户提交订单
Then:  系统创建一条订单记录,状态为"待支付",且库存扣减成功
```

SC 可以使用勾选框，并与 07 Test Plan 的 Traceability Matrix 联动。勾选含义必须预先定义，不能用“文件存在”代替验证通过。

**单一权威来源原则**：一个事实只在一个位置定义，其他文档引用编号和必要摘要。重复定义会产生版本漂移，实施时也会出现互相冲突的解释。

> 01 与 08 的关系：SC 是任务的最终验收目标；Non-goal 直接变成任务里的 Must not，具体见[任务模板](#task-template)和[正向约束](#spec-to-task)。

<a id="architecture"></a>

## 1.2 02 Architecture——系统静态结构

architecture 文档回答"系统由什么组成、边界在哪里、谁拥有什么"。

**Glossary 放在最前面。**明确每个关键词的准确含义,对架构形成硬约束。术语表常常是写完全部文档之后才补的,但文档最终要给别人读,所以前置。这是限制 AI 代码漂移最有效的手段之一——术语不定,AI 就会在实现里悄悄换概念。

**先画系统边界,再谈文件归属。**这里要回答的是“某个资源属于哪个模块”这类系统级问题；函数最终放在哪个文件，是边界与职责的实现结果。C4 模型建议按沟通需要选择视图层级，很多团队用 Context 和 Container 两层已经足够。先画整体构图：谁在里面、谁在外面、各容器之间怎么连。方法关系见[外部方法说明](#external-methods)。

**模块边界有两种常用写法：**

1. 每个模块分别写“责任”和“不能负责”。责任说明它拥有什么、提供什么；禁止事项说明它不能做什么。
2. 汇总成边界表，一行记录一个模块。

| 模块 | 职责(May) | 禁止(Must not) |
| --- | --- | --- |
| 订单服务 | 创建订单、校验库存、计算金额 | 直接扣款、发送短信 |
| 支付网关 | 发起支付、查询支付结果 | 修改订单状态 |

Must not 直接描述边界外的行为，后续还可以转成架构测试。只写“模块 X：管理 X”无法形成可检查的约束；需要说明它拥有的状态、提供的能力，以及禁止承担的职责。

**Invariants 写不变量。**"系统任何时候都必须为真"的命题,例如"每个组合根恰好持有一份某服务""某类记录在生命周期结束前必须可查询"。不变量是契约与测试的共同锚点。

**Architecture Evaluation 是自查。**可以按质量属性列出：

- Driver：关注什么。
- Tactic：用什么策略满足。
- Sensitivity / Trade-off：敏感点和代价。
- Risk：可能出现什么问题。
- Disposition：接受、缓解或继续取证。
- Evidence：将来用什么证据验证。

这张表要求设计同时记录收益、代价和验证方式。评估与 ADR 的配合方式在 1.6 展开。

<a id="runtime"></a>

## 1.3 03 Runtime——运行时怎么变化

Architecture 描述系统的静态组成，Runtime 描述这些构件运行时怎样协作。只检查单个类或模块，无法覆盖跨模块时序、状态和失败传播。

**先写一次完整操作。**每条关键路径至少包含：

1. 请求或事件从哪里进入。
2. 依次经过哪些模块。
3. 每一步读取或改变什么。
4. 成功时最终落到哪里。
5. 每一步可能怎样失败，失败后由谁接管。

成功主链与关键失败分支应放在同一视图中，避免运行时说明只覆盖 happy path。

**状态系统的核心是状态机。**如果系统或子模块有状态,画状态图,并配两张表。第一张是转移表,五列:

| Current | Event | Guard | Next | Side Effect |
| --- | --- | --- | --- | --- |
| 待支付 | 支付成功 | 金额一致 | 已支付 | 记录支付流水 |
| 已支付 | 发货 | 库存充足 | 已发货 | 生成物流单 |

Guard 是转移生效的守卫条件；Side Effect 是转移附带的动作。第二张表记录 `Event | Authority`，说明谁有权请求或报告事件。状态模型至少明确：

- 唯一的权威 owner 校验并应用状态转移。
- 非法转移被拒绝，原状态保持不变。
- 进入终态后，记录在规定的生命周期内仍可查询。
- 正在执行的操作遇到取消、超时或并发事件时如何收敛。

**最后用一张整体生命周期图收拢。**把各模块的路径串成"系统的一生":建立 → 运转 → 交互 → 结束/清理,每段指回前面的细节图。

> 03 与 08 的关系：实现证据表明运行流程不成立时，通过 [Design Delta](#design-delta) 裁决，再从 03 Runtime 向下检查 04、05、07 和 08。

<a id="contracts"></a>

## 1.4 04 Contracts——模块之间允许怎么交互

如果说 02/03 的图追求**理解**,那么 contract 追求**精确**。图说不清"这个函数失败时到底返回什么",契约必须说清。

**一份可执行的 Contract 至少回答八个问题：**

1. 输入是什么？
2. 输出或返回值是什么？
3. 前置条件是什么？
4. 后置条件是什么？
5. 会改变哪些状态？
6. 可能产生哪些领域失败？
7. 操作是否幂等？
8. 谁允许调用，谁不允许调用？

模板先写 Purpose 与 Ownership，再列 Public Operations。每个操作至少记录：

- Operation：签名或消息形状。
- Input / Output：输入输出。
- State effect：状态效果。
- Domain failure：领域失败。
- Idempotency、Precondition、Cancellation、Timeout：在相关时补充。

最后列 Must not，明确接口中不能出现的能力。禁止项直接约束接口形状，例如“不得创建某类资源”。

实战中契约文档常见的几种写法:

- **每个模块一个 Protocol**:列函数签名 + 集成约束(如"创建入口唯一""复用既有实现,不复制第二套逻辑""保留旧路径兼容")。
- **Runtime Invariants**:组合根级的不变量列表,常用 "exactly one" 句式——每个组合根恰好持有一份某服务,服务在整个生命周期内共享。
- **use-case API 层**:编排层的对外 API,只负责编排与委托,明确自己不做什么(不直接构造资源、不持有内部状态)。
- **建议代码目录**:可以给一份建议的文件布局,但**必须标注"非架构约束"**——目录只表达职责拆分意图,具体落点在实现阶段按现有代码惯例决定。Spec-driven 不等于提前锁死所有文件名。

契约中的类型、状态和事件必须与 03 Runtime 的状态机及权限表对应。契约暴露了转移接口，而状态机没有相应合法转移时，应先解决规格冲突再实施。

> 04 与 08 的关系：契约是 Task Verify 的判定依据；实现证据推翻契约时，通过 [Design Delta](#design-delta) 裁决，再调整 04 和受影响的 05、07、08。

<a id="failures"></a>

## 1.5 05 Failures——出错以后怎么办

错误处理需要在编码前明确检测、传播、恢复和最终状态，不能只在局部增加 `try/except`。

**先立全局 Failure Policy。**常见规则包括：

- 禁止 silent failure。
- Domain failure 使用 typed error 或 result 表达。
- Partial construction 失败后按既定边界回滚。
- Shutdown / teardown 保持幂等。
- 清理采用 best-effort 时，需要汇总并暴露失败。
- 底层组件不得无限重试。
- 非法状态转移被拒绝，原状态保持不变。

Policy 的措辞要与 Contract 和 ADR 一致。Rollback 覆盖哪些逻辑资源、所有权和外部残留，可能需要单独记录为 ADR。

**再给具体失败场景立表**,每个场景一行,带 ID 编号(形如 F-XXX-NN)供 08 引用:

| ID | Failure | Detect | Recovery owner | Recovery Action | Result/Test |
| --- | --- | --- | --- | --- | --- |
| F-ORD-01 | 库存不足 | 下单校验 | 订单服务 | 拒绝下单,返回 typed error | 无订单残留 |

每个 Failure ID 应回答：

1. 在哪里发现？
2. 谁负责恢复？
3. 怎样传播给调用方或操作者？
4. 能否重试，由谁重试？
5. 重试是否幂等？
6. 是否需要清理，清理哪些资源？
7. 最终状态是什么？
8. 是否需要发出事件或告警？

**错误分类决定处理动作。**Programmer、domain、environment、transient、permanent、cancellation 和 timeout error 对应的处理可能是 raise、retry、rollback、degrade 或 cancel。分类、处理动作和恢复 owner 应同时记录。

**列出 P0 Failure 清单。**重复 ID、资源不存在、非法状态转移、重复 shutdown、运行中崩溃等高优先级场景需要逐条映射到 Policy 和测试。

**控制 cascading failure。**多模块系统还要约定：

- 单点失败由谁兜底。
- 何时降级，降级后保留什么能力。
- 怎样避免多层 retry 相互放大。
- 哪些状态必须在失败后继续可查询。

> 05 与 08 的关系：Failure ID 直接进入 Task 的 References 与 Verify；回滚边界等事实与 Policy 冲突时，通过 [Design Delta](#design-delta) 裁决。

<a id="decisions"></a>

## 1.6 06 Decisions——为什么选择当前方案

决策文档保存选择及其背景、候选、代价和重审条件。`06 Decisions` 的编号表示归属位置；决定可能产生于目标讨论、架构设计、实施调查或验收。

**一份 ADR 只记录一个 architecturally significant decision。**基本字段包括：

- Status：Accepted、Deferred、Superseded 或 Rejected。
- Context：背景与需要解决的张力。
- Decision：接受的决定。
- Alternatives：备选及未被接受的理由。
- Consequences：正面、负面和中性后果。
- Deferred：明确延后的子问题。
- Review source：对应的 Human Review 裁决记录。

备选方案用对比表逐维度打分,结论明确写"接受/拒绝":

| 方案 | 复用 | 隔离 | 兼容旧路径 | 新复杂度 | 结论 |
| --- | --- | --- | --- | --- | --- |
| 方案 A | 高 | 高 | 高 | 中 | 接受 |
| 方案 B | 低 | 高 | 高 | 高 | 拒绝 |

举个例子(迷你版):

```
ADR-001: 缓存方案选择
Status: Accepted
Context: 查询热点数据,延迟与一致性的取舍需要明确。
Options:
  A. 进程内本地缓存 —— 简单,但多实例不一致
  B. 集中式缓存 —— 一致,但引入新依赖
  C. 暂不缓存 —— 零复杂度,延迟可能不达标
Decision: B
Consequences:
  + 多实例读一致
  - 引入运维依赖;缓存失效策略成为新决策点
Deferred: 缓存失效策略细节
```

**mini-ATAM 与 ADR 协作。**发生重大取舍时，可以按以下步骤进行：

1. 从 Problem 提取质量 Drivers。
2. 形成 Candidate Architecture。
3. 比较 Tactic、Sensitivity、Trade-off 和 Risk。
4. 根据风险调整候选方案。
5. 用 ADR 保存接受的决定、代价和验证方式。
6. 设计发生变化时重新评估受影响部分。

> 06 与 08 的关系：影响当前任务的 ADR 进入 References；Ownership 或 Boundary 被新证据推翻时，通过 [Design Delta](#design-delta) 裁决并定向传播。
>
<a id="test-plan"></a>

## 1.7 07 Test Plan——如何证明设计成立

07 Test Plan 在实施前说明怎样证明目标、契约和架构约束成立。

**测试策略分层：**

- Unit / Contract / State：覆盖纯逻辑和状态规则，使用可控依赖。
- Integration：验证多个模块组成的完整路径，可以使用 fake 隔离不稳定外部服务。
- End-to-end / real-service smoke：只在风险和环境需要时运行，并明确是否阻塞主线。

**检查项勾选语义要预先定义：**

1. 未勾选：尚未实现、未运行，或未通过要求的评审。
2. 已勾选：已有对应自动检查，并在指定基线上实际通过。
3. 已勾选项目成为后续 Phase 的回归项。
4. 后续修改使回归项失败时，当前 Phase 不得完成；应修复回归，或通过 Design Delta 更新已接受的契约与测试。
5. 单项通过不代表整体完成，最终状态由 Success Criteria 与 Traceability Matrix 决定。

**测试分类：**

- State Machine Tests：合法转移允许，非法转移拒绝且状态不变，终态可查询。
- Failure Tests：每个重要 Failure ID 至少有一条对应检查。
- Architecture Tests：用 ARCH 编号约束依赖方向和唯一入口。
- Contract / Isolation Tests：检查跨模块规则、实例隔离和兼容行为。

**把模糊的质量目标变成可验证场景(QAS)。**不要写"系统应该具有良好的扩展性",这种话无法验证。写成 Stimulus(刺激)/ Environment(环境)/ Response(响应)/ Measure(度量)四段。举个例子:

```
Stimulus:    新增一种支付方式
Environment: 现有下单流程不修改
Response:    注册新的支付插件即可接入
Measure:     核心订单模块修改 ≤ 1 个文件
```

它逼着设计者回答:**谁扩展什么、在什么条件下、以什么成本扩展?**"可扩展性"从此不再是抽象的好词,而是一条可测试的场景。

**架构约束的三层落地：**

1. 02 Architecture：记录人可读的职责、边界和 Must not。
2. 04 Contracts：把边界落实到接口和可依赖规则。
3. 07 Test Plan：为适合自动化的规则建立 ARCH 编号检查，例如禁止依赖方向或限制唯一创建入口。

落地链条是：

```
Architecture decision → Architecture rule → Automated test → CI
    → AI 无法静默违反
```

这符合 Architecture Fitness Function 的思路：把重要架构特性变成自动、持续的反馈。项目指令说明期望的工作方式，架构测试检查实现是否越过边界，两者承担不同职责。方法关系见[外部方法说明](#external-methods)。

**Traceability Matrix 收口。**矩阵按每条 Requirement 记录对应的 Architecture、Contract、Failure、ADR、Test、Task 和实际证据。缺失项可能表示该承诺尚未设计、无法验证，或本次范围无需覆盖；需要明确其状态，不能默认为完成。

> 07 与 08 的关系：ARCH、STATE 和 FAILURE 编号进入 Task 的 Verify；证明方式被新证据推翻时，通过 [Design Delta](#design-delta) 更新 07 和 08。

<a id="coverage-check"></a>

## 1.8 规格覆盖检查

写完 `01 Problem` 至 `07 Test Plan` 后，用下表检查当前增量是否覆盖了会改变实现方向的信息。这里检查的是内容，不要求每一行都有独立文件。

| 位置 | 最低覆盖内容 | 对应章节 |
| --- | --- | --- |
| 01 Problem | Goal、Non-goal、Success Criteria、未知项和停止条件 | [1.1](#problem) |
| 02 Architecture | 术语、边界、职责、owner、Must not 和不变量 | [1.2](#architecture) |
| 03 Runtime | 成功主链、关键失败分支、状态转移、触发权限和提交点 | [1.3](#runtime) |
| 04 Contracts | 输入、输出、前后置条件、状态效果、并发、取消和超时 | [1.4](#contracts) |
| 05 Failures | 检测、传播、恢复 owner、清理、最终状态和 Result unknown | [1.5](#failures) |
| 06 Decisions | Context、Alternatives、Trade-off、Verification、Escape Hatch | [1.6](#decisions) |
| 07 Test Plan | 测试层级、反例、追踪矩阵和 Done Gate | [1.7](#test-plan) |

---

<a id="task-execution"></a>

# 2. 支柱 B：Spec 执行——08 Tasks

08 是 SDD 的 Implementation 环节。它把规格与当前实现之间的差距拆成可验证任务，并记录调查、预检、实现和验收证据。

<a id="task-model"></a>

## 2.1 核心思维：Task 是 Spec 与 Code 之间的可验证增量

写 Task 时，先描述状态变化：

```
Current State ──delta──> Next Desired State
```

Task 定义从当前事实到目标状态的一次最小、可验证、受约束的变化。编写前依次回答：

1. 现状是什么？
2. 目标是什么？
3. 差距是什么？
4. 下一步最小变化是什么？
5. 哪里不能动，主要风险是什么？
6. 什么证据说明完成？

```
CURRENT    现在有什么?(以代码事实为准,不是想象)
TARGET     这一阶段最终要什么?
GAP        缺什么?
NEXT DELTA 最小的下一变化是什么?
RISKS      最可能失败/发散在哪里?
EVIDENCE   怎么证明完成?
```

举个例子(通用场景):

```
CURRENT    订单只能现金支付,已有下单与库存模块
TARGET     支持线上支付
GAP        无支付发起与回调处理闭环
NEXT DELTA 打通"下单 → 发起支付 → 回调更新订单状态"最小链路
RISKS      回调接口约定未定;失败回滚会触及库存
EVIDENCE   fake 支付回调下,订单状态按状态机正确迁移;失败路径无残留
```

一个重要区分是：**Task 从 Gap 推导**。把架构图直接切成“实现模块 A”“实现模块 B”，只会得到未考虑当前代码的 TODO 列表。应先问规格要求的状态与当前代码之间最重要的差距是什么，再根据代码事实选择解决方案。

有了 Gap，再用**最小可观察闭环**切任务。优先打通从入口到落点的最小纵向链路，使每一步完成后都有可运行、可检查的结果。底层重构没有新增用户能力时，也可以把结果写成可观察的架构性质，例如“所有 X 都经过同一个边界”。

模板可以很快熟悉，持续练习的重点是四个判断：**Reality Judgment**（证据支持的当前代码事实）、**Delta Judgment**（下一步最重要的差距）、**Scope Judgment**（本次做到哪里停止）、**Evidence Judgment**（什么证据足以证明完成）。

<a id="task-template"></a>

## 2.2 Task 模板与各字段写法

**08 文档的整体结构。**实战中 08 是一个滚动文档,通常由六个板块组成:

1. **总体任务列表**:MVP 与 Optional 分组,列出全部计划任务;Optional 项标注"不阻塞 MVP"。
2. **Phase 进度表**:一行一个 Phase,列 status 勾选、Phase 编号、目的、典型验证、对应任务。勾选表示该 Phase 完成。
3. **Current Facts**：当前代码事实，具体写法见[调查型任务](#investigation-task)，并标注 `Validated against: <commit>`。
4. **Accepted Design Constraints**：跨任务长期成立的设计约束，维护方式见[调查型任务](#investigation-task)。
5. **当前正在做的详细 Task**:只有当前 Task 写得最细,其余只留方向。
6. **Completed Tasks 汇总表**:Task | Outcome | End commit | History,一行一个已完成任务。

**单个 Task 的模板**:

```text
# TASK-XX <name>

Status:
Draft / Ready / In Progress / Done / Superseded

Goal:
这一任务完成后,系统新增什么可观察能力?什么时候停止?

References:
- REQUIREMENT / FACTS / ARCH / RUNTIME / CONTRACT / FAILURE / ADR / TEST

Preconditions:
开始这个 Task 前必须已经成立什么?

Allowed scope:
允许修改哪些模块/文件。

Must:
本 Task 必须实现的内容。

Must not:
明确禁止扩张到哪些内容。

Verify:
如何证明 Task 完成?

Handoff:
交接/人审约定。

Design delta:
发现 Spec 不成立时的记录与处理方式。
```

各字段的写法原则,依次是:

**Goal 先写可观察结果。**例如“用户可以通过统一入口创建订单，成功后可通过查询接口查到”。类名、函数名和文件位置通常属于实现手段，不作为 Goal。

**References 限定设计依据。**按需引用以下类型的具体条目：

- REQUIREMENT：需求与 SC。
- FACTS：Current Facts 与约束。
- ARCH、RUNTIME、CONTRACT、FAILURE：对应设计规则。
- ADR：已接受的关键决定。
- TEST：验证要求。

引用表示 Task 的设计依据已经存在；实现者发现需要改变依据时，应提出 Design Delta。

**Preconditions 回答为什么现在可以开始。**列出设计基线、目标分支、前置 Task 和依赖事实。Preconditions 不成立时，Task 保持 Draft 或 Blocked，不进入 Ready。

**Allowed scope 划定变化边界。**常写成 Primary scope 加必要的最小接缝。范围按职责区域描述；只有文件位置本身构成约束时，才提前锁定具体文件。

**Must 是完成 Goal 所需的最小事实。**检验方法：删除这一条后 Goal 是否仍成立；如果不成立，这一条才属于 Must。

**Must not 防止顺手扩张。** 问自己：做这个 Task 时，最容易把哪些相邻工作一起做掉？把它们列进 Must not，例如不实现下一个 Phase 的能力、不重构无关模块、不复制旧实现、不把内部行为塞进编排层。必要时用“本 Task 做 / 本 Task 不做”两列表格收口。

**Verify 在编码前写明。**逐条列出可执行检查，例如：

- Happy path 走完整链路。
- 关键失败路径没有超出规格允许的残留。
- 架构测试通过。
- 已接受的回归项继续通过。
- Diff audit 未发现范围扩张。

如果目标性质没有观察点，例如无法证明是否复用了统一入口，应先补充 04 Contracts 或 07 Test Plan。

**切分原则：**一个 Task 只有一个主要可验证结果。如果 Must not 持续增长、Allowed scope 横跨多个相互独立的区域，或 Verify 出现多组不同完成标准，应继续拆分。P0 / P1 / P2 属于总体任务列表，不写进单个 Task 的定义。

Task 可以按工程实验理解：

1. Hypothesis：有限改变将获得能力 X，且不破坏约束 Y。
2. Experiment：在 Allowed scope 内实施。
3. Measurement：运行测试、评审和架构检查。
4. Result：根据证据给出 Done、Partial 或 Blocked，并把新证据送入 Feedback。

**Task 动手前速查：**

- [ ] References 指向具体 Spec 条目，不只写文件名。
- [ ] Preconditions 解释为什么现在可以开始。
- [ ] Allowed scope 按职责区域定义，必要接缝有理由。
- [ ] Must 只包含 Goal 必需事实。
- [ ] Must not 防住最可能的范围扩张和边界破坏。
- [ ] Verify 已在编码前写明。
- [ ] 高风险任务已完成 Preflight 和要求的人工评审。
- [ ] 未决问题只阻塞依赖相应裁决的工作。

<a id="rolling-wave"></a>

## 2.3 Phase 与 Rolling-Wave Planning

**Phase 从能力成熟过程推导。**常见顺序是：

1. 建立必要基础结构。
2. 打通第一条端到端链路。
3. 建立正式交互通道。
4. 支持围绕共享状态协作。
5. 收拢关闭、取消与失败恢复。
6. 完成集成验证和架构检查。

文件或模块数量不用于决定 Phase 数量。典型 Phase 表如下：

| status | Phase | 目的 | 典型验证 | 对应任务 |
| --- | --- | --- | --- | --- |
| [ ] | Phase 0 | 现状对齐:Spec 与现有代码的差距分析 | 每条 Spec 假设都被代码事实验证 | 差距分析 |
| [ ] | Phase 1 | 核心组装:落实已接受的契约,建立基础结构 | 组合根能建立共享服务 | 核心组装 |
| [ ] | Phase 2 | 第一个垂直纵切 | 入口 → 编排 → 生命周期 → 登记 全链路 | 纵切一 |
| [ ] | Phase 3 | 交互纵切 | 成员之间通过正式通道交互 | 纵切二 |
| [ ] | Phase 4 | 协作 | 围绕共享状态协作 | 协作 |
| [ ] | Phase 5 | 生命周期与失败闭环 | shutdown/rollback 闭环 | 硬化 |
| [ ] | Phase 6 | 集成与架构 enforcement | SC、ARCH、Failure 测试全绿 | 集成验证 |

**滚动规划（Rolling-Wave Planning）**使用三种详细度：

- **过去压缩**：已完成 Task 只留结果和历史指针。
- **现在详细**：当前 Task 写全字段。
- **未来粗略**：后续 Phase 只写目标，近期一两个 Task 写大纲。

完成一个 Task 后刷新 Current Facts，再展开下一项。以下情况触发 Phase 重规划：

- 核心架构假设被证据推翻。
- Phase Goal 已不再合理。
- 新依赖使原顺序无法成立。
- 当前实现比预期多出或缺少关键能力。
- 某项风险的影响或不可逆性明显提高。

旧 Phase 标记为 Superseded，新 Phase 从更新后的事实与目标重新推导。

<a id="investigation-task"></a>

## 2.4 Phase 0 与 Investigation Task（调查型任务）

**调查型任务输出事实、证据、Blocker、Design Delta 和 GO / NO-GO。** Phase 0 的差距分析（Existing Code Gap Analysis）是典型形态。一份完整的 Gap Analysis 报告可以采用八段式：

1. **Baseline**:分支、HEAD、工作区状态、测试命令与实际结果、检查范围、仓库是否有修改。测试失败本身不使分析无法完成,但必须如实报告。
2. **Current Facts Validation**:逐条验证先前记录的代码事实,标记 confirmed / refuted / qualified,每条附代码证据。
3. **Component Inventory**:盘点每个相关组件,各标 reuse(复用)/ adapt(改造)/ new(新建)/ avoid(规避)之一,注明对应契约与目标 Phase。
4. **Phase Blockers**:阻塞下一阶段的问题,每条含 Invariant(什么不能牺牲)、Evidence(证据)、Impact(不处理的后果)、Recommended direction(推荐方向)。
5. **Deferred Questions**:明确不阻塞当前 Phase、留待后续的问题清单。
6. **Design Deltas**:发现的 Spec 缺口,每条含来源、推荐、备选、判断。
7. **GO/NO-GO for Phase**:结论;只有影响当前 Phase 的未解决设计冲突可以构成 NO-GO。
8. **Handoff**:只交报告不改仓库;建议人审并决定接受哪些事实与 Delta。

**Current Facts 的写法：**

- CF 编号。
- 状态：confirmed、refuted 或 qualified。
- 事实陈述和适用范围。
- 证据：基线 commit、仓库相对路径和行号，例如 `<commit>/<path>:<line>`。
- 表级基线：`Validated against: <commit>`。

每个 Task 完成后做 Impact-based Refresh，只重查本次触及领域的事实。历史证据继续绑定调查时的 commit，避免把后来行号当成原始基线。

**Accepted Design Constraints（DC）**保存跨多个 Task、持续限制实现自由度的高价值约束。每条使用 `ID | Constraint | Source`，并指向来源 Spec。DC 只有经过新证据、Human Review 和 Accepted Design Delta 才能修改。

**Decision Brief 的统一格式：**

1. Objective：这次要推进到哪里。
2. Verified Facts：只列影响决定的事实。
3. Decisions Required：最多 3–5 个，每个包含 Conflict、Options、Recommendation、Trade-off、Reversibility 和阻塞的下一步。
4. Deferred：本次明确不决定什么。
5. Recommendation：GO、Conditional GO 或 NO-GO。
6. Detailed Evidence：放在结论之后供抽查。

**审报告可以分三遍：**

1. 阅读 Goal、Blockers、Design Deltas 和 GO / NO-GO，确认需要裁决的问题。
2. 抽查每个 Blocker 的核心证据。
3. 独立比较 Options、Trade-off 和 Reversibility。

参数名、私有 helper 和文件落点等可逆实现细节可以标为“Phase 内决定”，避免占用高影响问题的评审时间。

**DD 裁决卡的结构。**每个需要人决策的点,用一张卡收口:

```
DD-nn
Facts:     事实是什么?
Decision:
  Invariant:  哪些东西不能牺牲?(先锁不变量)
  Mechanism:  用什么机制落实?(后定机制)
Why:       为什么这样选?
Deferred:  明确延后什么?
Verification: 怎么知道这个决定有效?
```

先确定 Invariant，再选择 Mechanism。不变量可以是“复用既有实现，不复制第二套逻辑”或“某模块是唯一状态 owner”；函数参数、薄适配器等可逆机制可以保留局部调整空间。职责边界发生变化时必须提出 Design Delta。

**Minimum Sufficient Decision**：为了让下一 Phase 安全开始，只裁决当前必须明确的内容。配合 Decision Horizon，把远期可逆细节留到获得更多证据后决定。

**决策框架八步：**

1. Evidence：什么证据说明问题存在。
2. Invariant：哪些性质不能牺牲。
3. Conflict：当前事实具体违反了什么。
4. Options：至少提出两个可行且有差异的方案。
5. Trade-off：比较复杂度、隔离、兼容、测试性、复用和迁移成本。
6. Minimum Sufficient Decision：当前最少需要锁定什么。
7. Verification：怎样验证决定有效。
8. Escape Hatch：判断失误时怎样退出或迁移。

决定记录还应说明：

- 已确认的当前事实。
- 尚未确认的部分。
- 选择当前方案的理由。
- Reversibility 与 Blast Radius。
- 验证方式和退出机制。

被接受的决定需要对应验证标准，例如复用、隔离、兼容和复杂度约束。无法描述验证方式时，应继续澄清决定的可观察结果。Human Review 分别检查事实证据和方案取舍，不要求复现整份调查。

<a id="implementation-task"></a>

## 2.5 Implementation Task（实现型任务）

实现型任务交付能力增量，并根据证据给出 Done、Partial 或 Blocked。控制重点包括：

1. **Baseline**：从什么状态开始。
2. **Scope**：哪里允许改变。
3. **Boundary**：哪些架构约束不能破坏。
4. **Verification**：怎样证明目标达成且没有回归。
5. **Escalation**：发现 Spec 不成立时怎么办。

**高风险实现任务用两段报告**。

动手前提交 **Preflight** 五段式:

1. **Baseline**:分支、HEAD、工作区状态、基线测试结果。
2. **Confirmed Implementation Facts**:动手前确认的代码事实(引用基线证据)。
3. **Planned Modules**:计划修改的文件/模块与每个区域的性质(主改 or 最小接缝)。
4. **Design Deltas Requiring Review**:发现 Spec 无法唯一确定实现的关键接缝,每条给出推荐裁决。
5. **Verification Gate**:验收门——人审接受全部 DD 后任务才可进入实现。

Preflight 结论是 Ready 或 Blocked。需要评审时，在相关决定接受后再开始依赖它的实现；已经授权的低风险、可逆局部问题可以按项目规则继续处理。

完成后提交 **Completion Report**：

1. **Implemented**：实现了什么。
2. **Files Changed**：修改了哪些职责区域或文件。
3. **Tests**：基线、定向和回归检查的实际结果。
4. **Boundary Checks**：依赖方向、禁止区域和越界能力检查。
5. **Design Deltas**：实现中发现的新 Delta；没有则写 None。
6. **Remaining Risks**：仍存在且已经明确的风险。
7. **Outcome**：Done、Partial 或 Blocked。

项目要求 Completion Review 时，评审接受前 Task 保持 In Progress。

**控制项从风险推导：**

- 编排层可能吸收内部行为 → 在 Must not 中禁止，并检查职责边界。
- 新功能可能顺手改动公共模块 → 加入架构测试和 Boundary Checks。
- 可能提前实现后续 Phase → 使用“本 Task 做 / 不做”表。
- 可能破坏旧路径 → 把兼容回归放入 Verify。
- 可能发生 scope creep → 使用 Allowed scope 和 diff audit。

<a id="feedback-handoff"></a>

## 2.6 向 09 Feedback 移交

`08 Tasks` 保存当前事实、差距、任务定义和执行证据。以下内容移交 `09 Feedback`：

- Design Delta。
- 关键证据争议。
- 规定的 Completion Review。
- Objective、Evidence、Blocker、候选选项和影响范围。

裁决完成后，08 接收已经传播的约束和下一步状态，不在 Task 内自行改写已接受设计。

<a id="task-lifecycle"></a>

## 2.7 Task 生命周期维护

**08 是滚动文档。**当前 Task 始终保有明确的 Spec 引用、Allowed scope、Must not 和 Verify。发现 Design Delta 时，暂停依赖旧前提的部分，完成裁决和规格传播后再继续。

**Task 的 Done 判定：**

- Goal achieved。
- 必需 Verify 在当前基线通过。
- Must not 未违反。
- 没有影响当前完成范围的未解决 Design Delta。
- 要求的 Completion Review 已接受。

**完成 Task 要压缩并保留历史。**详细定义压缩成 Completed Tasks 表中的一行：`Task | Outcome | End commit | History`。后续从新状态继续建立 Task，不改写旧任务当时描述的变化。

**信息按性质归位：**

- 当前事实与当前计划 → 08 Tasks。
- 被接受的目标、架构和验证规则 → `01–07` 对应权威位置。
- 裁决、传播和学习反馈 → 09 Feedback。
- 历史上发生过什么 → Git commit、PR 或归档目录。

**归档目录只保存 milestone evidence：**

- 正式 Gap Analysis 或同等级调查报告。
- 已接受的 Human Review。
- 能解释重大架构变化，且当前 Spec / ADR 无法完整表达调查过程的记录。

临时建议、brainstorm、失败的 prompt 输出和普通测试输出不进入长期归档。判断条件是：该材料半年后能否解释系统为何形成当前状态，并且现有 Spec / ADR 无法完整保存这段调查证据。

归档文件带元数据头。报告类:

```
Status: Archived / Non-authoritative
Task: TASK-XX <name>
Baseline: <commit hash>
Outcome: <review state>
Source of Truth: <authoritative documents>
```

审阅类:

```
Status: Accepted Review
Task: TASK-XX
Based on: <report>
Result: <adjudication summary>
Superseded by: <updated authoritative documents>
```

命名统一为 `TASK-XX_<artifact>.md`，例如 `TASK-01_gap-analysis.md`、`TASK-01_human-review.md`。历史证据使用 `<commit>/<path>:<line>` 绑定调查基线，不保存本机绝对路径；当前权威规则继续使用仓库相对路径和章节号。

Current Facts 通过 Impact-based Refresh 维护；DC 只通过 Human Review 和接受的 Design Delta 修改。08 保存当前事实与约束，历史证据保留原基线。

---

<a id="feedback-loop"></a>

# 3. 09 Feedback：Human Review 与闭环

`09 Feedback` 保存评审输入、裁决、传播计划和学习反馈。它不重新定义目标、架构或任务，也不把一条建议直接升级为事实。它的职责是区分证据、方案和授权，决定哪些变化被接受，再把接受的内容送回对应的权威位置。

<a id="spec-to-task"></a>

## 3.1 正向：Spec 约束 08 Tasks

设计层通过四条机制约束执行层：

- **References**：Task 引用 `01 Problem` 至 `07 Test Plan` 的具体条目，表示设计依据已经存在，实施时不能静默改写。
- **三层架构约束**：02 的人读规则、04 的代码契约和 07 的自动化检查共同进入 Task 的 Verify。
- **字段派生**：Preconditions、Allowed scope、Must、Must not 和 Verify 从当前规格与事实推导，不由实现者临时扩张。
- **Phase 顺序**：Phase 按能力成熟度推进，不提前实现后续阶段的行为。

<a id="design-delta"></a>

## 3.2 Design Delta 与停止条件

Design Delta 指新证据表明已接受的 Spec 无法继续成立，需要改变目标、边界、契约、失败语义、决定或证明方式。实现困难、局部算法选择和私有函数命名不自动构成 Design Delta。

当“按当前 Spec 完成 Task”与 Non-goal、架构规则、契约或 ADR 冲突时，实现者应暂停依赖旧前提的工作，并报告：

1. 哪条当前事实或证据推翻了哪条 Spec。
2. 为什么当前 Task 无法在既有边界内完成。
3. 最小 Design Delta、候选方案和受影响范围。
4. 在裁决前仍可安全继续的工作；没有则明确 Blocked。

```text
实现发现冲突 → 09 Feedback 收集证据 → Human Review
    → Accept / Reject / Explicitly Deferred / Needs Evidence
    → 定向传播规格 → 调整 08 Tasks → 继续或停止
```

<a id="human-review"></a>

## 3.3 Human Review

Human Review 是事实、方案、授权和完成证据的裁决点。高风险任务可以在 Preflight 后评审，完成报告也可以按项目规则要求评审。Review 至少包含：

- **Objective**：这次评审要决定什么，不决定什么。
- **Evidence Spot Checks**：抽查决定链中最关键的事实，不要求机械重做全部调查。
- **Decision Cards**：逐条列出 Invariant、Options、Trade-off、Reversibility、Blast Radius 和 Verification。
- **Adjudication**：每项给出 Accept、Reject、Explicitly Deferred 或 Needs Evidence。
- **Go / No-go**：说明哪些工作可以继续，Conditional Go 还缺哪些前提。
- **Propagation Plan**：接受的决定要回写哪些权威位置，哪些位置确认不受影响。

事实审核和方案审核需要分开。事实审核问证据是否支持当前描述；方案审核问候选是否守住不变量、代价是否可接受。阅读复杂报告时，可以先压缩成 Ownership、Lifecycle、State、Dependency Injection 和 Backward Compatibility 五类问题，再检查具体 Blocker。

<a id="change-routing"></a>

## 3.4 受控变化与影响传播

问题发生在哪一层，就先修改哪一层，再向下游检查实际影响：

| 新发现 | 首要处理位置 | 常见下游检查 |
| --- | --- | --- |
| Goal、Non-goal 或成功标准错误 | 01 Problem | 02–08 |
| 边界、职责或 owner 错误 | 02 Architecture，并记录必要 ADR | 03–08 |
| 流程、状态或生命周期不成立 | 03 Runtime | 04、05、07、08 |
| 跨模块规则与事实不匹配 | 04 Contracts | 05、07、08 |
| 失败传播或恢复责任错误 | 05 Failures | 04、07、08 |
| 取舍理由或选定机制改变 | 06 Decisions | 所有受影响规格与 08 |
| 证明方式不足或错误 | 07 Test Plan | 08 |
| Task 顺序或范围不准确 | 08 Tasks | 当前及后续 Task |
| 私有算法、函数名或 helper | Code / 当前 Task | 定向测试 |

```text
为什么做错了？              → 01
边界、职责或 owner 错了？   → 02
流程、状态或生命周期错了？  → 03
模块交互规则错了？          → 04
失败处理错了？              → 05
取舍理由或机制变了？        → 06
证明方式错了？              → 07
实施顺序或范围错了？        → 08
反馈如何裁决和传播？        → 09
局部私有实现错了？          → Code / 当前 Task
```

影响分析从变化点出发，不机械重写全部文档。接受决定只表示裁决完成；写入权威规格后才是 Propagated，实现完成后才是 Implemented，取得指定证据后才是 Verified。

<a id="done-gate"></a>

## 3.5 Done Gate 与传播检查

宣布 Done 前逐项确认：

- [ ] Goal 已实现，代码提交本身不作为完成证明。
- [ ] 必需 Verify 在当前基线实际通过。
- [ ] Must not、依赖方向和修改范围已经检查。
- [ ] 未运行检查的原因和影响已经说明。
- [ ] 没有影响当前完成范围的未解决 Design Delta。
- [ ] Accepted Decision 已传播到受影响的规格。
- [ ] 规定的 Completion Review 已接受。
- [ ] Current Facts 已刷新，完成 Task 已压缩。

<a id="closed-loop-diagram"></a>

## 3.6 闭环总图

```text
支柱 A：Spec 编写（01–07）            支柱 B：Spec 执行（08）
┌──────────────────────────────┐      ┌────────────────────┐
│ 01 → 02 → 03 → 04 → 05 → 07 │ ───→ │ 08 → Code → Evidence│
│  ↑    ↑    ↑    ↑            │      └─────────┬──────────┘
│  └──── Decisions（06）───────┘                │
└──────────────────────────────┘                ↓
      ↑                                  09 Feedback / Review
      └──────── Accepted + Propagated ──────────┘
```

`01 Problem` 至 `07 Test Plan` 展开 Specification 与 Design，`08 Tasks` 组织 Implementation，`09 Feedback` 裁决 Verification 中出现的新证据：

- 代码事实变化先刷新 Current Facts。
- Task 暴露 Contract 问题时回到 04 Contracts。
- Contract 暴露 Runtime 问题时回到 03 Runtime。
- Runtime 暴露 Architecture 问题时回到 02 Architecture。

---

<a id="practice"></a>

# 4. 实战方法与训练

<a id="human-ai-roles"></a>

## 4.1 人与 AI 的分工

在这套流程中，人通常承担 Problem owner、Architect、Decision maker 和 Reviewer；AI 可以承担资料整理、现状调查、候选方案生成、原型、实现、测试和静态分析。具体授权由当前任务决定，不把角色列表当作默认实施许可。

高影响决定由人确认，AI 在已接受的目标、范围和边界内推进。任务保持清晰、有限范围，尽量让每一步可运行、可测试、可评审、可回退。

<a id="human-first"></a>

## 4.2 Human-first 训练

如果目标是训练自己的设计判断，可以在新模块开始前先独立完成一轮限时设计，例如用 30–60 分钟回答 Problem、Context、Components、Runtime、State、Failure、Alternatives 和 Decision，再让 AI 评审。重点是保留“先形成自己的判断，再用反馈修正”的练习过程；时间可以按问题规模调整。

<a id="question-chain"></a>

## 4.3 看到需求时的问题链

看到“实现某个能力”的需求时，先回答会决定实现方向的问题：

```
Why?                         为什么做?
Who owns lifecycle?          谁拥有生命周期?
What states exist?           存在哪些状态?
What transitions are legal?  哪些转移合法?
What is the protocol?        交互协议是什么?
What if ... fails?           各失败场景下发生什么?
What happens to owned ...?   它拥有的资源/任务去哪?
What is the timeout?         超时语义是什么?
What is observable?          调用方能看到什么?
What invariants remain true? 什么不变量必须恒真?
Which module may know this?  哪个模块被允许知道这件事?
How can I test these?        怎么测试这些约束?
```

这些问题不要求一次写成完整长文。它们帮助识别需要明确的 owner、状态、协议、失败和验证，答案足以约束当前增量时即可继续。

<a id="small-changes"></a>

## 4.4 拆小原则

中等以上能力通常需要拆成一串可验证的小步，例如定义状态模型、实现领域对象、建立登记、落实契约、接入生命周期、补充清理。每一步应只交付一个主要结果，并尽量做到可运行、可测试、可评审、可回退。具体切分方法见 [2.1 Task 模型](#task-model)和[2.2 Task 模板](#task-template)。

<a id="practice-checklist"></a>

## 4.5 实战自检清单

- [ ] 问题与现状写清了吗？Goal、Non-goal、SC 齐了吗？
- [ ] 术语和系统边界明确了吗？
- [ ] 每个模块的责任、Must not 和 owner 明确了吗？
- [ ] 每条关键路径都有成功主链与关键失败分支吗？
- [ ] 状态转移、Guard、触发权限和权威 owner 一致吗？
- [ ] 跨模块契约覆盖输入、输出、状态效果、失败、幂等和超时吗？
- [ ] 每个重要失败场景都有检测、传播、恢复 owner 和最终状态吗？
- [ ] 外部动作结果未知时，是否避免把未知写成失败并盲目重试？
- [ ] 每个重大取舍都有候选、代价、验证、退出机制和重审条件吗？
- [ ] QAS、架构规则和 SC 都有相应证明方式吗？
- [ ] Traceability Matrix 能把承诺连到测试、Task 和实际证据吗？
- [ ] 写 08 前做过差距分析吗？Current Facts 绑定了适用基线吗？
- [ ] 每个 Task 的 Goal、References、Preconditions、Must not 和 Verify 完整吗？
- [ ] 高风险任务有 Preflight 吗？完成后有 Completion Report 和要求的评审吗？
- [ ] 发现 Spec 不成立时，是否通过 09 Feedback 裁决并回写正确层级？

---

<a id="appendix"></a>

# 附录 A：术语、方法与学习指导

<a id="glossary"></a>

## A.1 核心术语

| 术语 | 本文中的含义 | 主要章节 |
| --- | --- | --- |
| SDD | 先让目标、设计与验证依据收敛，再实施并用反馈修正规格 | [总览](#overview) |
| Current Fact | 在指定版本和范围内，由代码、测试或观察支持的当前事实 | [08 Tasks](#task-execution) |
| Accepted Design | 已按项目规则接受、但不等于已实现或已验证的设计 | [06 Decisions](#decisions) |
| Design Delta | 新证据表明已接受 Spec 无法继续成立时提出的设计变化请求 | [09 Feedback](#design-delta) |
| Owner | 对状态、资源合法性或生命周期承担最终责任的构件 | [02 Architecture](#architecture) |
| Invariant | 在相关范围内必须始终成立的性质 | [02 Architecture](#architecture) |
| Contract | 跨模块可依赖的输入、输出、状态效果和失败语义 | [04 Contracts](#contracts) |
| Commit point | 外部或已提交动作越过后，不能由本地简单撤销的时刻 | [03 Runtime](#runtime) |
| Result unknown | 本地证据不足以判断外部动作成功或失败的状态 | [05 Failures](#failures) |
| ADR | Architecture Decision Record，记录重要决定及其背景、候选和后果 | [06 Decisions](#decisions) |
| QAS | Quality Attribute Scenario，把质量目标写成带环境、刺激、响应和度量的场景 | [07 Test Plan](#test-plan) |
| Vertical slice | 贯穿最少必要层级、交付一个可观察结果的纵向切片 | [08 Tasks](#task-model) |
| Rolling-Wave Planning | 近期详细、远期粗略，并随新证据滚动修正的规划方式 | [Phase 规划](#rolling-wave) |
| Human Review | 对事实、方案、授权和完成证据进行人工裁决的检查点 | [Human Review](#human-review) |

<a id="method-map"></a>

## A.2 Architecture Before Coding 方法对照表

| 问题 | 方法 |
| --- | --- |
| 我要解决什么? | Design Doc / RFC |
| 系统边界是什么? | C4(重点 Context/Container 两层) |
| 系统由哪些模块构成? | arc42 Building Block View |
| 程序到底怎么跑? | Runtime View + Sequence Diagram |
| 状态如何变化? | State Machine |
| 接口是什么? | Contract / Schema |
| 系统为什么这样设计? | ADR |
| 哪些质量最重要? | Quality Attribute Scenario |
| 架构是否合理? | mini-ATAM |
| 如何避免架构漂移? | Fitness Functions / Architecture Tests |
| 怎么让 AI 按设计实现? | Spec-Driven Development + 项目指令 |
| 怎么避免一次修改过大? | Small changes / vertical slices |

<a id="arc42-checklist"></a>

## A.3 arc42 十二问清单

arc42 的 12 个部分可以当作架构问题清单使用，不要求每个功能写满 12 章：

| arc42 部分 | 你应该理解的问题 |
| --- | --- |
| Goals | 为什么做 |
| Constraints | 不能违反什么 |
| Context | 系统边界 |
| Solution Strategy | 核心方案 |
| Building Blocks | 模块 |
| Runtime View | 程序流程 |
| Deployment | 怎么运行 |
| Cross-cutting | 通用机制 |
| Decisions | 为什么这样设计 |
| Quality | 好的标准是什么 |
| Risks | 主要风险在哪里 |
| Glossary | 名词是什么意思 |

<a id="learning-path"></a>

## A.4 建议学习顺序

不必读完所有材料再开发。每学一种方法，就在独立构造的练习项目或自己的当前项目中验证一次：

| 阶段 | 学什么 | 练什么 |
| --- | --- | --- |
| 1 | C4 + arc42 Lite | 重画当前系统的边界与模块 |
| 2 | Sequence + State Machine | 描述核心循环与生命周期 |
| 3 | ADR | 把已有关键设计决策补出来 |
| 4 | Quality Attributes | 为可扩展性/可靠性写场景 |
| 5 | ADD + mini-ATAM | 为高影响模块比较 2–3 个方案 |
| 6 | Evolutionary Architecture | 写架构测试 |
| 7 | Software Engineering at Google | 改进 review 与变更纪律 |
| 8 | Spec-Driven Development | 规范 AI 协作开发流程 |
| 9 | iSAQB 体系(含 AGENTA) | 系统学习 AI 时代的架构 |

<a id="external-methods"></a>

## A.5 参考资料与方法关系

链接依据 V2 术语与方法索引整理，复核日期：2026-09-16。

- [GitHub Spec Kit](https://github.com/github/spec-kit) 是公开的 spec-driven 工具项目，当前把 SDD 组织为 specification、technical plan、tasks、implementation 和 convergence 等产物与活动。本文的 `01–09` 信息结构和七步活动是独立整理，不等同于其命令、技能或版本流程。
- [C4 model 的 diagram 指南](https://c4model.com/diagrams)提供按沟通目的选择系统上下文、容器、组件和代码视图的方法。本文借用先解释边界与主要构件、再决定是否需要细化视图的思路，不要求维护固定数量的图。
- [arc42 模板总览](https://arc42.org/overview/)提供软件架构文档的结构化问题地图。本文把它用于检查覆盖面，不要求逐章生成产物。
- Michael Nygard 的[《Documenting Architecture Decisions》](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)介绍了用 Status、Context、Decision 和 Consequences 保存架构决定的轻量记录。本文在此基础上加入 Verification、Escape Hatch、Review Trigger 和传播状态，以适配当前工作流。
- Carnegie Mellon University Software Engineering Institute 的[ATAM 资料集](https://www.sei.cmu.edu/library/architecture-tradeoff-analysis-method-collection/)介绍了以业务驱动和质量属性场景评估架构，并识别风险、敏感点和取舍点的方法。本文的 mini-ATAM 是个人实践中的轻量借鉴，不代表执行了正式 ATAM。
- [Thoughtworks 的《Building Evolutionary Architectures》页面](https://www.thoughtworks.com/insights/books/building-evolutionary-architectures)可用于了解演进式架构和 fitness function。本文把可自动检查的依赖与边界规则视为架构验证的一部分，不要求所有规则自动化。
- [Software Engineering at Google 在线版](https://abseil.io/resources/swe-book)可用于延伸阅读设计文档、评审、测试和长期维护。本文不把其中任一团队实践直接写成普遍规则。
- [iSAQB Advanced Level 模块页](https://www.isaqb.org/certifications/cpsa-certifications/cpsa-advanced-level/)提供软件架构进阶主题入口，其中包括面向 Agentic Software Engineering Contexts 的 AGENTA。它是学习线索，不是本文工作流效果的证明。

外部来源只支持相邻的方法说明，不用于证明这套工作流提高了效率或质量。涉及工具命令、模块名称和版本的信息，应在发布前重新核对官方页面。

---

这套实践可以压缩成一个循环：写下足以约束当前增量的 Spec，让 Task 在边界内执行；新证据推翻前提时，通过 `09 Feedback` 裁决，并从信息所属层级向下传播。

[返回目录](#toc)
