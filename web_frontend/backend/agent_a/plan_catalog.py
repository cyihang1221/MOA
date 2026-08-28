"""从已注册工具/图型推断计划八要素的补充字段。

不是 Agent A 的目的驱动重写：步骤列表仍来自现有规划模型。
这里只把需求 FR-2 要求的标题填成可评审内容，并标明「推断」。
"""
from __future__ import annotations

from typing import Any

# 工具名子串 → 步骤目标 / 输入 / 输出 / 判定 / 选择理由
TOOL_HINTS: list[tuple[str, dict[str, str]]] = [
    (
        "convert_raw",
        {
            "objective": "把厂商原始谱图转为开放格式，供下游峰检测读取",
            "input": "inputspace 中的 .raw / 厂商格式",
            "output": "converted_mzml/ 下的 mzML",
            "expected": "每个成功转换的 raw 对应一份 mzML；失败须留日志",
            "reason": "后续 XCMS/OpenMS/MZmine 均以 mzML 为输入",
        },
    ),
    (
        "data_preprocessing_xcms",
        {
            "objective": "在 mzML 上完成峰检测、对齐、分组与补峰，得到特征矩阵",
            "input": "mzML 目录 + metadata",
            "output": "峰表 / 特征矩阵 / XCMS 日志",
            "expected": "特征表行数为峰、列为样本；空表视为失败而非跳过",
            "reason": "当前 MCP 已注册 CentWave 预处理管线，适合 LC-MS 非靶向",
        },
    ),
    (
        "data_preprocessing_openms",
        {
            "objective": "用 OpenMS 完成峰检测与特征组装",
            "input": "mzML 目录",
            "output": "特征表 / featureXML（若启用）",
            "expected": "写出可读特征表；失败须有日志",
            "reason": "与 XCMS 等价的预处理选项，按计划选用其一",
        },
    ),
    (
        "data_preprocessing_mzmine",
        {
            "objective": "用 MZmine 完成峰检测与对齐",
            "input": "mzML 目录",
            "output": "MZmine 特征表",
            "expected": "特征表可被后续统计读取",
            "reason": "用户或方案指定 MZmine 时使用",
        },
    ),
    (
        "statistical_analysis_mixomics",
        {
            "objective": "在特征矩阵上做多元统计与差异检验，回答组间是否可分、哪些特征显著",
            "input": "特征表 + metadata 分组列",
            "output": "pca_scores.csv、plsda_scores.csv、volcano_results.csv、vip_scores.csv 等",
            "expected": "PCA/PLS-DA 坐标行数=样本数；火山图表含 log2FC 与 p/q 值",
            "reason": "仓库已接 mixOmics，可一次产出降维与差异结果",
        },
    ),
    (
        "molecular_networking",
        {
            "objective": "用谱间相似度构建分子网络，观察结构相关簇",
            "input": "MGF / 特征-谱对应表",
            "output": "network_nodes.csv、network_edges.csv、布局与分布图数据",
            "expected": "边表含 cosine；空网络须在日志说明阈值过严或 MS2 不足",
            "reason": "GNPS/FBMN 类网络是注释与家族发现的常用展示",
        },
    ),
    (
        "kegg_compound_enrichment",
        {
            "objective": "把差异化合物映射到通路，看哪些通路被富集",
            "input": "差异化合物/注释表",
            "output": "kegg_compound_enrich.csv",
            "expected": "含通路名与 p/q 或 count；无注释时允许空表但须声明",
            "reason": "KEGG ORA 是方案中通路层的默认工具",
        },
    ),
    (
        "deepmass",
        {
            "objective": "对 MS2 做深度学习谱库注释",
            "input": "MGF",
            "output": "注释表",
            "expected": "每条谱有得分或无匹配标记，不得静默丢弃",
            "reason": "DeepMASS 已在工具白名单中",
        },
    ),
    (
        "spectral_annotation",
        {
            "objective": "谱库匹配注释",
            "input": "MGF 或配对谱",
            "output": "library_matches.csv 一类注释表",
            "expected": "匹配结果可追溯到谱 ID",
            "reason": "为差异特征提供化合物层解释",
        },
    ),
]

