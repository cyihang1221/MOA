from mcp.server.fastmcp import FastMCP
from src.tools.convert_raw_to_mzml import (
    convert_raw_to_mzml_msconvert_impl,
    convert_raw_to_mzml_ThermoRawFileParser_impl,
    convert_raw_to_mzml_OpenMS_FileConverter_impl,
    mzml_directory_to_mgf_impl,
)
from src.tools.peak_detection import peak_detection_xcms_centwave_impl, peak_detection_peakonly_impl
from src.tools.peak_alignment import align_retention_time_obiwarp_impl, align_retention_time_loess_impl
from src.tools.peak_group import group_peaks_xcms_groupChromPeaks_impl
from src.tools.missing_peak_filling import fill_missing_peaks_xcms_fillChromPeaks_impl
from src.tools.filter_redundant_features import filter_redundant_features_camera_impl, filter_redundant_features_ramclustr_impl
from src.tools.library_match import (
    library_match_blink_impl,
    library_match_cosine_impl,
    library_match_jaccard_impl,
    library_match_ms2deepscore_impl,
    library_match_msbert_impl,
    library_match_pair_from_mgf_impl,
    library_match_full_workflow_impl,
    library_match_spectral_entropy_impl,
    library_match_spec2vec_impl,
)

mcp = FastMCP("MOA_tools")



# ============================= 数据转换 =============================
# ThermoRawFileParser
@mcp.tool(
    name="convert_raw_to_mzml_ThermoRawFileParser",
    description="""
    基于 ThermoRawFileParser，将质谱仪的 .raw 格式文件批量转换为 .mzml 格式文件，是 Thermo 专用的转换工具。

    此工具适用于：
    - 转换 Thermo 质谱仪的 .raw 文件
    - 进行质谱数据预处理

    参数：
    - input_dir: 输入目录，包含 .raw 文件
    - output_dir: 输出目录，保存转换后的 .mzML 文件

    此工具执行结果：
    - 转换得到的 .mzML 文件保存在指定输出目录
    """,
)  
async def convert_raw_to_mzml_ThermoRawFileParser_tool(input_dir: str, output_dir: str):
    convert_raw_to_mzml_ThermoRawFileParser_impl(input_dir, output_dir)
    return f"已使用 ThermoRawFileParser 完成 .raw 转 .mzML 的转换，输入目录: {input_dir}, 输出目录: {output_dir}"


# msconvert
@mcp.tool(
    name="convert_raw_to_mzml_msconvert",
    description="""
    基于 ProteoWizard 的 msconvert，将质谱仪的 .raw 格式文件批量转换为 .mzml 格式文件，支持峰拾取功能，适用于多种厂商的质谱数据转换。

    此工具适用于：
    - 转换质谱仪的 .raw 文件（不限于 Thermo）
    - 进行质谱数据预处理（如峰拾取）

    参数：
    - input_dir: 输入目录，包含 .raw 文件
    - output_dir: 输出目录，保存转换后的 .mzML 文件

    此工具执行结果：
    - 转换得到的 .mzML 文件保存在指定输出目录
    """
)  
async def convert_raw_to_mzml_msconvert_tool(input_dir: str, output_dir: str):
    convert_raw_to_mzml_msconvert_impl(input_dir, output_dir)
    return f"已使用 msconvert 完成 .raw 转 .mzML 的转换，输入目录: {input_dir}, 输出目录: {output_dir}"


@mcp.tool(
    name="mzml_directory_to_mgf",
    description="""
    将某个目录下所有真实存在的 .mzML 文件批量转为 .mgf（每个 mzML 生成同名 .mgf，默认导出 MS2 谱）。
    必须使用本工具完成「mzML → MGF」，禁止编造 sample.mzML 等不存在的文件名；应使用输入目录中实际列出的文件。

    此工具适用于：
    - raw 经 msconvert 转成 mzML 之后，再导出为 MGF 供 library_match_pair_from_mgf 使用
    - 不依赖 Docker

    参数：
    - input_dir: 包含 .mzML 的目录（例如 workspace/converted_mzml）
    - output_dir: 输出 .mgf 的目录（例如 workspace/converted_mgf）
    - ms_level: 导出哪一级 MS，默认 2（MS2）

    此工具执行结果：
    - 返回每个文件写出谱图数量的摘要文本
    """
)
async def mzml_directory_to_mgf_tool(input_dir: str, output_dir: str, ms_level: int = 2):
    summary = mzml_directory_to_mgf_impl(input_dir, output_dir, ms_level=ms_level)
    return f"已完成 mzML 批量转 MGF。\n{summary}"


