# 03 Runtime：{功能或系统名称}

状态：Draft / In Review / Accepted  
依据：[01 Problem]({相对链接})、[02 Architecture]({相对链接})

## 1. Success flow：{用例名称}

1. {发起者、动作、状态或数据效果}
2. {处理者、动作、状态或数据效果}
3. {调用方可观察结果}

## 2. Alternate and failure flows

| Step | Failure / Alternate event | Observable result | Failure ID |
| --- | --- | --- | --- |
| {主链步骤} | {失败或分支} | {最终可见状态} | {F-XX} |

## 3. State machine

| State ID | Current | Event | Guard | Next | Side effect |
| --- | --- | --- | --- | --- | --- |
| ST-01 | {当前状态} | {事件} | {守卫条件} | {下一状态} | {副作用} |

## 4. Event authority

| Event | Request / Report authority | Evidence checked by owner |
| --- | --- | --- |
| {事件} | {允许者} | {状态、版本、令牌等} |

- Authoritative state owner：{唯一 owner}
- Illegal transition：{拒绝方式与原状态语义}

## 5. Lifecycle

| Stage | Owner | Action | Failure / Cleanup |
| --- | --- | --- | --- |
| Create / Run / End / Cleanup | {责任方} | {动作} | {失败与收敛方式} |

## 6. External commit points

| Action | Commit point | Timeout meaning | Query / Idempotency support |
| --- | --- | --- | --- |
| {外部动作} | {不可简单撤销的时刻} | {失败或未知} | {能力或 Unknown} |

## 7. Observability

- Observer：{谁需要看结果}
- Authoritative view：{查询或事件}
- Retention：{终态保留要求}

## 8. Impact

- 需要同步的 `04/05/07/08`：{条目}
- 相关 ADR：{06 条目}

写法说明见[03 Runtime 主笔记](../03_Runtime_运行流程状态与生命周期.md)。

