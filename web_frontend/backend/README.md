# `web_frontend/backend` 区块

总图见上一级 [`LAYOUT.md`](../LAYOUT.md)。这里只标「打开哪个包」。

| 区块 | 目录 / 入口 | 不要放进去的东西 |
|------|-------------|------------------|
| 编排 | `webapp.py` `workflow.py` `abc_contract.py` `agent_backends.py` | 分析工具实现 |
| A | `agent_a/` | MCP 调用、最终报告 |
| B | `agent_b/` | 规划、出图 |
| C | `agent_c/` | XCMS / mixOmics / 任何计算工具 |
| 本地 B 回退 | 根上 `xcms_*.py` `mixomics_runner.py` `tool_runner.py` | 默认 massomics 路径不会走到这里 |
| 改图/拼图 | `plot_edit_*.py` `image_merge_*.py` `visual_*.py` | 仅会话完成后 |

A/B 的 **complete 代码根**由 `agent_backends.complete_abc_root()` 探测，默认 `MassOmics-Agent-B`。
