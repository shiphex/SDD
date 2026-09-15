# 04 Contracts：{模块或能力名称}

状态：Draft / In Review / Accepted  
Provider：{提供方}  
Consumers：{允许依赖的调用方}

## 1. Purpose and ownership

- Purpose：{边界存在的原因}
- Owner：{提供与生命周期责任}
- Related runtime：{03 状态或事件}

## 2. Public operations

### API-01：`{operation}`

- Semantics：{操作含义；Command / Query / Event}
- Input：{必需字段和约束}
- Output：{调用方可依赖字段}
- Preconditions：{可校验条件}
- Postconditions：{成功后保证}
- State effect：{对应状态转移或无状态变化}
- Domain failures：{稳定失败类型与条件}
- Idempotency：{键、范围、同键不同载荷语义；不适用则说明}
- Cancellation：{停止后续工作的保证}
- Timeout：{确定失败、未知或查询句柄}
- Authorization：{谁可调用}

## 3. Shared types and compatibility

| Type / Field | Meaning | Compatibility rule |
| --- | --- | --- |
| {类型或字段} | {语义} | {旧调用方、版本或迁移窗口} |

## 4. Runtime invariants

- INV-01：{跨调用始终成立的性质}

## 5. Must NOT

- {该接口绝不能暴露的越界能力}

## 6. Failure and verification links

- Failure IDs：{05 条目}
- Contract / State / Compatibility tests：{07 条目}
- ADR：{06 条目}

写法说明见[04 Contracts 系列文章](../04_Contracts_模块交互规则.md)。
