from mcp.server.fastmcp import FastMCP
# from src.tools.group_peaks import group_peaks_openms_PeakGroup_impl, group_peaks_xcms_groupChromPeaks_impl
# from src.tools.isotope_annotation import identify_isotopes_openms_IsotopeTools_impl
# from src.tools.mzmine_lcms import mzmine_lcms_datapreprocess_impl
from src.tools.convert_raw_to_mzml import convert_raw_to_mzml_msconvert_impl, convert_raw_to_mzml_ThermoRawFileParser_impl, convert_raw_to_mzml_OpenMS_FileConverter_impl
# from src.tools.peak_detection import peak_detection_kpic_impl, peak_detection_openms_featurefinder_impl, peak_detection_openms_peakpickerhires_impl, peak_detection_xcms_centwave_impl, peak_detection_peakonly_impl
# from src.tools.align_retention_time import align_retention_time_xcms_loess_impl, align_retention_time_xcms_obiwarp_impl
# from src.tools.missing_peak_filling import fill_missing_peaks_xcms_fillChromPeaks_impl
# from src.tools.filter_redundant_features import filter_redundant_features_camera_impl, filter_redundant_features_mzannotation_impl, filter_redundant_features_ramclustr_impl
from src.tools.xcms import data_preprocessing_xcms_impl, extract_differential_features_impl, feature_filtering_and_missing_value_imputation_KNN_impl, spectral_annotation_impl, statistical_analysis_mixomics_impl

mcp = FastMCP("MOA_tools")



# # ============================= MZmine LC-MS 非靶向代谢组全流程 =============================
# @mcp.tool(
#     name="mzmine_lcms_datapreprocess",
#     description="""
#     MZmine LC-MS 非靶向代谢组数据预处理流程: mzML原始数据 → 峰检测 → 冗余过滤 → 保留时间对齐 → 同位素注释 → 谱峰对齐 → 缺失峰填充

#     适用于 LC-MS，不适用于 GC-MS

#     输出：可直接用于多元统计、差异分析的完整定量峰表
#     """
# )
# async def mzmine_lcms_datapreprocess_tool(
#     input_dir: str,
#     output_dir: str,
#     file_pattern: str = "*.mzML",
#     mz_tolerance: float = 0.01,
#     rt_tolerance: float = 0.2,
#     min_intensity: float = 1000.0,
#     sn_threshold: float = 3.0,
#     min_matched_samples: int = 2,
#     min_peak_width: float = 0.05,
#     max_peak_width: float = 2.0
# ):
#     mzmine_lcms_datapreprocess_impl(
#         input_dir=input_dir,
#         output_dir=output_dir,
#         file_pattern=file_pattern,
#         mz_tolerance=mz_tolerance,
#         rt_tolerance=rt_tolerance,
#         min_intensity=min_intensity,
#         sn_threshold=sn_threshold,
#         min_matched_samples=min_matched_samples,
#         min_peak_width=min_peak_width,
#         max_peak_width=max_peak_width
#     )
#     return f"已使用 MZmine 完成非靶向代谢组 LC-MS 数据预处理，输入目录: {input_dir}, 输出目录: {output_dir}"



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


# OpenMS FileConverter
@mcp.tool(
    name="convert_raw_to_mzml_OpenMS_FileConverter",
    description="""
    基于 OpenMS 的 FileConverter，支持 mzML/mzXML/mgf 数据格式的互转。

    此工具适用于：
    - 进行质谱数据预处理
    - mzML/mzXML/mgf 数据格式的互转

    参数：
    - input_file: 输入目录
    - output_file: 输出目录

    此工具执行结果：
    - 转换得到的文件保存在指定输出目录
    """
)
async def convert_raw_to_mzml_OpenMS_FileConverter_tool(input_file: str, output_file: str):
    convert_raw_to_mzml_OpenMS_FileConverter_impl(input_file, output_file)
    return f"已使用 OpenMS FileConverter 完成 .raw 转 .mzML 的转换，输入目录: {input_file}, 输出目录: {output_file}"



# # ============================= 峰检测 =============================
# # xcms-CentWave
# @mcp.tool(
#     name="peak_detection_xcms_centwave",
#     description="""
#     基于 xcms-CentWave 对 LC-MS 代谢组学数据进行峰检测（peak picking）。

#     此工具适用于：
#     - 分析 mzML 文件
#     - 进行质谱数据预处理
#     - 提取色谱峰（feature detection）

#     特点：
#     - 峰检测时自动完成解卷积

#     参数：
#     - input_dir: 输入目录，包含 mzML 文件
#     - output_dir: 输出目录，保存峰检测结果
#     - file_pattern: mzML 文件的匹配模式，默认为 "*.mzML"
#     - peakwidth_min: 峰宽的最小值，默认为 5
#     - peakwidth_max: 峰宽的最大值，默认为 30
#     - snthresh: 信噪比阈值，默认为 10
#     - ppm: 质量精度，默认为 10
#     - prefilter_n: 预过滤的最小峰数，默认为 3
#     - prefilter_intensity: 预过滤的最小强度，默认为 1000

