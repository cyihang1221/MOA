# nature_distill（C 侧图注 / 结果叙述纪律）

从 [Yuan1z0825/nature-skills](https://github.com/Yuan1z0825/nature-skills)（Apache-2.0）蒸馏出的**短规则**，供质谱智能体 Agent C 使用。

**不是**把该仓库装进运行时，也**不**让 LLM 现写 matplotlib 脚本。渲染仍走 `PLOT_SPECS` + Vega/茶叶 matplotlib。

本包约束：

1. 图是视觉论证：先有方案主张，再陈述文件事实。
2. 图注统计可核对：比较对象、`n`、检验、阈值、误差线、多重校正、文件来源；没有就写「缺」。
3. 火山图写出 `p` / `|log2FC|` 与 `volcano_results.csv`；VIP 写出 `VIP>1` 与 `vip_scores.csv`。
4. 结果叙述不升级：分组分离 / VIP / 相关 ≠ 机制；QC ≠ 生物学处理。
5. 缺 KEGG 表：报告写**标缺**，不把未产出通路写成富集阳性。
6. 投稿导出（仅 PCA / 火山 / VIP / 热图的 matplotlib 终稿）：600 dpi PNG + PDF 矢量 + 字号检查。对齐/碰撞审计要等 matplotlib 几何门，不在 Vega 预览上做。
   端到端：`python -m unittest web_frontend.backend.agent_c.test_journal_export_e2e`；本机会话示例产出 `outputspace/…_60aca071/agent_c_output_journal_e2e/`。

对应上游文件（只作来源说明，不随仓库同步全文）：

- `skills/nature-figure/static/core/contract.md`
- `skills/nature-statistics/SKILL.md` 与 `references/figure-statistics.md`
- `skills/nature-writing` 的 Results 边界（claim 不超过证据）