# OpenMS FileConverter
@mcp.tool(
    name="convert_raw_to_mzml_OpenMS_FileConverter",
    description="""
    基于 OpenMS 的 FileConverter，支持 mzML/mzXML/mgf 等格式互转（需本机已安装 OpenMS 且路径正确）。

    重要：将 mzML 批量转为 MGF 时请使用 mzml_directory_to_mgf，不要使用本工具，以免虚构 input_file 导致失败。

    此工具适用于：
    - 单文件格式转换（且 input_file 必须真实存在）

    参数：
    - input_file: 输入文件的绝对路径
    - output_file: 输出文件的绝对路径

    此工具执行结果：
    - 转换得到的文件保存在指定路径
    """
)
async def convert_raw_to_mzml_OpenMS_FileConverter_tool(input_file: str, output_file: str):
    convert_raw_to_mzml_OpenMS_FileConverter_impl(input_file, output_file)
    return f"已使用 OpenMS FileConverter 完成格式转换，输入: {input_file}, 输出: {output_file}"



# ============================= 峰检测 =============================
# xcms-CentWave
@mcp.tool(
    name="peak_detection_xcms_centwave",
    description="""
    基于 xcms-CentWave 对 LC-MS 代谢组学数据进行峰检测（peak picking）。

    此工具适用于：
    - 分析 mzML 文件
    - 进行质谱数据预处理
    - 提取色谱峰（feature detection）

    参数：
    - input_dir: 输入目录，包含 mzML 文件
    - output_dir: 输出目录，保存峰检测结果
    - file_pattern: mzML 文件的匹配模式，默认为 "*.mzML"
    - peakwidth_min: 峰宽的最小值，默认为 5
    - peakwidth_max: 峰宽的最大值，默认为 30
    - snthresh: 信噪比阈值，默认为 10
    - ppm: 质量精度，默认为 10
    - prefilter_n: 预过滤的最小峰数，默认为 3
    - prefilter_intensity: 预过滤的最小强度，默认为 1000

    此工具执行结果：
    - 保存峰检测结果的 RDS 文件，包含所有检测到的色谱峰信息
    """
)
async def peak_detection_xcms_centwave_tool(input_dir: str, output_dir: str, file_pattern: str, peakwidth_min: int, peakwidth_max: int, snthresh: int, ppm: int, prefilter_n: int, prefilter_intensity: int):
    peak_detection_xcms_centwave_impl(input_dir, output_dir, file_pattern, peakwidth_min, peakwidth_max, snthresh, ppm, prefilter_n, prefilter_intensity)
    return f"已使用 xcms-CentWave 完成峰检测，输入目录: {input_dir}, 输出目录: {output_dir}"


# peakonly
@mcp.tool(
    name="peak_detection_peakonly",
    description="""
    基于 peakonly 对 LC-MS 代谢组学数据进行峰检测（peak picking）。

    此工具适用于：
    - 分析 mzML 文件
    - 进行质谱数据预处理
    - 提取色谱峰（feature detection）

    参数：
    - input_dir: 输入目录，包含 mzML 文件，文件应包含质心化的 MS1 数据
    - output_dir: 输出目录，保存峰检测结果
    - file_pattern: mzML 文件的匹配模式，默认为 "*.mzML"
    - model_dir: peakonly 模型文件所在目录，默认为 "workspace/models/

    此工具执行结果：
    - 保存峰检测结果的 RDS 文件，包含所有检测到的色谱峰信息
    """
)
async def peak_detection_peakonly_tool(input_dir: str, output_dir: str, file_pattern: str = "*.mzML", model_dir: str = "workspace/models/"):
    peak_detection_peakonly_impl(input_dir, output_dir, file_pattern, model_dir)
    return f"已使用 peakonly 完成峰检测，输入目录: {input_dir}, 输出目录: {output_dir}"



