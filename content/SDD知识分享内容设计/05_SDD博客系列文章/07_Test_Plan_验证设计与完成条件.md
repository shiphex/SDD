# 07 Test Plan：验证设计与完成条件

> SDD 系列第 7 篇｜上一篇：[06 Decisions](06_Decisions_设计取舍与决策记录.md)｜下一篇：[08 Tasks](08_Tasks_从差距到可验证增量.md)｜总览：[小白如何用 SDD 与 AI 开发软件](../04_小白如何用SDD与AI开发软件_博客.md)｜配套：[07 Test Plan 模板](templates/07-test-plan模板.md)

测试计划把目标、契约、状态、失败和架构约束转换成能够区分正确与错误实现的证据要求。具体命令应服从这些要求。

## 1. 本文回答的核心问题

`07` 回答：需要什么证据，才能证明需求、契约、状态、失败语义和架构约束在指定版本与范围内成立。

Test Plan（测试计划）描述准备怎样验证；实际执行证据描述已经观察到什么；完成结论判断这些证据是否覆盖全部必需条件。三者不能互相替代。

## 2. 为什么需要这份文档

如果先实现、最后再“补几个测试”，容易只覆盖代码已经方便暴露的路径，遗漏设计已经承诺的行为。

在编码前设计验证有三个作用：

- 迫使模糊的目标、边界和决定变成可观察承诺。
- 帮助 Task 找到最小可验证切片。
- 防止用局部测试通过推断整个目标完成。

验证不只等于测试代码。静态规则检查、人工 spot check、运行观测和外部结果查询都可以是证据，但必须说明各自证明的范围。

## 3. 写作前需要哪些输入

- `01` 的 Success Criteria（SC）和 Architecture Drivers。
- `02` 的不变量、依赖方向和 Must not。
- `03` 的主链、状态转移、时序、生命周期和提交点。
- `04` 的操作、前后置条件、领域失败和兼容语义。
- `05` 的 Failure ID、重试、恢复和最终状态。
- `06` 中每项 Accepted Decision 的 Verification。
- 当前测试设施、可观察接口和基线能力的事实。

若测试环境尚不具备某项能力，应将其记录为 Gap，并保持对应计划项未完成。

## 4. 设计时应依次思考哪些问题

### 4.1 从承诺推导证据

对每条承诺问：

1. 谁能观察结果？
2. 在什么初始条件下触发？
3. 需要观察哪些状态、输出或副作用？
4. 什么结果能反驳该承诺？
5. 哪一层测试最经济且足够可信？

不要从“已有测试框架支持什么”倒推规格。

### 4.2 分配测试层级

| 层级 | 主要证明内容 | 不适合单独证明 |
| --- | --- | --- |
| Unit | 局部算法、纯规则和边界条件 | 模块组合、真实外部契约 |
| Contract | 提供方与调用方共享的输入、输出和失败语义 | 整体业务流程 |
| State | 合法/非法转移、Guard、并发和终态 | 外部集成真实性 |
| Integration | 模块、存储或适配器组合后的行为 | 完整用户旅程 |
| Architecture | 依赖方向、禁止导入、边界形状 | 运行时业务正确性 |
| End-to-end | 关键用户路径和系统组合 | 所有边界条件的经济覆盖 |

同一承诺可以有多层证据，但每层要说明为什么需要，避免重复而无新增信心。

### 4.3 把状态与失败变成反例

状态测试除合法转移外，还应覆盖：

- 非法转移被拒绝且原状态不变。
- 重复事件的语义符合契约。
- 乱序事件不会越过 Guard。
- 终态按要求保持可查询。

每个关键 Failure ID 至少有一种证据，证明检测点、传播方式、恢复 owner 和最终状态符合 `05`。

### 4.4 让架构规则逐层落地

架构约束可以形成三层链：

1. `02` 的人读规则：例如“查询层不得修改领域状态”。
2. `04` 的代码契约：查询接口不暴露写操作。
3. `07` 的持续检查：依赖规则测试、接口形状测试或静态检查。

