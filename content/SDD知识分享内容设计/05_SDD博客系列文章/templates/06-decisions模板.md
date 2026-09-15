# 06 Decisions：{功能或系统名称}

## ADR-{编号}：{一个架构显著决定}

Status：Proposed / Accepted / Rejected / Deferred / Superseded  
Date：{日期}  
Decision horizon：{至少支撑到哪个阶段}  
Review source：{Human Review 或决定者；适用时填写}

### Context

- Conflict：{需要裁决的具体张力}
- Evidence baseline：{当前事实与适用版本}
- Invariant：{不能牺牲的性质}
- Drivers：{01 中的驱动因素}
- Unknowns：{仍不确定的事实}

### Alternatives

| Option | Invariant fit | Driver trade-off | Complexity | Reversibility | Blast radius | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| A | {分析} | {分析} | {分析} | {高/中/低} | {大/中/小} | Accept / Reject / Defer |
| B | {分析} | {分析} | {分析} | {高/中/低} | {大/中/小} | Accept / Reject / Defer |

### Decision

{接受什么，以及明确不决定什么。}

### Consequences

- Positive：{获得什么}
- Negative：{付出什么}
- New responsibilities：{新增所有权、运维或验证责任}

### Verification

- {能支持或反驳决定的证据}

### Escape hatch and review trigger

- Escape hatch：{判断错误时怎样退出或迁移}
- Review trigger：{出现什么证据时重审}
- Deferred：{延期项、依赖它的工作和重审条件}

### Propagation status

| Target | Required change | Status |
| --- | --- | --- |
| `01–08` 中的 {文档} | {条目} | Pending / Propagated / Not applicable |

写法说明见[06 Decisions 系列文章](../06_Decisions_设计取舍与决策记录.md)。