# ============================= 峰对齐 =============================
# XCMS-Obiwarp
@mcp.tool(
    name="align_retention_time_obiwarp",
    description="""
    基于 XCMS 的 Obiwarp 方法进行保留时间（RT）对齐。

    此工具适用于：
    - 对 LC-MS 代谢组学数据进行保留时间对齐
    - 解决不同样本之间的保留时间差异问题
    
    参数：
    - input_rds: 输入的 RDS 文件，包含需要对齐的色谱峰数据
    - output_rds: 输出的 RDS 文件，保存对齐后的结果

    此工具执行结果：
    - 对齐后的 RDS 文件，包含调整保留时间后的色谱峰数据
    """
)
async def align_retention_time_obiwarp_tool(input_rds: str, output_rds: str):
    align_retention_time_obiwarp_impl(input_rds, output_rds)
    return f"已使用 XCMS_Obiwarp 完成保留时间（RT）对齐，输入文件: {input_rds}, 输出文件: {output_rds}"


# XCMS-LOESS
@mcp.tool(
    name="align_retention_time_loess",
    description="""
    基于 XCMS 的 LOESS 方法进行保留时间（RT）对齐。

    此工具适用于：
    - 对 LC-MS 代谢组学数据进行保留时间校正
    - 使用 LOESS 校正方法调整样本间的保留时间差异
    
    参数：
    - input_rds: 输入的 RDS 文件，包含需要校正的色谱峰数据
    - output_rds: 输出的 RDS 文件，保存校正后的结果

    此工具执行结果：
    - 校正后的 RDS 文件，包含调整保留时间后的色谱峰数据
    """
)
async def align_retention_time_loess_tool(input_rds: str, output_rds: str):
    align_retention_time_loess_impl(input_rds, output_rds)
    return f"已使用 XCMS_LOESS 完成保留时间校正，输入文件: {input_rds}, 输出文件: {output_rds}"



# ============================= 峰分组 =============================
# XCMS-groupChromPeaks
@mcp.tool(
    name="group_peaks_xcms_groupChromPeaks",
    description="""
    基于 XCMS 的峰密度分组方法进行特征分组。

    此工具适用于：
    - 根据色谱峰的密度进行特征分组
    - 对于具有多样本的 LC-MS 数据，进行相似特征的合并
    
    参数：
    - input_rds: 输入的 RDS 文件，包含已检测到的色谱峰数据
    - output_rds: 输出的 RDS 文件，保存分组后的结果
    - groups: 样本组的定义（如果为空，将默认分为一组）
    - bw: 带宽，默认值为 30
    - min_fraction: 每个分组中需要至少的最小样本比例，默认值为 0.5
    - min_samples: 每个分组中最少需要的样本数，默认值为 1

    此工具执行结果：
    - 分组后的 RDS 文件，包含分组信息的色谱峰数据
    """
)
async def group_peaks_xcms_groupChromPeaks_tool(
    input_rds: str,
    output_rds: str,
    bw: int,
    min_fraction: float,
    min_samples: int,
    groups: list = None
):
    group_peaks_xcms_groupChromPeaks_impl(input_rds, output_rds, groups, bw, min_fraction, min_samples)
    return f"已使用 XCMS_groupChromPeaks 完成峰分组，输入文件: {input_rds}, 输出文件: {output_rds}"



# ============================= 缺失峰填充 =============================
# XCMS-fillChromPeaks
@mcp.tool(
    name="fill_missing_peaks_xcms_fillChromPeaks",
    description="""
    基于 XCMS 填补缺失的色谱峰数据。

    此工具适用于：
    - 填补因噪声或分辨率问题缺失的色谱峰
    - 基于已知的保留时间和质量信息，填补缺失的数据
    
    参数：
    - input_rds: 输入的 RDS 文件，包含检测到的色谱峰数据
    - output_rds: 输出的 RDS 文件，保存填补后的结果
    - expand_rt: 允许扩展的保留时间窗口，默认为 0.0
    - expand_mz: 允许扩展的质量窗口，默认为 0.0

    此工具执行结果：
    - 填补后的 RDS 文件，包含原有色谱峰数据以及填补的色谱峰数据
    """
)
async def fill_missing_peaks_xcms_fillChromPeaks_tool(
    input_rds: str,
    output_rds: str,
    expand_rt: float = 0.0,
    expand_mz: float = 0.0
):
    fill_missing_peaks_xcms_fillChromPeaks_impl(input_rds, output_rds, expand_rt, expand_mz)
    return f"已使用 XCMS_fillChromPeaks 完成缺失峰填补，输入文件: {input_rds}, 输出文件: {output_rds}"



