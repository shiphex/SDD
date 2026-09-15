# Human Review：{评审对象}

Review type：Problem / Design / Task Preflight / Design Delta / Completion  
Reviewer：{角色或姓名；公开材料使用非识别性角色}  
Baseline：{适用版本、报告或 Spec 状态}  
Review status：Draft / Accepted / Rejected / Conditional / Needs Evidence

## 1. Objective

{本次评审要决定什么；不决定什么。}

## 2. Evidence spot checks

| Claim | Evidence checked | Result | Limitation |
| --- | --- | --- | --- |
| {关键事实} | {版本/路径/测试/观察} | Confirmed / Rejected / Unknown | {适用边界} |

## 3. Decision cards

### DD-{编号}：{问题名称}

- Conflict：{哪条目标、设计或事实发生冲突}
- Options：{可行选项及条件}
- Decision：Accept / Reject / Explicitly Deferred / Needs Evidence
- Why：{基于证据和 Driver 的理由}
- Trade-off：{接受的代价}
- Reversibility：{高/中/低及回退方式}
- Blast radius：{受影响范围}
- Verification：{怎样确认决定有效}

## 4. Adjudication summary

- Accepted：{条目}
- Rejected：{条目与原因}
- Deferred：{条目、重审条件、受阻工作}
- Needs Evidence：{限定调查范围}

## 5. Go / No-go

- Result：GO / Conditional GO / NO-GO
- Allowed next scope：{允许继续的具体工作}
- Conditions：{必须先满足的条件}
- Blocked scope：{不得继续的工作}

## 6. Propagation plan

| Decision | Target `01–08` | Required update | Owner | Status |
| --- | --- | --- | --- | --- |
| {DD-XX} | {文档与条目} | {变化} | {责任方} | Pending / Propagated |

## 7. Completion distinction

- Current lifecycle status：Draft / Accepted / Propagated / Implemented / Verified
- Accepted decision：Yes / No
- Propagated specification：Yes / No / N/A
- Implemented change：Yes / No / N/A
- Verified evidence：Yes / No / N/A

使用说明见[09 Feedback、Human Review 与思维内化](../09_Feedback_Human_Review与思维内化.md)。
