# 02 Architecture：{功能或系统名称}

状态：Draft / In Review / Accepted  
依据：[01 Problem]({相对链接})

## 1. Glossary

| Term | Definition | Avoid |
| --- | --- | --- |
| {术语} | {本设计中的唯一含义} | {不使用的近义词} |

## 2. System boundary

- Inside：{系统负责的内容}
- Outside：{外部人、设备或服务}
- Entry points：{数据与控制入口}
- External effects：{系统不能最终控制的结果}

```text
{只画支持当前决定所需的上下文或构件关系}
```

## 3. Components and boundaries

| ID | Component | May | Must not |
| --- | --- | --- | --- |
| ARCH-01 | {构件} | {允许职责} | {高风险越界能力} |

## 4. Ownership

| State / Resource | Create | Authoritative owner | Mutate | Release / End | Observe |
| --- | --- | --- | --- | --- | --- |
| {对象} | {责任方} | {唯一 owner} | {允许者} | {责任方} | {只读者} |

## 5. Lifecycle and composition

- Composition root：{依赖组装位置}
- Lifecycle owner：{创建、共享、关闭责任}
- Partial construction：{未完成构造时的所有权}

## 6. Invariants and dependency rules

| ID | Rule | Enforcement / Verification |
| --- | --- | --- |
| INV-01 | {始终成立的性质} | {04 契约、07 检查或人工评审} |

## 7. Quality drivers and risks

| Driver | Tactic | Sensitivity / Trade-off | Risk | Evidence |
| --- | --- | --- | --- | --- |
| {DR-XX} | {策略} | {敏感点与代价} | {风险} | {验证入口} |

## 8. Decisions and impact

- ADR：{06 中的决定或 Proposed 项}
- 变化影响：{需要检查的 03–08 内容}

写法说明见[02 Architecture 系列文章](../02_Architecture_边界职责与所有权.md)。