# ============================= 过滤冗余特征 =============================
# CAMERA
@mcp.tool(
    name="filter_redundant_features_camera",
    description="""
    使用 CAMERA 进行冗余特征过滤。

    此工具适用于：
    - 基于 XCMS 生成的数据，通过 CAMERA 对冗余特征进行过滤
    - 去除多余的特征，并保留最具代表性的特征
    
    参数：
    - input_rds: 输入的 RDS 文件，包含 XCMS 处理后的色谱峰数据
    - output_rds: 输出的 RDS 文件，保存过滤后的结果

    此工具执行结果：
    - 过滤后的 RDS 文件，包含去除冗余特征后的色谱峰数据
    """
)
async def filter_redundant_features_camera_tool(
    input_rds: str,
    output_rds: str
):
    filter_redundant_features_camera_impl(input_rds, output_rds)
    return f"已使用 CAMERA 完成冗余特征过滤，输入文件: {input_rds}, 输出文件: {output_rds}"


# RAMClustR
@mcp.tool(
    name="filter_redundant_features_ramclustr",
    description="""
    使用 RAMClustR 进行冗余特征过滤。

    此工具适用于：
    - 基于 XCMS 生成的数据，通过 RAMClustR 对冗余特征进行过滤
    - 利用 RAMClustR 提供的算法进行高效特征过滤
    
    参数：
    - input_rds: 输入的 RDS 文件，包含 XCMS 处理后的色谱峰数据
    - output_rds: 输出的 RDS 文件，保存过滤后的结果

    此工具执行结果：
    - 过滤后的 RDS 文件，包含去除冗余特征后的色谱峰数据
    """
)
async def filter_redundant_features_ramclustr_tool(
    input_rds: str,
    output_rds: str
):
    filter_redundant_features_ramclustr_impl(input_rds, output_rds)
    return f"已使用 RAMClustR 完成冗余特征过滤，输入文件: {input_rds}, 输出文件: {output_rds}"


# ============================= 库匹配定性 =============================
# 推荐：从 MGF 路径配对打分（Agent 易用，勿传空列表）
@mcp.tool(
    name="library_match_pair_from_mgf",
    description="""
    从两个 MGF 文件各读取一条谱图（按 spectrum_index），执行库匹配打分。优先于直接传 mz/intensity 列表，避免大模型传空数组。

    此工具适用于：
    - 查询谱图与参考谱库中某条谱图的快速对比
    - 与 convert_raw_to_mzml 之后的流程衔接：可先将需比对的谱导出为 MGF，再调用本工具

    参数：
    - method: 打分方法，取其一（亦可写自然语言别名，将被映射为峰级实现：cosine / jaccard / spectral entropy）：
      blink | spec2vec | ms2deepscore |
      cosine_binned | spectral_entropy_binned | jaccard_binned |
      cosine_peak | spectral_entropy_peak | jaccard_peak
    - query_mgf_path: 查询谱图所在 MGF 的绝对路径
    - reference_mgf_path: 参考谱图所在 MGF 的绝对路径
    - query_spectrum_index: 查询 MGF 中的谱序号，从 0 开始，默认 0
    - reference_spectrum_index: 参考 MGF 中的谱序号，从 0 开始，默认 0
    - mz_tolerance: 仅用于 blink，默认 0.01
    - bin_size: 用于 *_binned 方法的分箱宽度（Da），默认 0.1
    - model_path: spec2vec/ms2deepscore 模型路径，可留空则从环境变量 SPEC2VEC_MODEL_PATH / MS2DEEPSCORE_MODEL_PATH 读取
    - precursor_mz / reference_precursor_mz: 可选，覆盖从 MGF 元数据解析的前体 m/z
    - output_dir: 可选，若提供则将本行结果追加写入该目录下的 library_match_pair_results.txt

    此工具执行结果：
    - 返回一行摘要字符串，包含 method、score、谱峰数等
    """
)
async def library_match_pair_from_mgf_tool(
    method: str,
    query_mgf_path: str,
    reference_mgf_path: str,
    query_spectrum_index: int = 0,
    reference_spectrum_index: int = 0,
    mz_tolerance: float = 0.01,
    bin_size: float = 0.1,
    model_path: str = "",
    precursor_mz: float | None = None,
    reference_precursor_mz: float | None = None,
    n_decimals: int = 2,
    output_dir: str = "",
):
    summary = library_match_pair_from_mgf_impl(
        method=method,
        query_mgf_path=query_mgf_path,
        reference_mgf_path=reference_mgf_path,
        query_spectrum_index=query_spectrum_index,
        reference_spectrum_index=reference_spectrum_index,
        mz_tolerance=mz_tolerance,
        bin_size=bin_size,
        model_path=model_path or None,
        precursor_mz=precursor_mz,
        reference_precursor_mz=reference_precursor_mz,
        n_decimals=n_decimals,
        output_dir=output_dir or None,
    )
    return f"已完成库匹配（MGF 配对）: {summary}"