#     此工具执行结果：
#     - .rds: xcms-CentWave 完整结果对象，可用于下游分析
#     - .csv: 通用峰表，可用于解卷积/下游分析
#     """
# )
# async def peak_detection_xcms_centwave_tool(input_dir: str, output_dir: str, file_pattern: str, peakwidth_min: int, peakwidth_max: int, snthresh: int, ppm: int, prefilter_n: int, prefilter_intensity: int):
#     peak_detection_xcms_centwave_impl(input_dir, output_dir, file_pattern, peakwidth_min, peakwidth_max, snthresh, ppm, prefilter_n, prefilter_intensity)
#     return f"已使用 xcms-CentWave 完成峰检测，输入目录: {input_dir}, 输出目录: {output_dir}"


# # OpenMS-PeakPickerHiRes
# @mcp.tool(
#     name="peak_detection_openms_peakpickerhires",
#     description="""
#     基于 OpenMS-PeakPickerHiRes 对 LC-MS/GC-MS 代谢组学数据进行高精度峰检测。

#     工具特点：
#     - 高精度、高稳定性
#     - 适合 Orbitrap / QE 等高分辨质谱
#     - 输出标准 CSV 峰表

#     参数：
#     - input_dir: 输入目录，包含 mzML 文件
#     - output_dir: 输出目录
#     - file_pattern: 文件匹配模式，默认 *.mzML
#     - peak_width: 预期峰宽度（分钟），默认 0.15
#     - snr_threshold: 信噪比阈值，默认 3.0
#     - mz_tol_ppm: 质量容差，默认 10 ppm
#     - intensity_threshold: 最小强度阈值，默认 1000

#     输出：
#     - CSV 标准峰表
#     - .featureXML OpenMS 峰对象，包含完整峰信息，可用于下游分析
#     """
# )
# async def peak_detection_openms_peakpickerhires_tool(
#     input_dir: str,
#     output_dir: str,
#     file_pattern: str = "*.mzML",
#     peak_width: float = 0.15,
#     snr_threshold: float = 3.0,
#     mz_tol_ppm: float = 10.0,
#     intensity_threshold: float = 1000.0
# ):
#     peak_detection_openms_peakpickerhires_impl(
#         input_dir=input_dir,
#         output_dir=output_dir,
#         file_pattern=file_pattern,
#         peak_width=peak_width,
#         snr_threshold=snr_threshold,
#         mz_tol_ppm=mz_tol_ppm,
#         intensity_threshold=intensity_threshold
#     )
#     return f"已使用 OpenMS-PeakPickerHiRes 完成峰检测，输入目录: {input_dir}, 输出目录: {output_dir}"


# # OpenMS-FeatureFinderMetabo
# @mcp.tool(
#     name="peak_detection_openms_featurefinder",
#     description="""
#     基于 OpenMS-FeatureFinderMetabo 对 LC-MS 代谢组学非靶向数据进行峰检测。
    
#     特点：
#     - OpenMS 官方专为代谢组学设计的核心峰检测算法
#     - 自动过滤同位素、加合物、噪声
#     - 高稳定性、高重复性
#     - 适合高分辨质谱（Orbitrap、QE、Fusion）

#     参数：
#     - input_dir: 输入目录，包含 mzML 文件
#     - output_dir: 输出目录
#     - file_pattern: mzML 文件匹配模式，默认 "*.mzML"
#     - mass_error: 质量偏差（ppm），默认 10.0
#     - intensity_threshold: 最小强度阈值，默认 1000.0
#     - min_peak_width: 最小峰宽度（分钟），默认 0.05
#     - max_peak_width: 最大峰宽度（分钟），默认 0.5
#     - snr_threshold: 信噪比阈值，默认 3.0

#     输出：
#     - CSV 标准代谢组学峰表（m/z、RT、强度、峰面积、SNR）
#     - .featureXML OpenMS 峰对象，包含完整峰信息，可用于下游分析
#     """
# )
# async def peak_detection_openms_featurefinder_tool(
#     input_dir: str,
#     output_dir: str,
#     file_pattern: str = "*.mzML",
#     mass_error: float = 10.0,
#     intensity_threshold: float = 1000.0,
#     min_peak_width: float = 0.05,
#     max_peak_width: float = 0.5,
#     snr_threshold: float = 3.0
# ):
#     peak_detection_openms_featurefinder_impl(
#         input_dir=input_dir,
#         output_dir=output_dir,
#         file_pattern=file_pattern,
#         mass_error=mass_error,
#         intensity_threshold=intensity_threshold,
#         min_peak_width=min_peak_width,
#         max_peak_width=max_peak_width,
#         snr_threshold=snr_threshold
#     )
#     return f"已使用 OpenMS-FeatureFinderMetabo 完成代谢组学峰检测，输入目录: {input_dir}, 输出目录: {output_dir}"


# # KPIC
# @mcp.tool(
#     name="peak_detection_kpic",
#     description="""
#     基于 KPIC（Kernel-based Peak Identification）对 LC-MS 代谢组学数据进行峰检测。

