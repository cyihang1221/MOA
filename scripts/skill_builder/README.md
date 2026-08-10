# Skill Builder：从文献配方提取可注入 Skill

从 `softwares_database/repro_recipes/` 解析高可复现度、含**显式软件参数**的配方，生成：

- `phase2_output/skill_registry.json` — CLI Agent / Web Agent 共用注册表
- `phase2_output/paper_skills/*.md` — 单篇文献 Skill（Pipeline + Parameters + Figures）
- `phase2_output/skills/consensus_*.md` — 多篇共识（工具偏好 + 参数频次）

## 一键构建

在项目根目录：

```bash
python scripts/skill_builder/build_skills.py
```

常用参数：

| 参数 | 默认 | 说明 |
|------|------|------|
| `--min-score` | 80 | `overall_reproducibility_score` 下限 |
| `--require-params` | 开 | 必须含 `parameters:` 字段 |
| `--max-paper-skills` | 25 | 单篇 Skill 数量上限 |
| `--min-consensus-papers` | 5 | 场景共识最少文献数 |

示例：只保留更高质量单篇：

```bash
python scripts/skill_builder/build_skills.py --min-score 85 --max-paper-skills 15
```

## Skill 内容结构

单篇 Skill 重点字段：

1. **Analysis Goal** — 文献研究目的
2. **Pipeline Coverage** — 步骤 / 工具 / 算法 / **parameters**（如 `ppm=5, peakwidth=[10,60]`）
3. **Expected Figures** — 目的→图→统计检验/可视化工具
4. **Parameter Highlights** — 参数摘要，便于 Agent 映射

共识 Skill 聚合多篇：`Tool Preference Order` + `Parameter Consensus`。

## Agent 如何使用

| 入口 | 行为 |
|------|------|
| `src/agent.py` `_match_skill` | 读 `phase2_output/skill_registry.json`，按 `trigger_keywords` 注入 plan |
| Web `agent_runner` | `skill_match.match_skills` → `skill_context` 注入计划/工具匹配 prompt |

优先级（Web）：**用户指令 > skill_context > literature_context > 默认流程**。

关闭 Web Skill 注入：`WEB_SKILL_MATCH=0`

## 数据来源说明

- 原料：`softwares_database/repro_recipes/recipe_*.txt`（约 2000+ 条）
- 筛选：`score>=80` 且含显式 `parameters:`（约 148 条可参与）
- **抓取新文章并抽参数级 recipe**：见 `scripts/paper_skill_pipeline/`（PubMed/PMC → Methods → LLM recipe → 可选 `--build-skills`）

## 文件一览

```
scripts/skill_builder/
  parse_recipes.py   # 解析 recipe 文本
  render_skills.py   # 渲染 Markdown Skill
  build_skills.py    # CLI 入口
phase2_output/
  skill_registry.json
  paper_skills/
  skills/
```