@mcp.tool(
    name="library_match_full_workflow",
    description="""
    一站式库匹配流程工具：raw -> mzML -> MGF -> library matching。

    适用于：
    - 已有 raw 文件目录，想直接完成转换与单对库匹配
    - 避免手动分步调用多个工具

    参数：
    - raw_input_dir: 原始 raw 文件目录
    - mzml_output_dir: mzML 输出目录
    - mgf_output_dir: MGF 输出目录
    - reference_mgf_path: 参考库 MGF 文件路径
    - method: 匹配方法（默认 cosine_peak）
    - converter: raw 转 mzML 的转换器，thermo 或 msconvert
    - query_mgf_path: 可选，指定用于匹配的 query mgf；不传则默认选 mgf_output_dir 下第一个
    - query_spectrum_index / reference_spectrum_index: 谱序号（默认 0）
    - mz_tolerance / bin_size: 匹配参数
    - model_path: spec2vec/ms2deepscore 可选模型路径
    - precursor_mz / reference_precursor_mz: 可选覆盖前体 m/z
    - n_decimals: spec2vec token 小数位
    - output_dir: 可选，写入摘要日志目录
    """
)
async def library_match_full_workflow_tool(
    raw_input_dir: str,
    mzml_output_dir: str,
    mgf_output_dir: str,
    reference_mgf_path: str,
    method: str = "cosine_peak",
    converter: str = "thermo",
    query_mgf_path: str = "",
    query_spectrum_index: int = 0,
    reference_spectrum_index: int = 0,
    mz_tolerance: float = 0.01,
    bin_size: float = 0.1,
    model_path: str = "",
    precursor_mz: float | None = None,
    reference_precursor_mz: float | None = None,
    n_decimals: int = 2,
    output_dir: str = "",
):
    summary = library_match_full_workflow_impl(
        raw_input_dir=raw_input_dir,
        mzml_output_dir=mzml_output_dir,
        mgf_output_dir=mgf_output_dir,
        reference_mgf_path=reference_mgf_path,
        method=method,
        converter=converter,
        query_mgf_path=query_mgf_path or None,
        query_spectrum_index=query_spectrum_index,
        reference_spectrum_index=reference_spectrum_index,
        mz_tolerance=mz_tolerance,
        bin_size=bin_size,
        model_path=model_path or None,
        precursor_mz=precursor_mz,
        reference_precursor_mz=reference_precursor_mz,
        n_decimals=n_decimals,
        output_dir=output_dir or None,
    )
    return f"已完成完整库匹配流程: {summary}"