#     特点：
#     - 基于核函数拟合，对噪声、基质效应更稳健
#     - 适合复杂基质、峰形较差、低信噪比数据
#     - 与 XCMS 对象兼容，可后续对齐/分组

#     适用：
#     - LC-MS 非靶向代谢组学
#     - 复杂基质（血清、植物、微生物样本）

#     参数：
#     - input_dir: 输入目录，包含 mzML 文件
#     - output_dir: 输出目录
#     - file_pattern: mzML 文件匹配模式，默认 "*.mzML"
#     - ppm: 质量偏差，默认 10.0
#     - peak_width: 预期峰宽（秒/点数），默认 10.0
#     - sn_thresh: 信噪比阈值，默认 3.0
#     - min_intensity: 最小强度阈值，默认 1000.0

#     输出：
#     - .rds: KPIC 完整结果对象
#     - .csv: 通用峰表，可用于解卷积/下游分析
#     """
# )
# async def peak_detection_kpic_tool(
#     input_dir: str,
#     output_dir: str,
#     file_pattern: str = "*.mzML",
#     ppm: float = 10.0,
#     peak_width: float = 10.0,
#     sn_thresh: float = 3.0,
#     min_intensity: float = 1000.0
# ):
#     peak_detection_kpic_impl(
#         input_dir=input_dir,
#         output_dir=output_dir,
#         file_pattern=file_pattern,
#         ppm=ppm,
#         peak_width=peak_width,
#         sn_thresh=sn_thresh,
#         min_intensity=min_intensity
#     )
#     return f"已使用 KPIC 完成峰检测，结果保存为 .rds + .csv，输入目录: {input_dir}, 输出目录: {output_dir}"


# # peakonly
# @mcp.tool(
#     name="peak_detection_peakonly",
#     description="""
#     基于 peakonly 对 LC-MS 代谢组学数据进行峰检测（peak picking）。

#     此工具适用于：
#     - 分析 mzML 文件
#     - 进行质谱数据预处理
#     - 提取色谱峰（feature detection）

#     参数：
#     - input_dir: 输入目录，包含 mzML 文件，文件应包含质心化的 MS1 数据
#     - output_dir: 输出目录，保存峰检测结果
#     - file_pattern: mzML 文件的匹配模式，默认为 "*.mzML"
#     - model_dir: peakonly 模型文件所在目录，默认为 "workspace/models/

#     此工具执行结果：
#     - .csv: 通用峰表，可用于解卷积/下游分析
#     """
# )
# async def peak_detection_peakonly_tool(input_dir: str, output_dir: str, file_pattern: str = "*.mzML", model_dir: str = "workspace/models/"):
#     peak_detection_peakonly_impl(input_dir, output_dir, file_pattern, model_dir)
#     return f"已使用 peakonly 完成峰检测，输入目录: {input_dir}, 输出目录: {output_dir}"



# # ============================= 峰解卷积 =============================



# # ============================= 过滤冗余特征 =============================
# # CAMERA
# @mcp.tool(
#     name="filter_redundant_features_camera",
#     description="""
#     使用 CAMERA 进行冗余特征过滤。

#     工具特点：
#     - 自动识别输入格式：XCMS的.rds格式，OpenMS的.featureXML格式，.csv通用峰表格式
#     - 基于同位素、加合物、碎片的特征关系进行过滤，去除冗余特征
    
#     参数：
#     - input_rds: 输入的 RDS 文件，包含 XCMS 处理后的色谱峰数据
#     - output_rds: 输出的 RDS 文件，保存过滤后的结果

#     输出：
#     - 过滤后的 RDS 文件，包含去除冗余特征后的色谱峰数据
#     """
# )
# async def filter_redundant_features_camera_tool(
#     input_file: str,
#     output_rds: str
# ):
#     filter_redundant_features_camera_impl(input_file, output_rds)
#     return f"已使用 CAMERA 完成冗余特征过滤，输入文件: {input_file}, 输出文件: {output_rds}"


# # RAMClustR
# @mcp.tool(
#     name="filter_redundant_features_ramclustr",
#     description="""
#     使用 RAMClustR 进行冗余特征过滤。
    
#     工具特点：
#     - RAMClustR 基于谱图相关性 + RT 进行特征聚类，去除同位素/加合物/碎片冗余
#     - 自动识别输入格式：XCMS的.rds格式，OpenMS的.featureXML格式，.csv通用峰表格式
    
#     参数：
#     - input_rds: 输入的 .rds/.featureXML/.csv 文件，包含色谱峰数据
#     - output_rds: 输出的 RDS 文件，保存过滤后的结果

#     输出：
#     - 过滤后的 RDS 文件，包含去除冗余特征后的色谱峰数据
#     """
# )
# async def filter_redundant_features_ramclustr_tool(
#     input_rds: str,
#     output_rds: str
# ):
#     filter_redundant_features_ramclustr_impl(input_rds, output_rds)
#     return f"已使用 RAMClustR 完成冗余特征过滤，输入文件: {input_rds}, 输出文件: {output_rds}"


