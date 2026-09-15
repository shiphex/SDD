# 08 Tasks：{功能或阶段名称}

状态：Planning / In Progress / In Review / Blocked / Done  
当前基线：{版本、工作区与日期}

## 1. Current Facts

| ID | Fact | Evidence | Last checked | Affected by current Task? |
| --- | --- | --- | --- | --- |
| CF-01 | {当前事实} | {版本/路径/测试/观察} | {日期} | Yes / No |

## 2. Accepted Design Constraints

| ID | Constraint | Authoritative reference | Propagation status |
| --- | --- | --- | --- |
| DC-01 | {已接受约束} | {01–07 条目} | Propagated / Pending |

## 3. Phase plan

| Phase | Target capability | Dependencies | Review trigger | Status |
| --- | --- | --- | --- | --- |
| 1 | {近期能力} | {依赖} | {新证据触发重排} | Current / Future / Done |

## 4. Gap derivation

- Current State：{当前可观察能力}
- Target：{近期已接受目标}
- Gap：{缺少什么，不先写方案}
- Smallest Delta：{一个主要可验证结果}
- Evidence：{完成所需实际证据}

## 5. TASK-{编号}：{结果式名称}

Type：Investigation / Implementation  
Status：Planned / Ready / In Progress / In Review / Blocked / Done

### Goal

{完成后可以观察到什么结果。}

### References

- `01`：{Goal / Non-goal / SC}
- `02`：{边界 / owner / invariant}
- `03`：{流程 / 状态 / 生命周期}
- `04`：{契约}
- `05`：{Failure ID}
- `06`：{Accepted ADR；无则 N/A}
- `07`：{Verification ID}

### Preconditions

- {为什么现在可以开始；未满足项必须阻塞或转调查}

### Allowed scope

- Primary：{允许改变的职责区域}
- Minimal seams：{必要接缝及理由}

### Must

- {完成 Goal 必需的最小事实}

### Must not

- {最可能发生的范围扩张或边界破坏}

### Verify

- {编码前定义的定向、回归和边界检查}

### Design Delta rule

- Stop when：{哪些冲突需要暂停}
- Report：{冲突 Spec、证据、最小选项和影响}

## 6. Preflight（高风险任务适用）

- Baseline：{版本、工作区、基线测试}
- Confirmed Implementation Facts：{证据}
- Planned Modules：{主改与最小接缝}
- Design Deltas Requiring Review：None / {条目}
- Verification Gate：{进入实施门槛}
- Outcome：Ready / Blocked

## 7. Completion Report

- Implemented：{实际结果}
- Files Changed：{范围与原因}
- Tests：{实际执行、结果与基线}
- Boundary Checks：{Must not、禁止依赖、零修改区域}
- Design Deltas：None / {状态与传播}
- Remaining Risks：{不阻塞当前完成的已知风险}
- Outcome：Done / Blocked / Partial

## 8. Completed Tasks

| Task | Outcome | End baseline | History / Evidence |
| --- | --- | --- | --- |
| {TASK-XX} | {结果摘要} | {版本} | {必要入口} |

写法说明见[08 Tasks 系列文章](../08_Tasks_从差距到可验证增量.md)。