# Cosine
@mcp.tool(
    name="library_match_cosine",
    description="""
    使用 Cosine（余弦相似度）对两个**等长**数值向量打分。若谱图为 m/z+强度列表且长度不一致，请改用 library_match_pair_from_mgf（method=cosine_binned）或 library_match_blink。

    此工具适用于：
    - 计算查询谱图向量与参考谱图向量之间的相似度
    - 作为库匹配定性的基础评分函数

    参数：
    - query_vector: 查询向量（数值列表，禁止传空列表）
    - reference_vector: 参考向量（数值列表，禁止传空列表）

    此工具执行结果：
    - 返回两个向量的余弦相似度分数（范围 [-1, 1]）
    """
)
async def library_match_cosine_tool(
    query_vector: list[float],
    reference_vector: list[float]
):
    score = library_match_cosine_impl(query_vector, reference_vector)
    return f"已完成 Cosine 相似度计算，score={score:.6f}"


# Jaccard
@mcp.tool(
    name="library_match_jaccard",
    description="""
    使用 Jaccard 相似度对两个向量进行相似度计算，适用于基于“特征是否出现”的库匹配定性任务。

    此工具适用于：
    - 计算查询向量与参考向量的特征重叠程度
    - 作为二值化特征匹配的基础评分函数

    参数：
    - query_vector: 查询向量（数值列表，非零表示该特征出现）
    - reference_vector: 参考向量（数值列表，非零表示该特征出现）

    此工具执行结果：
    - 返回两个向量的 Jaccard 相似度分数（范围 [0, 1]）
    """
)
async def library_match_jaccard_tool(
    query_vector: list[float],
    reference_vector: list[float]
):
    score = library_match_jaccard_impl(query_vector, reference_vector)
    return f"已完成 Jaccard 相似度计算，score={score:.6f}"


# Spectral entropy
@mcp.tool(
    name="library_match_spectral_entropy",
    description="""
    使用真实 Spectral entropy 相似度对两个谱图向量进行匹配，适用于质谱库匹配定性任务。

    此工具适用于：
    - 计算查询谱图与参考谱图的谱熵相似度
    - 作为谱图分布相似性的评分函数

    参数：
    - query_vector: 查询向量（数值列表，建议为非负强度）
    - reference_vector: 参考向量（数值列表，建议为非负强度）

    此工具执行结果：
    - 返回两个向量的 Spectral entropy 相似度分数（范围 [0, 1]）
    """
)
async def library_match_spectral_entropy_tool(
    query_vector: list[float],
    reference_vector: list[float]
):
    score = library_match_spectral_entropy_impl(query_vector, reference_vector)
    return f"已完成 Spectral entropy 相似度计算，score={score:.6f}"


# Spec2Vec
@mcp.tool(
    name="library_match_spec2vec",
    description="""
    使用真实 Spec2Vec 模型进行库匹配定性评分。

    此工具适用于：
    - 计算查询谱图与参考谱图的 Spec2Vec 相似度
    - 通过 model_path 或环境变量 SPEC2VEC_MODEL_PATH 加载模型
    - 若谱图在 MGF 文件中，优先使用 library_match_pair_from_mgf（method=spec2vec），勿传空 mz 列表

    参数：
    - query_mz: 查询谱图 m/z 列表
    - query_intensity: 查询谱图强度列表
    - reference_mz: 参考谱图 m/z 列表
    - reference_intensity: 参考谱图强度列表
    - model_path: Spec2Vec 模型路径（可选）
    - precursor_mz: 查询谱图前体离子 m/z（可选）
    - reference_precursor_mz: 参考谱图前体离子 m/z（可选）
    - n_decimals: 生成 Spec2Vec token 时的保留小数位（默认 2）

    此工具执行结果：
    - 返回两个谱图的 Spec2Vec 相似度分数
    """
)
async def library_match_spec2vec_tool(
    query_mz: list[float],
    query_intensity: list[float],
    reference_mz: list[float],
    reference_intensity: list[float],
    model_path: str = "",
    precursor_mz: float | None = None,
    reference_precursor_mz: float | None = None,
    n_decimals: int = 2
):
    score = library_match_spec2vec_impl(
        query_mz,
        query_intensity,
        reference_mz,
        reference_intensity,
        model_path or None,
        precursor_mz,
        reference_precursor_mz,
        n_decimals
    )
    return f"已完成 Spec2Vec 相似度计算，score={score:.6f}"