# # mzAnnotation
# @mcp.tool(
#     name="filter_redundant_features_mzannotation",
#     description="""
#     使用 mzAnnotation 进行冗余特征过滤。
    
#     工具特点：
#     - 自动识别输入格式：XCMS的.rds格式，OpenMS的.featureXML格式，.csv通用峰表格式
    
#     参数：
#     - input_rds: 输入的 .rds/.featureXML/.csv 文件，包含色谱峰数据
#     - output_rds: 输出的 RDS 文件，保存过滤后的结果

#     输出：
#     - 过滤后的 RDS 文件，包含去除冗余特征后的色谱峰数据
#     """
# )
# async def filter_redundant_features_mzannotation_tool(
#     input_rds: str,
#     output_rds: str
# ):
#     filter_redundant_features_mzannotation_impl(input_rds, output_rds)
#     return f"已使用 mzAnnotation 完成冗余特征过滤，输入文件: {input_rds}, 输出文件: {output_rds}"



# # ============================= 同位素识别 =============================
# # OpenMS-IsotopeTools
# @mcp.tool(
#     name="identify_isotopes_openms_IsotopeTools",
#     description="""
#     使用 OpenMS-IsotopeTools 进行同位素识别。

#     适用于：
#     - 对已完成峰检测、冗余特征过滤的 LC-MS 代谢组学特征进行同位素标注
#     - 自动识别同一物质的同位素峰簇（M0、M+1、M+2）并分配分组ID

#     局限：
#     - 不做元素组成推断、仅做同位素峰分组
#     - 无法区分同分异构、仅依靠 mz/RT 二维信息

#     参数：
#     - input_rds: 输入的 RDS 文件（已过滤后的特征表）
#     - output_rds: 输出的 RDS 文件，添加了同位素分组注释结果

#     此工具执行结果：
#     - 新增 isotope_group、charge 等同位素注释列
#     - 保留所有原始特征，不删除、不修改原始定量数据
#     """
# )
# async def identify_isotopes_openms_IsotopeTools_tool(
#     input_rds: str,
#     output_rds: str
# ):
#     identify_isotopes_openms_IsotopeTools_impl(input_rds, output_rds)
#     return f"已使用 OpenMS-IsotopeTools 完成同位素识别，输入文件: {input_rds}, 输出文件: {output_rds}"



# # ============================= 保留时间对齐 =============================
# # XCMS-Obiwarp
# @mcp.tool(
#     name="align_retention_time_xcms_obiwarp",
#     description="""
#     基于 XCMS 的 Obiwarp 方法进行保留时间（RT）对齐。

#     此工具适用于：
#     - 对 LC-MS 代谢组学数据进行保留时间对齐
#     - 解决不同样本之间的保留时间差异问题
    
#     参数：
#     - input_rds: 输入的 RDS 文件，包含需要对齐的色谱峰数据
#     - output_rds: 输出的 RDS 文件，保存对齐后的结果

#     此工具执行结果：
#     - 对齐后的 RDS 文件，包含调整保留时间后的色谱峰数据
#     """
# )
# async def align_retention_time_xcms_obiwarp_tool(input_rds: str, output_rds: str):
#     align_retention_time_xcms_obiwarp_impl(input_rds, output_rds)
#     return f"已使用 XCMS_Obiwarp 完成保留时间（RT）对齐，输入文件: {input_rds}, 输出文件: {output_rds}"


# # XCMS-LOESS
# @mcp.tool(
#     name="align_retention_time_xcms_loess",
#     description="""
#     基于 XCMS 的 LOESS 方法进行保留时间（RT）对齐。

#     此工具适用于：
#     - 对 LC-MS 代谢组学数据进行保留时间校正
#     - 使用 LOESS 校正方法调整样本间的保留时间差异
    
#     参数：
#     - input_rds: 输入的 RDS 文件，包含需要校正的色谱峰数据
#     - output_rds: 输出的 RDS 文件，保存校正后的结果

#     此工具执行结果：
#     - 校正后的 RDS 文件，包含调整保留时间后的色谱峰数据
#     """
# )
# async def align_retention_time_xcms_loess_tool(input_rds: str, output_rds: str):
#     align_retention_time_xcms_loess_impl(input_rds, output_rds)
#     return f"已使用 XCMS_LOESS 完成保留时间校正，输入文件: {input_rds}, 输出文件: {output_rds}"



# # ============================= 峰分组（谱峰对齐） =============================
# # XCMS-groupChromPeaks
# @mcp.tool(
#     name="group_peaks_xcms_groupChromPeaks",
#     description="""
#     基于 XCMS 的峰密度分组方法进行特征分组。

#     此工具适用于：
#     - 根据色谱峰的密度进行特征分组
#     - 对于具有多样本的 LC-MS 数据，进行相似特征的合并
    
#     参数：
#     - input_rds: 输入的 RDS 文件，包含已检测到的色谱峰数据
#     - output_rds: 输出的 RDS 文件，保存分组后的结果
#     - groups: 样本组的定义（如果为空，将默认分为一组）
#     - bw: 带宽，默认值为 30
#     - min_fraction: 每个分组中需要至少的最小样本比例，默认值为 0.5
#     - min_samples: 每个分组中最少需要的样本数，默认值为 1

