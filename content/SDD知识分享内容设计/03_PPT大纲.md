# 《小白如何用 SDD 与 AI 开发软件》Marp 演示大纲

状态：双主线 Marp 制作基线  
画布：16:9  
主讲：16 页，约 20～25 分钟  
附录：2 页

## 产物与技术边界

- 使用 Marp Markdown 作为内容和版式事实源，独立主题 CSS 控制字体、颜色、间距和层级。
- Mermaid 图保留 `.mmd` 源文件，生成本地 SVG 后嵌入 Marp，不依赖演示现场的远程服务。
- 同时导出 PDF 和普通 PPTX。Markdown、CSS 和 Mermaid 可维护；PPTX 只作为分发副本。
- 不启用实验性的 editable PPTX 导出。
- 制作时固定 Marp 与 Mermaid 版本，并在导出前核对各自官方说明。

## 视觉与叙事规则

- 全部使用纯色背景，不使用背景图片、装饰插图、渐变、纹理、代码、终端或真实产品界面。
- 暖白为主背景，深灰正文，单一蓝色强调；封面可以使用纯蓝背景。
- 使用本机可稳定渲染中文的无衬线字体，不依赖远程字体。
- 封面标题约 42pt，页面标题不低于 32pt，正文原则上不低于 18pt。
- 每页只推进一个主要判断，减少卡片、标签、页脚碎片和重复说明。
- 页面在不看讲者备注时也能理解主要结论；备注只补充解释、转场和来源。
- 个人助理只出现在第 2 页，第 3～18 页不再引用该场景。
- 七步活动与 `01–09` 信息地图同时出现，但不画成一一对应或线性瀑布；总览由入口内容承担，不另设编号。

演示统一使用以下七步名称，不在页面制作时另造一套流程：

1. 明确目标与验收。
2. 核实当前状态。
3. 设计必要边界。
4. 确定关键决定。
5. 推导最小增量。
6. 实施并处理变化。
7. 验证并同步。

## 主讲页面

1. **小白如何用 SDD 与 AI 开发软件**  
   结论：先让目标、设计、任务和证据互相对应。纯蓝封面，保留标题、副标题和讲者信息位置。

2. **一句愿景缺少哪些中间判断**  
   使用一次独立构造的虚构个人助理愿景。列出缺失的目标、当前事实、边界、状态、失败和完成证据；页内明确“场景到此结束”。

3. **人的活动与 `01–09` 是两条主线**  
   嵌入 Mermaid 图 1：上层为七步活动，下层为 `01–07`、`08`、`09` 三个信息区域；显示读取、写入和反馈回退。主结论是“活动产生信息，文档保存当前有效信息”。

4. **目标与验收怎样写入 `01/07`**  
   左侧用 Goal、Non-goal、SC 说明人判断什么；右侧用 `01` 与初步 `07` 说明写入位置；底部给退出门槛。

5. **Current Facts 怎样写入 `08`**  
   区分 `01` 的相对稳定问题基线和 `08` 的滚动 Current Facts。展示 Evidence → Current State → Gap，不把旧文档和提案写成事实。

6. **Architecture Baseline 分布在 `02–05`**  
   四行可编辑表格：`02` 静态边界与 owner、`03` 运行与状态、`04` 交互契约、`05` 失败与恢复。说明文档深度随风险调整。

7. **System Boundary、Ownership、Runtime 与 State**  
   说明边界内外、唯一状态 owner、生命周期 owner、事件权限和非法转移。首次提 C4，仅说明按沟通目的选择有用视图。

8. **Contracts、Failures、ADR 与 Verification**  
   从可依赖交互到失败最终状态，再到关键取舍与证明方式。首次提 ADR、mini-ATAM、QAS 和 Fitness Functions；`06` 标记为跨阶段位置。