# MS2DeepScore
@mcp.tool(
    name="library_match_ms2deepscore",
    description="""
    使用真实 MS2DeepScore 模型进行库匹配定性评分。

    此工具适用于：
    - 计算查询谱图与参考谱图的 MS2DeepScore 相似度
    - 通过 model_path 或环境变量 MS2DEEPSCORE_MODEL_PATH 加载模型
    - 若谱图在 MGF 文件中，优先使用 library_match_pair_from_mgf（method=ms2deepscore）

    参数：
    - query_mz: 查询谱图 m/z 列表
    - query_intensity: 查询谱图强度列表
    - reference_mz: 参考谱图 m/z 列表
    - reference_intensity: 参考谱图强度列表
    - model_path: MS2DeepScore 模型路径（可选）
    - precursor_mz: 查询谱图前体离子 m/z（可选）
    - reference_precursor_mz: 参考谱图前体离子 m/z（可选）

    此工具执行结果：
    - 返回两个谱图的 MS2DeepScore 相似度分数
    """
)
async def library_match_ms2deepscore_tool(
    query_mz: list[float],
    query_intensity: list[float],
    reference_mz: list[float],
    reference_intensity: list[float],
    model_path: str = "",
    precursor_mz: float | None = None,
    reference_precursor_mz: float | None = None
):
    score = library_match_ms2deepscore_impl(
        query_mz,
        query_intensity,
        reference_mz,
        reference_intensity,
        model_path or None,
        precursor_mz,
        reference_precursor_mz
    )
    return f"已完成 MS2DeepScore 相似度计算，score={score:.6f}"


# BLINK
@mcp.tool(
    name="library_match_blink",
    description="""
    使用真实BLINK快速匹配计算两条谱图的相似度。

    此工具适用于：
    - 在给定 m/z 容差下进行谱峰快速匹配
    - 对查询谱图与参考谱图进行快速库匹配打分
    - 若谱图在 MGF 中，优先使用 library_match_pair_from_mgf（method=blink）

    参数：
    - query_mz: 查询谱图 m/z 列表
    - query_intensity: 查询谱图强度列表
    - reference_mz: 参考谱图 m/z 列表
    - reference_intensity: 参考谱图强度列表
    - mz_tolerance: 峰匹配容差（默认 0.01）

    此工具执行结果：
    - 返回 BLINK 风格相似度分数（范围 [0, 1]）
    """
)
async def library_match_blink_tool(
    query_mz: list[float],
    query_intensity: list[float],
    reference_mz: list[float],
    reference_intensity: list[float],
    mz_tolerance: float = 0.01
):
    score = library_match_blink_impl(query_mz, query_intensity, reference_mz, reference_intensity, mz_tolerance)
    return f"已完成 BLINK 相似度计算，score={score:.6f}"


# MS-BERT
@mcp.tool(
    name="library_match_msbert",
    description="""
    使用外部脚本进行 MS-BERT 推理并返回相似度评分。

    此工具适用于：
    - 通过独立脚本对查询谱图和参考谱图进行 MS-BERT 推理
    - 通过 script_path 或环境变量 MSBERT_INFER_SCRIPT 指定推理脚本

    参数：
    - query_mz: 查询谱图 m/z 列表
    - query_intensity: 查询谱图强度列表
    - reference_mz: 参考谱图 m/z 列表
    - reference_intensity: 参考谱图强度列表
    - script_path: MS-BERT 推理脚本路径（可选）
    - model_path: MS-BERT 模型路径（可选）
    - precursor_mz: 查询谱图前体离子 m/z（可选）
    - reference_precursor_mz: 参考谱图前体离子 m/z（可选）
    - timeout_sec: 脚本超时时间（秒）

    此工具执行结果：
    - 返回 MS-BERT 推理得到的相似度分数
    """
)
async def library_match_msbert_tool(
    query_mz: list[float],
    query_intensity: list[float],
    reference_mz: list[float],
    reference_intensity: list[float],
    script_path: str = "",
    model_path: str = "",
    precursor_mz: float | None = None,
    reference_precursor_mz: float | None = None,
    timeout_sec: int = 120
):
    score = library_match_msbert_impl(
        query_mz,
        query_intensity,
        reference_mz,
        reference_intensity,
        script_path or None,
        model_path or None,
        precursor_mz,
        reference_precursor_mz,
        timeout_sec
    )
    return f"已完成 MS-BERT 相似度计算，score={score:.6f}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
    