#     此工具执行结果：
#     - 分组后的 RDS 文件，包含分组信息的色谱峰数据
#     """
# )
# async def group_peaks_xcms_groupChromPeaks_tool(
#     input_rds: str,
#     output_rds: str,
#     bw: int,
#     min_fraction: float,
#     min_samples: int,
#     groups: list = None
# ):
#     group_peaks_xcms_groupChromPeaks_impl(input_rds, output_rds, groups, bw, min_fraction, min_samples)
#     return f"已使用 XCMS_groupChromPeaks 完成峰分组，输入文件: {input_rds}, 输出文件: {output_rds}"


# # OpenMS-PeakGroup
# @mcp.tool(
#     name="group_peaks_openms_PeakGroup",
#     description="""
#     基于 OpenMS-PeakGroupFinder 进行多样品谱峰分组与保留时间对齐。

#     此工具适用于：
#     - 对已完成同位素注释的 LC-MS 特征进行跨样本峰对齐
#     - 解决不同样本间 m/z 和保留时间漂移导致的峰不匹配问题
    
#     参数：
#     - input_rds: 输入的 RDS 文件（已完成同位素注释）
#     - output_rds: 输出的 RDS 文件，保存谱峰对齐结果

#     此工具执行结果：
#     - 新增 peak_group（峰组ID）、aligned_rt（对齐后保留时间）列
#     - 同一物质在不同样本中归属为同一组，实现标准化对齐
#     """
# )
# async def group_peaks_openms_PeakGroup_tool(input_rds: str, output_rds: str):
#     group_peaks_openms_PeakGroup_impl(input_rds, output_rds)
#     return f"已使用 OpenMS_PeakGroup 完成谱峰分组与保留时间对齐，输入文件: {input_rds}, 输出文件: {output_rds}"



# # ============================= 缺失峰填充 =============================
# # XCMS-fillChromPeaks
# @mcp.tool(
#     name="fill_missing_peaks_xcms_fillChromPeaks",
#     description="""
#     基于 XCMS 填补缺失的色谱峰数据。

#     此工具适用于：
#     - 填补因噪声或分辨率问题缺失的色谱峰
#     - 基于已知的保留时间和质量信息，填补缺失的数据
    
#     参数：
#     - input_rds: 输入的 RDS 文件，包含检测到的色谱峰数据
#     - output_rds: 输出的 RDS 文件，保存填补后的结果
#     - expand_rt: 允许扩展的保留时间窗口，默认为 0.0
#     - expand_mz: 允许扩展的质量窗口，默认为 0.0

#     此工具执行结果：
#     - 填补后的 RDS 文件，包含原有色谱峰数据以及填补的色谱峰数据
#     """
# )
# async def fill_missing_peaks_xcms_fillChromPeaks_tool(
#     input_rds: str,
#     output_rds: str,
#     expand_rt: float = 0.0,
#     expand_mz: float = 0.0
# ):
#     fill_missing_peaks_xcms_fillChromPeaks_impl(input_rds, output_rds, expand_rt, expand_mz)
#     return f"已使用 XCMS_fillChromPeaks 完成缺失峰填补，输入文件: {input_rds}, 输出文件: {output_rds}"



# # ============================= 库匹配定性 =============================
# # Cosine
# @mcp.tool(
#     name="library_match_cosine",
#     description="""
#     使用 Cosine（余弦相似度）对两个向量进行相似度计算，适用于谱图向量化后的库匹配定性任务。

#     此工具适用于：
#     - 计算查询谱图向量与参考谱图向量之间的相似度
#     - 作为库匹配定性的基础评分函数

#     参数：
#     - query_vector: 查询向量（数值列表）
#     - reference_vector: 参考向量（数值列表）

#     此工具执行结果：
#     - 返回两个向量的余弦相似度分数（范围 [-1, 1]）
#     """
# )
# async def library_match_cosine_tool(
#     query_vector: list[float],
#     reference_vector: list[float]
# ):
#     score = library_match_cosine_impl(query_vector, reference_vector)
#     return f"已完成 Cosine 相似度计算，score={score:.6f}"


# # Jaccard
# @mcp.tool(
#     name="library_match_jaccard",
#     description="""
#     使用 Jaccard 相似度对两个向量进行相似度计算，适用于基于“特征是否出现”的库匹配定性任务。

#     此工具适用于：
#     - 计算查询向量与参考向量的特征重叠程度
#     - 作为二值化特征匹配的基础评分函数

#     参数：
#     - query_vector: 查询向量（数值列表，非零表示该特征出现）
#     - reference_vector: 参考向量（数值列表，非零表示该特征出现）

#     此工具执行结果：
#     - 返回两个向量的 Jaccard 相似度分数（范围 [0, 1]）
#     """
# )
# async def library_match_jaccard_tool(
#     query_vector: list[float],
#     reference_vector: list[float]
# ):
#     score = library_match_jaccard_impl(query_vector, reference_vector)
#     return f"已完成 Jaccard 相似度计算，score={score:.6f}"