FIGURE_HINTS: dict[str, dict[str, str]] = {
    "pca": {
        "theme": "样本在无监督空间中是否按实验分组分离（数据质量/批效应初判）",
        "logic": "特征矩阵 → 标准化 → PCA → 样本得分着色 → 读组内聚集与组间分离",
        "purpose": "回答「分组是否构成主要方差来源」，不是生物标志物证明",
        "design": "PC1–PC2 散点；点=样本；颜色=metadata Group；可加 95% 椭圆",
        "expected": "同组宜相对聚集；若按 Batch 着色更分离，则提示批效应",
        "rationale": "无监督图放在差异图之前，避免把监督分离误当成质量合格",
    },
    "plsda": {
        "theme": "在给定分组下样本能否被监督分离",
        "logic": "带标签的特征矩阵 → PLS-DA → 得分图 → 与 PCA 对照",
        "purpose": "展示分组相关的协方差结构；须与 PCA 对照，防止过拟合叙事",
        "design": "LV1–LV2 散点；颜色=分组",
        "expected": "组间沿 LV1 或 LV2 分开；若 PCA 完全重叠而 PLS-DA 完美分开，解读须保守",
        "rationale": "监督图回答「按设计分组能否分开」，与 PCA 的无监督问题不同",
    },
    "volcano": {
        "theme": "哪些特征在统计与效应量上同时显著",
        "logic": "组间检验 → log2FC 与 −log10(p/q) → 阈值分区 → 上/下调点",
        "purpose": "把「显著且有效应」的特征集合可视化，供后续注释/网络使用",
        "design": "横轴 log2FC，纵轴 −log10(p)；阈值线；颜色区分显著/不显著",
        "expected": "显著点落在两侧；阈值须与方案 Expected results 一致",
        "rationale": "与 PCA 不同：这里回答差异特征分布，不回答样本是否聚成一团",
    },
    "vip_bar": {
        "theme": "哪些变量对监督模型贡献最大",
        "logic": "PLS-DA → VIP 排序 → 条形图",
        "purpose": "给出候选变量优先级，供热图与注释收窄范围",
        "design": "横条图，VIP 降序；可标 VIP=1 参考线",
        "expected": "头部变量 VIP 明显高于其余；名单应能对上热图行名",
        "rationale": "VIP 是模型贡献而非单独的因果证明，故与火山图并列而非替代",
    },
    "heatmap_vip": {
        "theme": "高 VIP 特征在样本中的强度模式是否与分组一致",
        "logic": "取 Top VIP → 样本×特征矩阵 → 聚类热图",
        "purpose": "检查头部特征是否在组内可重复、组间可区分",
        "design": "行=特征、列=样本；列注释=分组；行/列可聚类",
        "expected": "同组列颜色块宜连续；与 VIP 名单一致",
        "rationale": "把条形图上的名单展开成样本模式，避免只报告一个 VIP 分数",
    },
    "kegg_bar": {
        "theme": "差异化合物落在哪些通路",
        "logic": "差异/注释化合物 → KEGG ORA → −log10(p) 或 count 条形图",
        "purpose": "从特征名单升到通路层，为机制讨论提供可引用的富集结果",
        "design": "通路名为纵轴，显著性或 count 为横轴",
        "expected": "显著通路排在前面；无注释时图应标 missing 而非空绘",
        "rationale": "通路图依赖注释，与火山图的「未鉴定特征」层区分",
    },
    "kegg_bubble": {
        "theme": "富集通路的显著性与覆盖规模",
        "logic": "ORA 结果 → 气泡（大小=count，颜色=p）",
        "purpose": "同时看「是否显著」与「涉及多少化合物」的权衡",
        "design": "散点/气泡；双编码 count 与 p",
        "expected": "高 count 且低 p 的通路醒目",
        "rationale": "条形图只排显著性；气泡补覆盖度，避免只报一条最显著通路",
    },
    "cosine_hist": {
        "theme": "网络边的谱相似度分布，检查阈值是否过严或过松",
        "logic": "边表 cosine → 直方图",
        "purpose": "为网络阈值提供可检查的分布，而不是只给一张拓扑图",
        "design": "cosine 直方图；可标所用阈值",
        "expected": "阈值附近应有足够边；若几乎无边则阈值或 MS2 质量有问题",
        "rationale": "阈值权衡图，对应需求中的 trade-off 呈现",
    },
    "degree_hist": {
        "theme": "节点连接度是否形成少数枢纽",
        "logic": "节点度数 → 直方图",
        "purpose": "描述网络稀疏/枢纽结构，辅助阅读拓扑图",
        "design": "度数直方图",
        "expected": "多数低度数、少数高度数（若像无标度）；高度数节点应能在拓扑图找到",
        "rationale": "拓扑图看形状，度数分布给出可核对的计数",
    },
    "family_size": {
        "theme": "分子家族规模分布",
        "logic": "连通分量大小 → 条形/直方图",
        "purpose": "看是否存在大簇（相关结构）还是大量单节点",
        "design": "家族大小分布",
        "expected": "若几乎全是 size=1，说明网络未连上，需回头看 cosine 阈值",
        "rationale": "与度数分布互补：一个看节点，一个看连通家族",
    },
    "network_topology": {
        "theme": "分子网络的整体连通与家族着色",
        "logic": "节点+边+布局 → 网络图，颜色=家族或注释类",
        "purpose": "展示结构相关簇，供与注释/差异特征交叉阅读",
        "design": "力导向或预计算布局；点大小可选度数",
        "expected": "可见簇而非一片散点；孤立点过多则与 family_size 互相印证",
        "rationale": "这是网络的主图；分布图是它的诊断，不重复画同一拓扑",
    },
}


def hint_for_tool(task: str) -> dict[str, str]:
    low = (task or "").lower()
    for key, hint in TOOL_HINTS:
        if key in low:
            return hint
    return {
        "objective": "完成本步计算（由规划步骤描述）",
        "input": "上一步产物或会话 inputspace",
        "output": "写入本会话 outputspace",
        "expected": "写出对应文件与日志；失败不得静默跳过",
        "reason": "来自当前规划步骤中的工具名",
    }


def hint_for_plot(plot_type: str) -> dict[str, str]:
    aliases = {
        "kegg_dotplot": "kegg_bubble",
    }
    key = aliases.get(plot_type, plot_type)
    return FIGURE_HINTS.get(key) or {
        "theme": f"展示 {plot_type} 相关结果",
        "logic": "结果表 → 该注册图型 → 读图",
        "purpose": f"方案步骤需要 {plot_type} 图",
        "design": "按已注册 PlotSpec 默认编码",
        "expected": "图与对应 CSV 行数/列名可核对",
        "rationale": "由规划步骤中的图型关键词推断，供评审是否保留",
    }


def figure_payload(plot_type: str, index: int, spec_title: str) -> dict[str, Any]:
    h = hint_for_plot(plot_type)
    return {
        "figure_id": f"Figure {index}",
        "plot_type": plot_type,
        "title": spec_title or plot_type,
        "theme": h["theme"],
        "logic": h["logic"],
        "purpose": h["purpose"],
        "expected_observation": h["expected"],
        "panels": [
            {
                "panel_id": "A",
                "purpose": h["purpose"],
                "design": h["design"],
                "expected_observation": h["expected"],
                "rationale": h["rationale"],
            }
        ],
    }
