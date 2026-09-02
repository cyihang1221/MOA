"""PLOT_SPECS 语义数据契约：每个 plot_type 必须声明 CSV 从哪来。

C 只消费文件、不保证 B 写出。本表用来发现「注册了但没人写」：
- ``b_tool``：Agent B 工具直接写出（含同型异名）
- ``derived``：C 从 B 已有上游表现算（不要求 B 改）
- ``paper_or_upload``：论文复现 / 用户上传，质谱流水线不会产出
- ``mixed``：既有 B 产物也有论文表（例如置换检验）
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlotDataContract:
    plot_type: str
    source: str
    producers: tuple[str, ...]
    notes: str = ""


PLOT_DATA_CONTRACT: tuple[PlotDataContract, ...] = (
    PlotDataContract("pca", "b_tool", ("statistical_analysis_mixomics", "statistical_analysis_metax")),
    PlotDataContract("plsda", "b_tool", ("statistical_analysis_mixomics",)),
    PlotDataContract(
        "volcano",
        "b_tool",
        (
            "statistical_analysis_mixomics",
            "statistical_analysis_metax",
            "statistical_analysis_sklearn",
            "statistical_analysis_metaboanalyst",
            "statistical_analysis_simca",
        ),
        "变体表走列名归一（log2fc→log2FC）",
    ),
    PlotDataContract(
        "vip_bar",
        "b_tool",
        ("statistical_analysis_mixomics", "statistical_analysis_simca", "statistical_analysis_metaboanalyst"),
    ),
    PlotDataContract("heatmap_vip", "b_tool", ("statistical_analysis_mixomics",)),
    PlotDataContract("family_size", "b_tool", ("molecular_networking_fbmn", "molecular_networking_gnps")),
    PlotDataContract("degree_hist", "b_tool", ("molecular_networking_fbmn", "molecular_networking_gnps")),
    PlotDataContract("cosine_hist", "b_tool", ("molecular_networking_fbmn", "molecular_networking_gnps")),
    PlotDataContract(
        "network_topology",
        "derived",
        ("molecular_networking_fbmn", "molecular_networking_gnps"),
        "B 不写 network_layout.csv，C 从节点/边表现算 spring_layout",
    ),
    PlotDataContract("precursor_mass_diff", "b_tool", ("molecular_networking_fbmn",)),
    PlotDataContract("pearson_hist", "b_tool", ("molecular_networking_fbmn",)),
    PlotDataContract("mass2motif_overview", "b_tool", ("molecular_networking_ms2lda",)),
    PlotDataContract("mass2motif_fragments", "b_tool", ("molecular_networking_ms2lda",)),
    PlotDataContract("motif_spectrum_heatmap", "b_tool", ("molecular_networking_ms2lda",)),
    PlotDataContract("chemical_class_distribution", "b_tool", ("molnetenhancer",)),
    PlotDataContract("family_chemical_consensus", "b_tool", ("molnetenhancer",)),
    PlotDataContract("annotation_propagation", "b_tool", ("molnetenhancer",)),
    PlotDataContract("kegg_bubble", "b_tool", ("kegg_compound_enrichment",)),
    PlotDataContract("kegg_dotplot", "b_tool", ("kegg_compound_enrichment",)),
    PlotDataContract("kegg_barplot", "b_tool", ("kegg_compound_enrichment",)),
    PlotDataContract(
        "fbmn_group_intensity",
        "derived",
        ("molecular_networking_fbmn",),
        "B 不写聚合表，C 从 fbmn_nodes.csv 的 mean_<group> 列按家族聚合",
    ),
    PlotDataContract(
        "mass2motif_network",
        "derived",
        ("molecular_networking_ms2lda",),
        "B 不写二部图表，C 从 spectra_motif_scores.csv 派生",
    ),
    PlotDataContract(
        "constituent_bar",
        "paper_or_upload",
        ("agent_c.fixtures.duyun_maojian",),
        "TPC/TFC/TFAA 湿实验，质谱流水线不会写 tea_constituents.csv",
    ),
    PlotDataContract(
        "relative_abundance_heatmap",
        "paper_or_upload",
        ("agent_c.fixtures.duyun_maojian",),
        "两个丰度表互为备选（data_mode=any），不与 mixomics VIP 热图混用",
    ),
    PlotDataContract(
        "hca_heatmap",
        "paper_or_upload",
        ("agent_c.fixtures.duyun_maojian",),
        "hca_matrix.csv 由论文复现提供；不用 heatmap_top_vip_matrix 冒充",
    ),
    PlotDataContract(
        "correlation_heatmap",
        "paper_or_upload",
        ("agent_c.fixtures.duyun_maojian",),
    ),
    PlotDataContract(
        "bioactivity_bar",
        "paper_or_upload",
        ("agent_c.fixtures.duyun_maojian",),
    ),
    PlotDataContract(
        "sensory_scores",
        "paper_or_upload",
        ("agent_c.fixtures.duyun_maojian",),
    ),
    PlotDataContract(
        "plsda_permutation",
        "mixed",
        ("statistical_analysis_simca", "agent_c.fixtures.duyun_maojian"),
        "SIMCA permMN 与论文 permutation/R2/Q2 表共用渲染器，列名归一",
    ),
    PlotDataContract("splot", "b_tool", ("statistical_analysis_simca",)),
    PlotDataContract("opls_outlier", "b_tool", ("statistical_analysis_simca",)),
    PlotDataContract("roc_auc_hist", "b_tool", ("statistical_analysis_metax",)),
    PlotDataContract("significance_venn", "b_tool", ("statistical_analysis_metax",)),
    PlotDataContract("log2fc_hist", "b_tool", ("statistical_analysis_metax",)),
)

# B 会出 PNG、但没有对应语义 CSV，因此不进 PLOT_SPECS（只能通用改标题）。
UNREGISTERED_B_PNGS: tuple[tuple[str, str], ...] = (
    ("statistical_analysis_simca_hotelling_t2.png", "T² 只进图、未写 CSV"),
    ("statistical_analysis_simca_score_plot.png", "无标准 plsda_scores.csv"),
    ("statistical_analysis_metax_plsda_plot.png", "无 plsda_scores.csv"),
    ("statistical_analysis_metaboanalyst_pca_plot.png", "无 pca_scores.csv"),
    ("statistical_analysis_metaboanalyst_plsda_plot.png", "无 plsda_scores.csv"),
    ("statistical_analysis_metaboanalyst_heatmap.png", "无矩阵 CSV"),
    ("statistical_analysis_sklearn_pca_plsda.png", "PCA/PLS-DA 合图，无分表"),
    ("statistical_analysis_dl_confusion_matrix.png", "有 predictions.csv 但未注册图型"),
    ("molecular_network_dashboard.png", "2×2 拼图，不做语义重绘"),
)

# 论文/上传专用文件：禁止把 mixomics 矩阵挂成别名，避免 inventory 误出茶叶图。
PAPER_ONLY_FILES: frozenset[str] = frozenset(
    {
        "tea_constituents.csv",
        "bioactivity_assays.csv",
        "sensory_scores.csv",
        "correlation_matrix.csv",
        "hca_matrix.csv",
        "differential_metabolites_abundance.csv",
        "volatile_differential_abundance.csv",
    }
)


def contract_by_plot_type() -> dict[str, PlotDataContract]:
    return {item.plot_type: item for item in PLOT_DATA_CONTRACT}
