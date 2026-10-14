"""C 侧图注/解读纪律：蒸馏自 nature-skills，不引入其绘图运行时。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

MISSING = "缺"

SOURCE = "Yuan1z0825/nature-skills (Apache-2.0), distilled for MassAgent Agent C"

KEGG_PLOT_TYPES = frozenset({"kegg_bubble", "kegg_dotplot", "kegg_barplot", "kegg_bar"})
KEGG_FILE_NAMES = ("kegg_compound_enrich.csv", "enrichment_results.csv")
ENRICHMENT_CLAIM_RE = re.compile(r"显著富集")

CAPTION_FOOTER_ZH = (
    "图注只陈述方案要求、文件计数与可核对统计；方案预期观察不是已证实结论。"
    "不得把分组分离或相关写成机制。"
)
CAPTION_FOOTER_EN = (
    "Caption states the plan, file counts, and checkable statistics only; "
    "planned observations are not confirmed findings. Separation or correlation is not mechanism."
)

# 图注「prompt」：C 图注是确定性拼接，但这份契约同时注入报告 LLM。
CAPTION_CONTRACT_PROMPT = """图注契约 + 统计清单：
1. 图件主张来自分析方案，不是已证实结论。
2. 必须写出文件来源（结果 CSV 文件名）。
3. 统计清单：比较对象、n、检验、阈值、误差线、多重校正；没有则写「缺」，禁止编造。
4. 火山图必须写 p / |log2FC| 阈值与 volcano_results.csv。
5. VIP 图必须写 VIP 阈值与 vip_scores.csv。
6. KEGG 缺表或空表：写「标缺」；禁止「显著富集」。
7. 分组分离、VIP 排序或相关不是生物学机制。
"""

INSIGHTS_EXTRA_RULES = """
7. 图件主张来自分析方案，不是已证实结论；key_findings 必须能指向输入中的文件计数或 CSV 数据支撑。
8. 不得把 PCA/PLS-DA 分离、VIP 排序或相关网络升级成生物学机制、因果或疾病/等级结论。
9. QC 是质控样本，不是第三个生物学处理；不得把 QC 当作处理组解释。
10. 统计字段（p、FDR、VIP 阈值、n、检验名）只能引用上下文已给出的值；没有则在 caveats 写「缺」，禁止编造。
11. 空富集表或 missing_data 图必须写标缺；若 kegg_status 为 missing/empty，全文禁止「显著富集」。
12. 遵守图注契约：每张 VIP/火山图的解读必须能对应文件名与阈值；不要改写统计清单里的「缺」。
"""

VISION_EXTRA_RULES = """
额外边界：
- 只描述可见簇、轴、图例、阈值线；不要读出图中没有的 p 值或 VIP。
- 可见分离不等于生物学机制，也不等于等级差异。
- QC 点若与生物学组同色或聚成一团，只能描述位置，不能写成第三个处理效应。
- 图中没有通路气泡/点图时，不要口述「显著富集」。
"""

_PLOT_EVIDENCE_ROLE = {
    "pca": "质量/整体分离（无监督）",
    "plsda": "监督分离与模型拟合",
    "volcano": "主证据（差异方向与显著性计数）",
    "vip_bar": "变量贡献（模型内排序，不是 p 值）",
    "heatmap_vip": "表达模式（核对分组色块）",
    "kegg_bubble": "通路富集（可缺）",
    "kegg_dotplot": "通路富集（可缺）",
    "kegg_barplot": "通路富集（可缺）",
    "network_topology": "分子网络结构",
    "plsda_permutation": "模型稳健性（置换，不是机制）",
}


def figure_claim_from_job(job: dict[str, Any]) -> str:
    """一句话图件主张，只取方案字段，不把预期观察写成结论。"""
    for key in ("purpose", "theme", "logic"):
        text = str(job.get(key) or "").strip()
        if text:
            return text
    panels = job.get("panels") or []
    if panels and isinstance(panels[0], dict):
        for key in ("rationale", "design"):
            text = str(panels[0].get(key) or "").strip()
            if text:
                return text
    return ""


def evidence_role_from_job(job: dict[str, Any]) -> str:
    panels = job.get("panels") or []
    if panels and isinstance(panels[0], dict):
        role = str(panels[0].get("rationale") or panels[0].get("role") or "").strip()
        if role:
            return role
    pt = str(job.get("plot_type") or "").strip()
    return _PLOT_EVIDENCE_ROLE.get(pt, "")


def caption_footer(*, zh: bool) -> str:
    return CAPTION_FOOTER_ZH if zh else CAPTION_FOOTER_EN


def _has_qc_groups(stats: dict[str, Any], bullets: list[str]) -> bool:
    groups = stats.get("groups") or {}
    if any("QC" in str(k).upper() for k in groups):
        return True
    blob = " ".join(str(b) for b in bullets)
    return "QC" in blob.upper()


def _uniq_names(*groups: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for group in groups:
        if group is None:
            continue
        if isinstance(group, (str, Path)):
            items = [group]
        else:
            items = list(group)
        for item in items:
            name = Path(str(item)).name.strip()
            if not name or name in seen:
                continue
            seen.add(name)
            out.append(name)
    return out


def source_file_names(
    job: dict[str, Any] | None = None,
    stats: dict[str, Any] | None = None,
) -> list[str]:
    job = job or {}
    stats = stats or {}
    return _uniq_names(
        job.get("source_files"),
        job.get("data_files"),
        stats.get("source_file"),
        stats.get("source_files"),
    )


def attach_reporting_checklist(plot_type: str, out: dict[str, Any]) -> None:
    """在 data_narrative 上补「图注统计」核对项；缺的写 缺，不编造。"""
    pt = str(plot_type or "").strip()
    stats = dict(out.get("stats") or {})
    bullets = list(out.get("bullets") or [])
    items: list[tuple[str, str]] = []

    def add(label: str, value: str) -> None:
        items.append((label, value))

    src = str(stats.get("source_file") or "").strip() or MISSING

    if pt in {"pca", "plsda"}:
        n = stats.get("n_samples")
        add("比较对象", "、".join(str(k) for k in (stats.get("groups") or {})) or MISSING)
        add("n", f"{n} 个样本点" if n is not None else MISSING)
        if _has_qc_groups(stats, bullets):
            add("独立单位", "样本点；QC 是质控，不是生物学处理")
        else:
            add("独立单位", "样本点（生物学重复 vs 技术重复未在表中区分则标缺）")
        add("检验", "无监督降维" if pt == "pca" else "监督降维（PLS-DA），不是 p 值检验")
        add("阈值", "不适用")
        add("误差线", "不适用")
        add("多重校正", "不适用")
        add("文件来源", src)
    elif pt == "volcano":
        n = stats.get("n_features")
        add("比较对象", str(stats.get("contrast") or MISSING))
        add("n", f"{n} 个特征" if n is not None else MISSING)
        add("独立单位", "特征，不是生物学重复")
        add("检验", str(stats.get("test_name") or MISSING))
        p_thr = stats.get("p_threshold")
        fc_thr = stats.get("log2fc_threshold")
        if p_thr is not None and fc_thr is not None:
            add("阈值", f"p<{p_thr} 且 |log2FC|≥{fc_thr}")
        elif stats.get("n_p_value_lt_0.05") is not None:
            add("阈值", "p<0.05（按列计数）")
        elif stats.get("n_significant") is not None:
            add("阈值", "Significant 列计数（阈值定义以结果表为准）")
        else:
            add("阈值", MISSING)
        add("误差线", "不适用")
        if stats.get("n_adj_p_value_lt_0.05") is not None:
            add("多重校正", "FDR/adj_p 列已计数")
        else:
            add("多重校正", MISSING)
        add("文件来源", src)
    elif pt == "vip_bar":
        n_high = stats.get("n_vip_above_threshold", stats.get("n_vip_gt1"))
        thr = stats.get("vip_threshold")
        add("比较对象", MISSING)
        if n_high is not None and thr is not None:
            add("n", f"VIP>{float(thr):g} 共 {n_high} 个")
        elif n_high is not None:
            add("n", f"VIP 超阈值共 {n_high} 个")
        else:
            add("n", MISSING)
        add("独立单位", "模型内特征，不是独立假设检验")
        add("检验", "PLS-DA VIP（变量投影）")
        if thr is not None:
            add("阈值", f"VIP>{float(thr):g}（计数与作图虚线同一阈值）")
        else:
            add("阈值", MISSING)
        add("误差线", "不适用")
        add("多重校正", "不适用")
        add("文件来源", src)
    elif pt == "heatmap_vip":
        add("比较对象", "、".join(str(k) for k in (stats.get("groups") or {})) or MISSING)
        n_row = stats.get("n_rows")
        n_col = stats.get("n_cols")
        if n_row is not None and n_col is not None:
            add("n", f"{n_row}×{n_col}")
        else:
            add("n", MISSING)
        add("检验", "表达矩阵展示（不是新的假设检验）")
        add("阈值", str(stats.get("vip_threshold") or MISSING))
        add("误差线", "不适用")
        add("多重校正", "不适用")
        add("文件来源", src)
    elif pt in KEGG_PLOT_TYPES:
        add("比较对象", MISSING)
        add("n", MISSING if not bullets else "见上表行数")
        add("独立单位", "通路条目")
        add("检验", MISSING)
        add("阈值", MISSING)
        add("误差线", "不适用")
        add("多重校正", MISSING)
        add("文件来源", src)
        empty = any("共 **0**" in str(b) or "共 0 " in str(b) for b in bullets)
        missing = stats.get("kegg_status") in {"missing", "empty"} or empty or not bullets
        if missing:
            add("富集结论", "标缺（未产出可核对通路表，不写成富集阳性）")
    elif pt:
        add("比较对象", MISSING)
        add("n", MISSING if stats.get("n_samples") is None and stats.get("n_features") is None else "见表内计数")
        add("检验", MISSING)
        add("阈值", MISSING)
        add("文件来源", src)

    if not items:
        return
    line = "图注统计：" + "；".join(f"{k}：{v}" for k, v in items) + "。"
    out.setdefault("bullets", []).append(line)
    out.setdefault("stats", {})["reporting_checklist"] = {k: v for k, v in items}


def caption_contract_and_stats(
    job: dict[str, Any],
    facts: list[str],
    *,
    zh: bool,
    data_narrative: dict[str, Any] | None = None,
) -> list[str]:
    """图注后半段：文件来源 + 统计清单（可与 facts 中的计数并存）。"""
    parts: list[str] = []
    stats = dict((data_narrative or {}).get("stats") or {})
    names = source_file_names(job, stats)
    fact_blob = "；".join(str(x) for x in facts)
    if names:
        joined = "、".join(f"`{n}`" for n in names)
        label = "文件来源：" if zh else "Source files: "
        if "文件来源" not in fact_blob and "Source files" not in fact_blob:
            parts.append(label + joined)
    checklist = stats.get("reporting_checklist")
    if isinstance(checklist, dict) and checklist:
        blob = "；".join(f"{k}：{v}" for k, v in checklist.items())
        parts.append(("统计清单：" if zh else "Stats checklist: ") + blob + "。")
    pt = str(job.get("plot_type") or "")
    if pt in KEGG_PLOT_TYPES and str(job.get("status") or "") in {
        "missing_data",
        "missing_metadata",
        "unsupported",
    }:
        parts.append(
            "KEGG：标缺。未产出通路表，不写成富集阳性。"
            if zh
            else "KEGG: missing; no enrichment claim."
        )
    return parts


def insights_system_prompt(base: str) -> str:
    return (
        base.rstrip()
        + "\n"
        + INSIGHTS_EXTRA_RULES.strip()
        + "\n\n"
        + CAPTION_CONTRACT_PROMPT.strip()
        + "\n"
    )


def vision_system_prompt(base: str) -> str:
    return base.rstrip() + "\n" + VISION_EXTRA_RULES.strip() + "\n"


def _inventory_has_kegg_file(inventory: dict[str, Any] | None) -> bool:
    inv = inventory or {}
    std = inv.get("standard_files") or {}
    if std.get("enrichment_results.csv"):
        return True
    names: set[str] = set()
    for item in inv.get("files") or []:
        if not isinstance(item, dict):
            continue
        names.add(str(item.get("name") or ""))
        names.add(Path(str(item.get("rel") or "")).name)
    if any(name in names for name in KEGG_FILE_NAMES):
        return True
    for item in inv.get("plottable") or []:
        if not isinstance(item, dict):
            continue
        for fname in item.get("data_files") or []:
            if Path(str(fname)).name in KEGG_FILE_NAMES:
                return True
    return False


def _plan_wants_kegg(plan: dict[str, Any] | None, figures: list[dict[str, Any]] | None) -> bool:
    for fig in (plan or {}).get("required_visualization") or []:
        if not isinstance(fig, dict):
            continue
        if str(fig.get("plot_type") or "") in KEGG_PLOT_TYPES:
            return True
        blob = " ".join(str(fig.get(k) or "") for k in ("title", "theme", "purpose"))
        if re.search(r"kegg|通路富集", blob, re.I):
            return True
    tools = str((plan or {}).get("tools_required") or "")
    if re.search(r"kegg", tools, re.I):
        return True
    for step in (plan or {}).get("workflow") or []:
        blob = str(step) if not isinstance(step, dict) else " ".join(str(v) for v in step.values())
        if re.search(r"kegg", blob, re.I):
            return True
    for fig in figures or []:
        if str(fig.get("plot_type") or "") in KEGG_PLOT_TYPES:
            return True
    return False


def resolve_kegg_status(
    *,
    plan: dict[str, Any] | None = None,
    inventory: dict[str, Any] | None = None,
    figures: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """KEGG 是否有可核对结果表。缺/空则不允许富集阳性表述。"""
    has_file = _inventory_has_kegg_file(inventory)
    wanted = _plan_wants_kegg(plan, figures)
    empty = False
    missing_fig = False
    for fig in figures or []:
        pt = str(fig.get("plot_type") or "")
        if pt not in KEGG_PLOT_TYPES:
            continue
        if str(fig.get("status") or "") in {"missing_data", "missing_metadata"}:
            missing_fig = True
        narr = fig.get("data_narrative") or {}
        stats = narr.get("stats") or {}
        if stats.get("kegg_status") in {"missing", "empty"}:
            empty = True
        bullets = " ".join(str(b) for b in (narr.get("bullets") or []))
        if "共 **0**" in bullets or "共 0 " in bullets:
            empty = True
    if not has_file or missing_fig:
        reason = "未找到 kegg_compound_enrich.csv"
        if missing_fig and wanted:
            reason = "方案需要 KEGG 图，但结果目录没有对应表"
        return {
            "status": "missing",
            "wanted": wanted,
            "allow_enrichment_claim": False,
            "reason": reason,
            "label": "标缺",
        }
    if empty:
        return {
            "status": "empty",
            "wanted": wanted,
            "allow_enrichment_claim": False,
            "reason": "KEGG 表为空",
            "label": "标缺",
        }
    return {
        "status": "present",
        "wanted": wanted,
        "allow_enrichment_claim": True,
        "reason": "",
        "label": "有表",
    }


def kegg_gap_markdown(status: dict[str, Any] | None, *, zh: bool = True) -> str:
    if not status or status.get("allow_enrichment_claim"):
        return ""
    reason = str(status.get("reason") or "").strip()
    if zh:
        extra = f"（{reason}）" if reason else ""
        return (
            "### 通路富集（KEGG）\n\n"
            f"KEGG：**标缺**{extra}。"
            "本报告不把未产出的通路结果写成富集阳性。"
        )
    extra = f" ({reason})" if reason else ""
    return (
        "### Pathway enrichment (KEGG)\n\n"
        f"KEGG: **missing**{extra}. No positive enrichment claim is made."
    )


def strip_false_enrichment_claims(text: str, *, kegg_missing: bool) -> str:
    if not kegg_missing or not text:
        return text
    return ENRICHMENT_CLAIM_RE.sub("通路结果标缺", text)


def apply_enrichment_claim_guard(payload: Any, *, kegg_missing: bool) -> Any:
    if not kegg_missing:
        return payload
    if isinstance(payload, str):
        return strip_false_enrichment_claims(payload, kegg_missing=True)
    if isinstance(payload, list):
        return [apply_enrichment_claim_guard(x, kegg_missing=True) for x in payload]
    if isinstance(payload, dict):
        return {k: apply_enrichment_claim_guard(v, kegg_missing=True) for k, v in payload.items()}
    return payload


def insights_user_prompt_suffix(kegg: dict[str, Any] | None, *, zh: bool = True) -> str:
    status = kegg or {}
    if status.get("allow_enrichment_claim"):
        extra = (
            "KEGG 有结果表，可引用行数与列内阈值；不要升级成机制。"
            if zh
            else "KEGG table is present; cite row counts only."
        )
        return "\n\n【图注契约 / 统计清单】\n" + CAPTION_CONTRACT_PROMPT + "\n【KEGG】" + extra + "\n"
    reason = str(status.get("reason") or "未找到 kegg_compound_enrich.csv")
    if zh:
        kegg_line = f"kegg_status=missing；{reason}。必须写标缺。禁止输出「显著富集」。"
    else:
        kegg_line = (
            f"kegg_status=missing ({reason}). Mark as missing. "
            "Do not claim significant enrichment."
        )
    return "\n\n【图注契约 / 统计清单】\n" + CAPTION_CONTRACT_PROMPT + "\n【KEGG】" + kegg_line + "\n"


__all__ = [
    "CAPTION_CONTRACT_PROMPT",
    "KEGG_PLOT_TYPES",
    "MISSING",
    "SOURCE",
    "apply_enrichment_claim_guard",
    "attach_reporting_checklist",
    "caption_contract_and_stats",
    "caption_footer",
    "evidence_role_from_job",
    "figure_claim_from_job",
    "insights_system_prompt",
    "insights_user_prompt_suffix",
    "kegg_gap_markdown",
    "resolve_kegg_status",
    "source_file_names",
    "strip_false_enrichment_claims",
    "vision_system_prompt",
]