9. **`01–09` 权威信息地图**  
   使用可编辑表格列出九个位置的 Owns 与 Update trigger。强调总览由本演示承担，`08` 不复制完整 Spec，`09` 不覆盖权威文档。文档组织处按需提 arc42。

10. **从 SC 到实际证据**  
    嵌入 Mermaid 图 2：`SC → 设计约束 → TEST → TASK References → 实际证据 → Review/定向回写`。用 `Draft / Accepted / Propagated / Implemented / Verified` 区分状态。

11. **Gap 决定下一项 Vertical Slice**  
    展示 `Current State → Target → Gap → Smallest Delta → Evidence`。Task 只交付一个主要结果，并引用 `01–07` 的具体条目。此处按需提 GitHub Spec Kit 作为外部任务组织参考。

12. **Task Contract 限定 AI 的工作空间**  
    显示 Goal、References、Preconditions、Allowed scope、Must、Must not、Verify、Design Delta、Handoff。强调 References 是引用，不是重抄设计。

13. **Preflight 与 Human Review 决定能否实施**  
    左侧 Preflight Brief：基线、计划变化、目标区域、约束、阻塞、Readiness；右侧 Human Review：关键证据抽查、裁决和 GO/Conditional GO/NO-GO。

14. **Implementation 遇到新证据时怎样处理**  
    嵌入 Mermaid 图 3：局部实现问题留在 Task；事实变化刷新 Current Facts；已接受 Spec 冲突形成 Design Delta，经 Human Review 回到拥有信息的文档。外部动作无明确结果时保留 Unknown Result。

15. **Completion Report 不是一句“已完成”**  
    展示 Implemented、Files changed、Tests、Boundary checks、Design Deltas、Remaining risks、Result、Write-back。说明计划、实际证据和完成结论不能互相替代。

16. **反馈定向回写，下一次从新事实开始**  
    收束为三步：刷新拥有信息的文档 → 传播到 `07/08` → 选择下一项 Gap。不给出口号式承诺，不回到个人助理场景。

## 附录

17. **七步活动与文档写回完整矩阵**  
    一页可编辑表格，列出每步的判断问题、主要写入、同步检查与退出门槛，供会后独立查阅。

18. **空白 Task、Preflight 与 Completion 工作底稿**  
    三栏或上下分区展示可复制字段。Human Review 作为独立记录提示，不塞进 Task 正文。

## Mermaid 图定义

1. **双主线总图**：少节点、少交叉线；表达七步活动怎样读写三个信息区域以及反馈可回退。
2. **Spec 到证据的追踪链**：表达 SC、设计约束、TEST、TASK、实际证据和 Review 的连续关系。
3. **Design Delta 与反馈回写循环**：区分局部实现、事实变化、Spec 冲突及其不同去向。

图中不塞入 `01–09` 的完整知识清单；完整职责使用可编辑表格承载。

## 讲者备注原则

- 每页备注约 80～150 个中文字，说明该页判断、必要来源和自然转场。
- 不把页面缺失的核心结论藏在备注中。
- 第 2 页明确结束虚构场景，后续备注不得继续引用。
- 不写制作过程、本机路径、聊天标识、内部资料名称或验证日志。
- 对计划中的演示产物使用“将、预期、待验证”；只有导出和渲染后才能记录实际结果。

## 交付检查

- 总页数为 18，前 16 页进入主讲计时。
- 双主线图、追踪链和 Design Delta 回写循环各有一份 `.mmd` 与本地 SVG。
- 七步与 `01–09` 没有画成一一对应或瀑布流程。
- `01/08`、`06`、`09` 三组易混关系均得到明确说明。
- 五种状态、Unknown Result、Test Plan 与实际证据没有混用。
- 所有页面为纯色背景，不存在图片装饰、文字溢出、过小字号或图线穿过标签。
- Markdown、CSS 和 Mermaid 可以重新生成 PDF 与普通 PPTX；导出结果需逐页渲染检查。
- 标题、术语、七步、信息归属和工作底稿字段与博客完全一致。