能够持续自动评估的架构特征，可以写成 [Architecture Fitness Functions](https://www.thoughtworks.com/content/dam/thoughtworks/documents/books/bk_building_evolutionary_architectures_second_edition_free_chapter.pdf)（架构适应度函数）。它们是当前架构验证的一部分，不意味着所有架构判断都能自动化。

部分规则无法自动化。对风险重要的此类规则，记录明确的人工检查方法和抽样范围。

### 4.5 写 Quality Attribute Scenario

[Quality Attribute Scenario](https://www.sei.cmu.edu/library/architecture-tradeoff-analysis-method-collection/)（质量属性场景，简称 QAS）把“快、稳、可恢复”等形容词改成可测情境：

| 元素 | 问题 |
| --- | --- |
| Source | 谁或什么产生刺激？ |
| Stimulus | 发生什么事件？ |
| Environment | 在什么运行条件下？ |
| Artifact | 哪个系统部分受到影响？ |
| Response | 系统预期怎样响应？ |
| Measure | 用什么阈值或观察判定？ |

阈值必须来自需求、基线或接受的决定，不能为了让表格完整而编造。

### 4.6 建立 Traceability Matrix

Traceability Matrix（追踪矩阵）连接跨文档编号：

| Requirement / SC | Architecture rule | Runtime / State | Contract | Failure | Decision | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| SC-XX | ARCH-XX | ST-XX | API-XX | F-XX | ADR-XX | TEST-XX |

每一格可以按适用性填写，但任何重要承诺都应能找到足够的设计与验证依据。空格必须说明“不适用”及原因，避免形成无声遗漏。

### 4.7 定义勾选语义

推荐统一使用：

- `[ ] Planned`：验证方式已设计，尚未执行。
- `[~] Partial / Blocked`：执行过但证据不完整，或受阻。
- `[x] Passed at <baseline>`：已在明确版本与环境执行并通过。
- `[!] Failed at <baseline>`：已执行且发现不符合预期。

如果 Markdown 工具不支持非标准复选框，可用状态列替代。关键是不能把“已写测试”或“文件存在”直接标成通过。

### 4.8 设计完成门槛

Task 或阶段完成前至少检查：

- Goal 对应的必需行为已有实际证据。
- 关键约束和受影响回归已验证。
- 未执行检查已说明原因及影响。
- 已接受的 Design Delta 已传播到规范、实现和验证。
- 没有影响当前完成范围的未解决阻塞项。
- 项目要求的 Completion Review 已完成。

## 5. 最小内容与高风险扩展内容

### 5.1 最小内容

- SC 到验证项的映射
- 关键契约、状态和失败场景
- 测试层级与执行条件
- 完成门槛
- 计划与实际结果的状态规则

### 5.2 高风险扩展

- 完整 Traceability Matrix
- QAS 与阈值来源
- 故障注入和恢复演练
- 并发、乱序和重复事件
- 兼容矩阵与迁移测试
- 架构自动检查和人工 spot check
- 环境、数据、版本与证据保留方式

## 6. 独立虚构示例

> 教学推演：以下“多语言菜单草稿器”完全虚构，只用于说明验证设计。所有条目均为 Planned，不代表实际执行。

目标之一是：翻译人员可以保存多个草稿，但只有经审核的版本能够被发布。

### 6.1 验证项

| ID | 层级 | 预期证据 | 状态 |
| --- | --- | --- | --- |
| TEST-01 | State | “草稿 → 发布”被拒绝，原状态不变 | Planned |
| TEST-02 | Contract | `publish` 对未审核版本返回 `ReviewRequired` | Planned |
| TEST-03 | Integration | 审核通过后发布，查询接口返回同一版本号 | Planned |
| TEST-04 | Architecture | 翻译适配器没有直接写发布状态的能力 | Planned |

### 6.2 追踪矩阵

| SC | Architecture | State | Contract | Failure | Decision | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| SC-01 仅审核版本可发布 | ARCH-01 发布状态由 Catalog owner 管理 | ST-03 | API-PUBLISH | F-PUB-01 | ADR-002 | TEST-01/02/03/04 |

### 6.3 结论边界

这张表只说明“准备怎样证明”。在测试实际运行并绑定到明确基线前，不能写“仅审核版本可发布已验证”。

## 7. 常见错误与诊断方式

| 错误 | 诊断问题 | 修正方向 |
| --- | --- | --- |
| 从测试函数清单开始 | 它们分别证明哪条承诺？ | 从 SC、契约和失败反推 |
| 一个 E2E 覆盖所有内容 | 失败时能定位哪条规则吗？ | 分配到合适测试层 |
| 测试文件存在就勾选 | 在哪个版本实际运行过？ | 记录基线与结果 |
| QAS 阈值凭空出现 | 阈值由谁接受、依据是什么？ | 补需求或基线来源 |
| 只测合法状态转移 | 非法、重复、乱序会怎样？ | 增加反例和不变性检查 |
| 测试通过就宣布全部完成 | 未验证约束和评审门槛呢？ | 对照完整完成条件 |

## 8. 与其他文档的输入、输出和更新关系

- 从 `01` 接收 SC 和 Driver。
- 从 `02–05` 接收边界、状态、契约和 Failure ID。
- 从 `06` 接收每项决定的 Verification。
- 输出给 `08`：每个 Task 的 Verify 和完成门槛。
- 从实施接收实际结果，并在 `08` 的 Completion Report 中绑定基线。
- 验证方式被证据推翻时，形成 Design Delta 回到对应文档；只为迎合实现而修改测试会掩盖设计冲突。

## 9. 什么变化会触发本文更新

- SC、契约、状态、失败语义或架构规则改变。
- Accepted Decision 的验证方式改变。
- 实现引入新的高风险路径或兼容面。
- 现有验证不能区分正确与错误实现。
- 测试环境或观察接口变化使证据失效。

单次运行结果通常更新完成记录，不改写 Test Plan；只有验证设计本身变化才更新本文件。

## 10. 对应模板与延伸阅读

- [07 Test Plan 模板](templates/07-test-plan模板.md)
- [01 Problem](01_Problem_问题目标与成功标准.md)
- [03 Runtime](03_Runtime_运行流程状态与生命周期.md)
- [05 Failures](05_Failures_失败语义与恢复责任.md)
- [08 Tasks](08_Tasks_从差距到可验证增量.md)
- [SEI Architecture Tradeoff Analysis Method 资料集](https://www.sei.cmu.edu/library/architecture-tradeoff-analysis-method-collection/)
- [Building Evolutionary Architectures 节选](https://www.thoughtworks.com/content/dam/thoughtworks/documents/books/bk_building_evolutionary_architectures_second_edition_free_chapter.pdf)

---

系列导航：上一篇：[06 Decisions：设计取舍与决策记录](06_Decisions_设计取舍与决策记录.md)｜下一篇：[08 Tasks：从差距到可验证增量](08_Tasks_从差距到可验证增量.md)｜[返回总览](../04_小白如何用SDD与AI开发软件_博客.md)
