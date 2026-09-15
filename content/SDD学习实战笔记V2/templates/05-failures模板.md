# 05 Failures：{功能或系统名称}

状态：Draft / In Review / Accepted

## 1. Failure Policy

- Domain failure：{表示与传播规则}
- Retry owner：{唯一责任层与预算}
- Partial construction：{回滚所有权}
- Shutdown / close：{是否幂等}
- Cleanup：{best-effort 与错误聚合规则}
- Illegal transition：{拒绝与状态保持}
- Unknown external result：{记录、查询与人工恢复规则}

## 2. Error categories

| Category | Examples in this design | Handling verb |
| --- | --- | --- |
| Programmer / Domain / Environment / Transient / Permanent / Cancellation / Timeout | {例子} | Raise / Reject / Retry / Rollback / Compensate / Cleanup / Escalate |

## 3. Failure scenarios

| ID | Failure | Detect | Propagate | Recovery owner | Retry / Idempotency | Rollback / Compensation / Cleanup | Final state | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F-XX-01 | {失败} | {检测点} | {接收者} | {责任方} | {规则} | {动作} | {可查询状态} | {07 条目} |

## 4. External unknown result

- Request ID：{关联或幂等标识}
- Commit point：{可能已生效的时刻}
- Query support：Yes / No / Unknown
- Safe replay condition：{接收端保证；没有则禁止推断}
- Manual path：{需要时的人工处置}

## 5. Cascading-failure checks

- 多层重试：{如何避免}
- 单点失败隔离：{边界}
- 多项清理：{如何继续并聚合}
- 非关键依赖降级：{适用时填写}

## 6. Decisions and impact

- ADR：{06 条目}
- 同步 `03/04/07/08`：{受影响条目}

写法说明见[05 Failures 主笔记](../05_Failures_失败语义与恢复责任.md)。