# # Spectral entropy
# @mcp.tool(
#     name="library_match_spectral_entropy",
#     description="""
#     使用 Spectral entropy 相似度对两个谱图向量进行匹配，适用于质谱库匹配定性任务。

#     此工具适用于：
#     - 计算查询谱图与参考谱图的谱熵相似度
#     - 作为谱图分布相似性的评分函数

#     参数：
#     - query_vector: 查询向量（数值列表，建议为非负强度）
#     - reference_vector: 参考向量（数值列表，建议为非负强度）

#     此工具执行结果：
#     - 返回两个向量的 Spectral entropy 相似度分数（范围 [0, 1]）
#     """
# )
# async def library_match_spectral_entropy_tool(
#     query_vector: list[float],
#     reference_vector: list[float]
# ):
#     score = library_match_spectral_entropy_impl(query_vector, reference_vector)
#     return f"已完成 Spectral entropy 相似度计算，score={score:.6f}"


# # Spec2Vec
# @mcp.tool(
#     name="library_match_spec2vec",
#     description="""
#     使用 Spec2Vec 嵌入向量进行库匹配定性评分。

#     此工具适用于：
#     - 计算查询谱图与参考谱图的 Spec2Vec 嵌入相似度
#     - 作为深度表示学习驱动的库匹配评分函数

#     参数：
#     - query_embedding: 查询谱图的 Spec2Vec 嵌入向量
#     - reference_embedding: 参考谱图的 Spec2Vec 嵌入向量

#     此工具执行结果：
#     - 返回两个嵌入向量的相似度分数（Cosine）
#     """
# )
# async def library_match_spec2vec_tool(
#     query_embedding: list[float],
#     reference_embedding: list[float]
# ):
#     score = library_match_spec2vec_impl(query_embedding, reference_embedding)
#     return f"已完成 Spec2Vec 相似度计算，score={score:.6f}"


# # MS2DeepScore
# @mcp.tool(
#     name="library_match_ms2deepscore",
#     description="""
#     使用 MS2DeepScore 嵌入向量进行库匹配定性评分。

#     此工具适用于：
#     - 计算查询谱图与参考谱图的 MS2DeepScore 嵌入相似度
#     - 作为深度学习驱动的库匹配评分函数

#     参数：
#     - query_embedding: 查询谱图的 MS2DeepScore 嵌入向量
#     - reference_embedding: 参考谱图的 MS2DeepScore 嵌入向量

#     此工具执行结果：
#     - 返回两个嵌入向量的相似度分数（Cosine）
#     """
# )
# async def library_match_ms2deepscore_tool(
#     query_embedding: list[float],
#     reference_embedding: list[float]
# ):
#     score = library_match_ms2deepscore_impl(query_embedding, reference_embedding)
#     return f"已完成 MS2DeepScore 相似度计算，score={score:.6f}"


# # BLINK
# @mcp.tool(
#     name="library_match_blink",
#     description="""
#     使用 BLINK 风格快速匹配计算两条谱图的相似度。

#     此工具适用于：
#     - 在给定 m/z 容差下进行谱峰快速匹配
#     - 对查询谱图与参考谱图进行快速库匹配打分

#     参数：
#     - query_mz: 查询谱图 m/z 列表
#     - query_intensity: 查询谱图强度列表
#     - reference_mz: 参考谱图 m/z 列表
#     - reference_intensity: 参考谱图强度列表
#     - mz_tolerance: 峰匹配容差（默认 0.01）

#     此工具执行结果：
#     - 返回 BLINK 风格相似度分数（范围 [0, 1]）
#     """
# )
# async def library_match_blink_tool(
#     query_mz: list[float],
#     query_intensity: list[float],
#     reference_mz: list[float],
#     reference_intensity: list[float],
#     mz_tolerance: float = 0.01
# ):
#     score = library_match_blink_impl(query_mz, query_intensity, reference_mz, reference_intensity, mz_tolerance)
#     return f"已完成 BLINK 相似度计算，score={score:.6f}"


# # MS-BERT
# @mcp.tool(
#     name="library_match_msbert",
#     description="""
#     使用 MS-BERT 嵌入向量进行库匹配定性评分。

#     此工具适用于：
#     - 计算查询谱图与参考谱图的 MS-BERT 嵌入相似度
#     - 作为 BERT 表示学习驱动的库匹配评分函数

#     参数：
#     - query_embedding: 查询谱图的 MS-BERT 嵌入向量
#     - reference_embedding: 参考谱图的 MS-BERT 嵌入向量

#     此工具执行结果：
#     - 返回两个嵌入向量的相似度分数（Cosine）
#     """
# )
# async def library_match_msbert_tool(
#     query_embedding: list[float],
#     reference_embedding: list[float]
# ):
#     score = library_match_msbert_impl(query_embedding, reference_embedding)
#     return f"已完成 MS-BERT 相似度计算，score={score:.6f}"
    



# ======================================================================================================================================



