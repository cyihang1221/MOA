# 新文献 → 参数级 Skill 流水线

把 **PubMed / Europe PMC / OpenAlex** 等开放接口上的文章检索出来，**筛选**后抽成与 `repro_recipes` 同格式的配方（含软件参数），再构建 Skill。

> 不做 Sci-Hub、不破解付费站。OpenAlex 对应「科学文献/SCI 元数据」开放检索。

## 推荐入口（师兄流程：爬取 → 筛选 → Skill）

```bash
# 使用 MOA 环境
/home/chenyihang/miniconda3/envs/MOA/bin/python \
  scripts/paper_skill_pipeline/crawl_filter_build.py --dry-run

# 完整：检索+筛选+抽 recipe+建 Skill
/home/chenyihang/miniconda3/envs/MOA/bin/python \
  scripts/paper_skill_pipeline/crawl_filter_build.py \
  --sources pubmed,europe_pmc,openalex \
  --max-per-source 8 --top-k 3 --mindate 2022 \
  --build-skills
```

### 步骤说明

| 步骤 | 模块 | 做什么 |
|------|------|--------|
| 1 检索 | `search_sources.py` | PubMed / Europe PMC / OpenAlex 并行检索并去重 |
| 2 筛选 | `filter_literature.py` | 按 PMC、工具词、参数线索、期刊、引用等打分，取 top-k |
| 3 下载 Methods | `fetch_papers.py` | PMC HTML → Methods；再按数值参数密度二次筛选 |
| 4 抽 recipe | `extract_recipe.py` | LLM → `parameters: key=value` 级配方 |
| 5 建 Skill | `skill_builder` | `--build-skills` 时刷新 `phase2_output/` |

筛选报告：`softwares_database/paper_fetch_cache/crawl_reports/last_crawl_selection.json`

## 单篇 / 旧入口

```bash
python scripts/paper_skill_pipeline/run_pipeline.py --doi 10.xxxx/yyyy --build-skills
python scripts/paper_skill_pipeline/run_pipeline.py --pmid 38294426
```

## 流程总览

```
queries / DOI / PMID
   │
   ├─ PubMed ──┐
   ├─ Europe PMC ├─→ merge/dedupe → meta filter → PMC Methods
   └─ OpenAlex ─┘         │              │
                          │              ▼
                          │     methods richness filter
                          │              │
                          ▼              ▼
                    crawl report     LLM recipe → repro_recipes
                                              │
                                              ▼
                                       skill_builder
```

## 依赖与环境变量

- `LLM_*`：抽取 recipe 必需
- 可选：`NCBI_EMAIL`、`NCBI_API_KEY`、`OPENALEX_EMAIL`（礼貌限流）

## 局限

- 默认需要 **PMC / OA 全文**；付费全文请用 `--methods-file`
- 「参数详细」靠启发式 + LLM，**建议人工抽查** top 结果
- 已有 `recipe_*.txt` 默认不覆盖（`--overwrite`）

## 依赖

- `.env` 中已有：`LLM_MODEL_ID` / `LLM_API_KEY` / `LLM_BASE_URL`
- 可选：`NCBI_EMAIL`、`NCBI_API_KEY`（提高 NCBI eutils 配额、降低限流）
- Python 包：`requests`、`beautifulsoup4`、`python-dotenv`、`openai`

## 用法

```bash
# 1) 按 DOI（须有 PMC 开放全文）
python scripts/paper_skill_pipeline/run_pipeline.py \
  --doi 10.1038/s41592-025-02813-0 --build-skills

# 2) 按 PMID
python scripts/paper_skill_pipeline/run_pipeline.py --pmid 38294426

# 3) 检索新文（推荐）
python scripts/paper_skill_pipeline/run_pipeline.py \
  --query "XCMS AND untargeted metabolomics" \
  --max-papers 3 --mindate 2024 --build-skills

# 4) 已有 Methods 文本（无 PMC 也可）
python scripts/paper_skill_pipeline/run_pipeline.py \
  --methods-file /path/to/methods.txt \
  --title "Paper title" --doi 10.xxxx/yyyy --build-skills

# 5) 只抓 Methods，不调用 LLM
python scripts/paper_skill_pipeline/run_pipeline.py --doi 10.xxxx/yyyy --skip-llm
```

## 输出位置

| 路径 | 内容 |
|------|------|
| `softwares_database/paper_fetch_cache/html/` | PMC HTML 缓存 |
| `softwares_database/paper_fetch_cache/methods/` | Methods 纯文本 |
| `softwares_database/paper_fetch_cache/recipes_json/` | 结构化 JSON |
| `softwares_database/repro_recipes/recipe_*.txt` | 与旧语料同 schema 的配方 |

## 参数抽取约定

LLM 被要求：

- `parameters` 写成 `key=value, key2=value2`（如 `ppm=5, peakwidth=[10,60]`）
- **禁止编造**文中未出现的数值参数；缺失写 `not_reported`
- 几乎无显式参数却打高分时，脚本会把分数压到 ≤55

## 局限

- 默认依赖 **PMC 开放全文**；付费墙 PDF 需自行导出 Methods 后用 `--methods-file`
- 图注若不在 Methods 段，figure 字段可能偏推断，以 `statistical_test` / `visualization_tool` 是否 `not_reported` 为准
- 与旧版 `paper_method_extractor_V3.py` 的区别：V3 产出自然语言配置摘要；本流水线产出 **可复现 recipe + Skill**
- 已存在的 `recipe_*.txt` **默认不覆盖**，需显式 `--overwrite`

## 与 skill_builder 的关系

```bash
# 仅重建 Skill（含新写入的 recipe）
python scripts/skill_builder/build_skills.py --min-score 80
```
