# 07 Test Plan：{功能或系统名称}

状态：Draft / In Review / Accepted  
验证基线：{计划适用版本或环境}

## 1. Status semantics

- Planned：只完成验证设计，尚未执行。
- Partial / Blocked：证据不完整或执行受阻。
- Passed at {baseline}：在指定基线实际通过。
- Failed at {baseline}：在指定基线发现不符合预期。

## 2. Verification items

| ID | Layer | Promise under test | Setup / Stimulus | Expected evidence | Status / Actual result |
| --- | --- | --- | --- | --- | --- |
| TEST-01 | Unit / Contract / State / Integration / Architecture / E2E | {承诺} | {条件与动作} | {可反驳的观察} | Planned |

## 3. Failure verification

| Failure ID | Detection | Propagation | Recovery | Final state | Test ID |
| --- | --- | --- | --- | --- | --- |
| {F-XX} | {预期} | {预期} | {预期} | {预期} | {TEST-XX} |

## 4. Quality Attribute Scenarios

| ID | Source | Stimulus | Environment | Artifact | Response | Measure / Source |
| --- | --- | --- | --- | --- | --- | --- |
| QAS-01 | {来源} | {刺激} | {条件} | {对象} | {响应} | {阈值及依据} |

## 5. Traceability Matrix

| Requirement / SC | Architecture | Runtime / State | Contract | Failure | Decision | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| {SC-XX} | {ARCH/INV} | {ST} | {API} | {F 或 N/A} | {ADR 或 N/A} | {TEST} |

## 6. Completion gate

- [ ] Goal 的必需行为有实际证据。
- [ ] 关键边界、契约、状态和失败路径已覆盖。
- [ ] 受影响回归已执行。
- [ ] 未执行检查已说明原因和影响。
- [ ] Accepted Design Delta 已传播并验证。
- [ ] 必需 Completion Review 已接受。

## 7. Evidence record

| Baseline / Environment | Command or observation | Result | Scope proved | Limitations |
| --- | --- | --- | --- | --- |
| {版本与环境} | {实际检查} | Pass / Fail / Blocked | {证明范围} | {不能证明什么} |

写法说明见[07 Test Plan 主笔记](../07_Test_Plan_验证设计与完成条件.md)。