# ============================= xcms: data preprocessing =============================
@mcp.tool(
    name="data_preprocessing_xcms",
    description="""
    This tool processes untargeted LC-MS/MS data using XCMS with standard steps: peak picking (centWave), retention time alignment (Obiwarp), peak grouping (PeakDensity), and gap filling. It then performs blank subtraction (ratio-based filtering) and, for the retained features, extracts the best matching MS/MS spectra from the raw data in parallel. The final outputs are a feature quantification table (CSV) and the corresponding MS/MS spectra (MGF), ready for structural annotation with tools like DeepMass.

    Parameters:
    - input_dir: directory containing .mzML files
    - output_dir: path to save feature quantification table (CSV) and corresponding MS/MS spectra (MGF)
    - file_pattern: mzML 文件的匹配模式，默认为 "*.mzML"
    - blank_pattern: 用于识别空白样本的文件名模式，默认为 "Blank"
    - ms2_ppm: MS/MS 匹配的质量精度，默认为 20 ppm
    - ms2_rt_window: MS/MS 匹配的保留时间窗口，默认为 5 秒
    - blank_ratio_threshold: 空白过滤的强度比率阈值，默认为 3
    - n_cores: 并行处理的核心数，默认为 None（使用所有可用核心）
    - ppm: 质量精度，默认为 10 ppm
    - peakwidth: 预期峰宽范围，默认为 (5, 20) 秒
    - snthresh: 信噪比阈值，默认为 10
    - prefilter: 预过滤参数，默认为 (3, 100)，表示至少有 3 个峰且强度至少为 100
    - bin_size: m/z 分箱大小，默认为 0.25
    - center: 峰分组的中心方法，默认为 1（基于质心）
    - bw: 峰分组的带宽，默认为 5
    - min_fraction: 峰分组中至少需要的样本比例，默认为 0.5
    - min_samples: 峰分组中至少需要的样本数，默认为 2

    Notes:
    - The MS2 matching tolerance (ms2_ppm, ms2_rt_window) should reflect your instrument’s accuracy.
    - If no blank samples are detected, the script skips subtraction and uses all features (still filtered by MS2 availability).

    Outputs:
    - feature quantification table (CSV) and the corresponding MS/MS spectra (MGF)，保存在指定输出目录
    """
)
async def data_preprocessing_xcms_tool(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.mzML",
    blank_pattern: str = "Blank",
    ms2_ppm: float = 20,
    ms2_rt_window: float = 5,
    blank_ratio_threshold: float = 3,
    n_cores: int | None = None,
    ppm: float = 10,
    peakwidth: tuple = (5, 20),
    snthresh: float = 10,
    prefilter: tuple = (3, 100),
    bin_size: float = 0.25,
    center: int = 1,
    bw: float = 5,
    min_fraction: float = 0.5,
    min_samples: int = 2
):
    data_preprocessing_xcms_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        file_pattern=file_pattern,
        blank_pattern=blank_pattern,
        ms2_ppm=ms2_ppm,
        ms2_rt_window=ms2_rt_window,
        blank_ratio_threshold=blank_ratio_threshold,
        n_cores=n_cores,
        ppm=ppm,
        peakwidth=peakwidth,
        snthresh=snthresh,
        prefilter=prefilter,
        bin_size=bin_size,
        center=center,
        bw=bw,
        min_fraction=min_fraction,
        min_samples=min_samples
    )
    
    return f"已使用 xcms 完成数据预处理，输入数据为 mzML 文件，输出数据为 feature quantification table (CSV) and corresponding MS/MS spectra (MGF)，输入目录为 {input_dir}, 输出目录为 {output_dir}"



# ============================= feature filtering + KNN imputation =============================
@mcp.tool(
    name="feature_filtering_and_missing_value_imputation_knn",
    description="""
    This tool performs feature-level filtering and KNN-based missing value imputation on metabolomics feature tables.

    Steps:
    1. Filter features based on presence ratio across samples
    2. Filter low-intensity features
    3. Apply KNN imputation to fill missing values

    Input format:
    feature_id,mz,rt_med,sample1,sample2,...

    Parameters:
    - input_csv: input feature table CSV
    - output_csv: output cleaned feature table CSV
    - min_presence: minimum fraction of non-missing values per feature (default 0.5)
    - min_intensity: minimum mean intensity threshold (default 0.0)
    - n_neighbors: number of neighbors for KNN imputation (default 5)

    Outputs:
    - filtered + imputed feature table (CSV)
    - summary text file
    """
)
async def feature_filtering_and_missing_value_imputation_knn_tool(
    input_csv: str,
    output_csv: str,
    min_presence: float = 0.5,
    min_intensity: float = 0.0,
    n_neighbors: int = 5
):
    feature_filtering_and_missing_value_imputation_KNN_impl(
        input_csv=input_csv,
        output_csv=output_csv,
        min_presence=min_presence,
        min_intensity=min_intensity,
        n_neighbors=n_neighbors
    )

    return (
        f"Feature filtering and KNN imputation completed.\n"
        f"Input: {input_csv}\n"
        f"Output: {output_csv}\n"
        f"Parameters: min_presence={min_presence}, min_intensity={min_intensity}, n_neighbors={n_neighbors}"
    )



# ============================= statistical analysis (mixOmics) =============================
@mcp.tool(
    name="statistical_analysis_mixomics",
    description="""
    This tool performs metabolomics statistical analysis using mixOmics in R.

    Workflow:
    - PCA (unsupervised exploration)
    - PLS-DA (supervised classification)
    - Cross-validation (Mfold)
    - VIP score calculation
    - Volcano plot (2-group only)
    - Differential metabolite selection
    - Heatmap of top VIP features

    Input:
    - input_csv: feature table (feature_id,mz,rt_med,samples...)
    - metadata_csv: Sample/Group mapping file
    - output_dir: result directory

    Key outputs:
    - PCA / PLS-DA plots
    - VIP scores
    - differential metabolites
    - volcano plot
    - heatmap of top features
    """
)
async def statistical_analysis_mixomics_tool(
    input_csv: str,
    metadata_csv: str,
    output_dir: str,
    ncomp_pca: int = 5,
    ncomp_plsda: int = 2,
    scale_method: str = "autoscale",
    top_n_heatmap: int = 50,
    seed: int = 123,
    vip_threshold: float = 1.0,
    pvalue_threshold: float = 0.05,
    padj_threshold: float = 0.05,
    log2fc_threshold: float = 1.0,
    use_fdr: bool = True
):
    statistical_analysis_mixomics_impl(
        input_csv=input_csv,
        metadata_csv=metadata_csv,
        output_dir=output_dir,
        ncomp_pca=ncomp_pca,
        ncomp_plsda=ncomp_plsda,
        scale_method=scale_method,
        top_n_heatmap=top_n_heatmap,
        seed=seed,
        vip_threshold=vip_threshold,
        pvalue_threshold=pvalue_threshold,
        padj_threshold=padj_threshold,
        log2fc_threshold=log2fc_threshold,
        use_fdr=use_fdr
    )

    return (
        f"Statistical analysis completed using mixOmics.\n"
        f"Input feature table: {input_csv}\n"
        f"Output directory: {output_dir}"
    )



# ============================= extract differential features =============================
@mcp.tool(
    name="extract_differential_features",
    description="""
    This tool extracts differential metabolite features and their MS/MS spectra.

    Workflow:
    - Read differential_metabolites.csv
    - Filter feature table by selected Feature IDs
    - Extract corresponding MGF spectra blocks

    Inputs:
    - differential_csv: differential metabolite table
    - input_mgf: full MS/MS spectra file (MGF)
    - input_feature_table: full feature table CSV

    Outputs:
    - output_mgf: filtered spectra MGF
    - output_feature_table: filtered feature table CSV
    """
)
async def extract_differential_features_tool(
    differential_csv: str,
    input_mgf: str,
    input_feature_table: str,
    output_mgf: str,
    output_feature_table: str
):
    extract_differential_features_impl(
        differential_csv=differential_csv,
        input_mgf=input_mgf,
        input_feature_table=input_feature_table,
        output_mgf=output_mgf,
        output_feature_table=output_feature_table
    )

    return (
        f"Differential feature extraction completed.\n"
        f"Input differential metabolites: {differential_csv}\n"
        f"Input MGF: {input_mgf}\n"
        f"Input feature table: {input_feature_table}\n"
        f"Output MGF: {output_mgf}\n"
        f"Output feature table: {output_feature_table}"
    )



# ============================= spectral annotation =============================
@mcp.tool(
    name="spectral_annotation",
    description="""
    This tool performs MS/MS spectral annotation using GNPS libraries via R (Spectra + MetaboAnnotation).

    Workflow:
    - Load query spectra (MGF)
    - Load GNPS positive/negative libraries (MSP)
    - Perform cosine similarity matching
    - Merge POS/NEG results
    - Annotate feature table with compound names and scores

    Inputs:
    - mgf_path: query MS/MS spectra
    - feat_csv: feature table CSV
    - output_csv: annotated feature table

    Parameters:
    - precursor_ppm: precursor tolerance in ppm (default 5)
    - fragment_tol: fragment tolerance in Da (default 0.02)
    - min_cosine: minimum similarity score (default 0.7)

    Outputs:
    - annotated feature table CSV
    """
)
async def spectral_annotation_tool(
    mgf_path: str,
    feat_csv: str,
    output_csv: str,
    precursor_ppm: float = 5,
    fragment_tol: float = 0.02,
    min_cosine: float = 0.7
):
    spectral_annotation_impl(
        mgf_path=mgf_path,
        feat_csv=feat_csv,
        output_csv=output_csv,
        precursor_ppm=precursor_ppm,
        fragment_tol=fragment_tol,
        min_cosine=min_cosine
    )

    return (
        f"Spectral annotation completed.\n"
        f"Input MGF: {mgf_path}\n"
        f"Input feature table: {feat_csv}\n"
        f"Output: {output_csv}"
    )




# 用于挂起服务器，而非测试。这段代码的存在是必要的，不能注释掉
if __name__ == "__main__":
    mcp.run(transport="stdio")
    