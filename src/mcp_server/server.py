from mcp.server.fastmcp import FastMCP
import sys as _sys
import builtins as _builtins
import os
import json as _json
import csv as _csv
import glob as _glob

# ——————————————————————————————————————————————————————————
# MCP 协议使用 stdout 传输 JSONRPC 消息。
# 工具函数中的 print() 默认写入 stdout 会污染 MCP 通信通道，
# 导致客户端解析失败（"Failed to parse JSONRPC message"）。
# 这里将全局 print() 默认输出重定向到 stderr，
# FastMCP 内部通过 anyio 原始 fd 写 JSONRPC，不受影响。
# ——————————————————————————————————————————————————————————
_print_original = _builtins.print

def _print(*args, **kwargs):
    kwargs.setdefault("file", _sys.stderr)
    kwargs.setdefault("flush", True)
    _print_original(*args, **kwargs)

_builtins.print = _print
# from src.tools.group_peaks import group_peaks_openms_PeakGroup_impl, group_peaks_xcms_groupChromPeaks_impl
# from src.tools.isotope_annotation import identify_isotopes_openms_IsotopeTools_impl
# from src.tools.mzmine_lcms import mzmine_lcms_datapreprocess_impl
from src.tools.convert_raw_to_mzml import convert_raw_to_mzml_msconvert_impl, convert_raw_to_mzml_ThermoRawFileParser_impl, convert_raw_to_mzml_OpenMS_FileConverter_impl, data_transformation_proteowizard_impl, data_transformation_proteowizard_batch_impl
# from src.tools.peak_detection import peak_detection_kpic_impl, peak_detection_openms_featurefinder_impl, peak_detection_openms_peakpickerhires_impl, peak_detection_xcms_centwave_impl, peak_detection_peakonly_impl
# from src.tools.align_retention_time import align_retention_time_xcms_loess_impl, align_retention_time_xcms_obiwarp_impl
# from src.tools.missing_peak_filling import fill_missing_peaks_xcms_fillChromPeaks_impl
# from src.tools.filter_redundant_features import filter_redundant_features_camera_impl, filter_redundant_features_mzannotation_impl, filter_redundant_features_ramclustr_impl
from src.tools.xcms import data_preprocessing_xcms_impl, extract_differential_features_impl, feature_filtering_and_missing_value_imputation_KNN_impl, kegg_compound_enrich_impl, spectral_annotation_impl, statistical_analysis_mixomics_impl
from src.tools.molecular_networking import molecular_networking_gnps_impl, molecular_networking_fbmn_impl, molecular_networking_ms2lda_impl, molecular_networking_molnetenhancer_impl
from src.tools.MZMine import peak_detection_mzmine_gridmass_impl, data_preprocessing_mzmine_impl, peak_detection_mzmine_adap_impl, align_features_mzmine_joint_aligner_impl
from src.tools.OpenMS import peak_picking_openms_impl, feature_detection_openms_featurefinder_impl, isotope_analysis_openms_impl, peak_group_alignment_openms_impl
from src.tools.openms import data_preprocessing_openms_impl
from src.tools.deepmass import deepmass_annotation_impl
from src.tools.data_preprocessing import data_preprocessing_kpic_impl, data_preprocessing_pitracer_impl, data_preprocessing_tracmass_impl, data_preprocessing_peakonly_impl
from src.tools.redundant_feature_filtering import redundant_feature_filtering_camera_impl, redundant_feature_filtering_ramclust_impl, redundant_feature_filtering_mzannotation_impl, redundant_feature_filtering_pipeline_impl


mcp = FastMCP("MOA_tools")


# ═══════════════════════════════════════════════════════════════════════════════
# 工具返回结构化信息收集器
# ═══════════════════════════════════════════════════════════════════════════════


def _format_tool_result(tool_name, output_dirs, extra_metrics=None):
    """
    在工具 _impl 执行完后调用，扫描输出目录并生成结构化 JSON 返回值。

    收集信息包括：
    - 所有生成的文件列表（路径、大小、是否为空）
    - 各类文件数量统计
    - 摘要文件内容解析
    - 关键 CSV 的行数/列数
    - 空文件/缺失文件告警

    Args:
        tool_name: 工具名称
        output_dirs: 输出目录列表（支持多个目录）
        extra_metrics: 额外指标 dict（工具特有的指标）

    Returns:
        JSON 字符串，包含完整的结构化执行结果
    """
    result = {
        "tool": tool_name,
        "success": True,
        "output_dirs": list(output_dirs),
        "files_created": [],
        "total_files": 0,
        "total_size_bytes": 0,
        "file_type_counts": {},
        "csv_summaries": {},
        "summary_contents": {},
        "metrics": extra_metrics or {},
        "warnings": [],
        "errors": [],
    }

    total_size = 0
    ext_counts = {}

    for output_dir in output_dirs:
        if not isinstance(output_dir, str) or not output_dir.strip():
            continue
        if not os.path.isdir(output_dir):
            result["warnings"].append(f"Output directory not found: {output_dir}")
            continue

        for root, dirs, files in os.walk(output_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                relpath = os.path.relpath(fpath, output_dir)
                try:
                    size = os.path.getsize(fpath)
                except OSError:
                    size = -1

                total_size += max(size, 0)
                ext = os.path.splitext(fname)[1] or "(no ext)"
                ext_counts[ext] = ext_counts.get(ext, 0) + 1

                file_entry = {
                    "path": relpath,
                    "size_bytes": size,
                    "is_empty": size == 0,
                    "directory": output_dir,
                }
                result["files_created"].append(file_entry)

                # — 读取摘要文件 —
                if "summary" in fname.lower() and fname.endswith(".txt"):
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="replace") as sf:
                            result["summary_contents"][relpath] = sf.read()[:3000]
                    except Exception:
                        pass

                # — 解析关键 CSV —
                if fname.endswith(".csv") and size > 0:
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="replace") as cf:
                            reader = _csv.reader(cf)
                            headers = next(reader, [])
                            rows = sum(1 for _ in reader)
                        result["csv_summaries"][relpath] = {
                            "columns": headers[:30],
                            "column_count": len(headers),
                            "row_count": rows,
                        }
                    except Exception:
                        pass

    result["total_files"] = len(result["files_created"])
    result["total_size_bytes"] = total_size
    result["file_type_counts"] = ext_counts

    # — 告警：空输出 —
    if result["total_files"] == 0:
        result["success"] = False
        result["errors"].append("No output files generated")

    # — 告警：空文件 —
    empty_files = [f["path"] for f in result["files_created"] if f["is_empty"]]
    if empty_files:
        result["warnings"].append(f"Zero-byte files: {empty_files}")

    return _json.dumps(result, ensure_ascii=False, indent=2)



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
    return _format_tool_result("convert_raw_to_mzml_ThermoRawFileParser", [output_dir])


# msconvert
@mcp.tool(
    name="convert_raw_to_mzml_msconvert",
    description="""[Category: data_conversion]
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
    return _format_tool_result("convert_raw_to_mzml_msconvert", [output_dir])


# OpenMS FileConverter
@mcp.tool(
    name="convert_raw_to_mzml_OpenMS_FileConverter",
    description="""
    基于 OpenMS 的 FileConverter，支持 mzML/mzXML/mgf 数据格式的互转。

    此工具适用于：
    - 进行质谱数据预处理
    - mzML/mzXML/mgf 数据格式的互转

    参数：
    - input_file: 输入文件路径
    - output_file: 输出文件路径
    - openms_path: OpenMS 可执行文件目录，留空则从系统 PATH 查找

    此工具执行结果：
    - 转换得到的文件保存在指定输出路径
    """
)
async def convert_raw_to_mzml_OpenMS_FileConverter_tool(input_file: str, output_file: str, openms_path: str = ""):
    convert_raw_to_mzml_OpenMS_FileConverter_impl(input_file, output_file, openms_path)
    return _format_tool_result("convert_raw_to_mzml_OpenMS_FileConverter", [os.path.dirname(output_file)])



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



# ============================= 同位素识别 =============================
# OpenMS-IsotopeTools
@mcp.tool(
    name="isotope_analysis_openms",
    description="""
    使用 OpenMS-IsotopeTools 对已完成特征检测的 LC-MS 数据进行同位素峰识别与分组。

    处理流程：
    1. MetaboliteAdductDecharger（内置 MetaboliteFeatureDeconvolution 算法）— 估计每个特征的电荷状态并识别加合物
    2. TextExporter — 将带电荷信息的特征导出为 CSV 格式

    适用场景：
    - 对已完成特征检测（如 FeatureFinderMetabo）的 featureXML 文件进行同位素标注
    - 自动识别同一化合物的同位素峰簇（M0、M+1、M+2 等），基于同位素间 m/z 差值（~1.003 Da）进行分组
    - 非靶向代谢组学流程中，特征检测之后、峰组对齐之前的同位素注释步骤
    - 为后续统计分析和代谢物鉴定提供同位素分组信息

    局限：
    - 仅做同位素峰分组，不做元素组成推断（如 C/H/N/O 原子数估算）
    - 不区分同分异构体，仅依赖 m/z 和 RT 二维信息
    - 需要输入文件已完成特征检测（featureXML 格式），不接受原始 mzML

    参数：
    - input_dir (str): 包含 featureXML 文件的输入目录
    - output_dir (str): 输出目录，所有结果文件将写入此目录
    - file_pattern (str, 默认 "*.featureXML"): 用于匹配输入文件的 glob 模式
    - max_charge (int, 默认 3): 最大电荷数，影响电荷状态估计范围
    - openms_path (str, 默认 ""): OpenMS 可执行文件所在目录路径，留空则使用系统 PATH

    输出文件：
    - *_charged.featureXML: 带电荷状态信息（charge）的特征文件，可直接用于下游 OpenMS 工具
    - *_isotope_annotated.csv: 同位素注释特征表，包含 isotope_group（同位素分组ID）、charge（电荷数）、m/z、RT 等列

    工作流位置：
    特征检测 → 【此工具：同位素分析】 → 峰组对齐
    """
)
async def isotope_analysis_openms_tool(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.featureXML",
    max_charge: int = 3,
    openms_path: str = "",
):
    isotope_analysis_openms_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        file_pattern=file_pattern,
        max_charge=max_charge,
        openms_path=openms_path,
    )
    return _format_tool_result("isotope_analysis_openms", [output_dir])



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
    description="""[Category: data_preprocessing]
    This tool processes untargeted LC-MS/MS data using XCMS with standard steps: peak picking (centWave), retention time alignment (Obiwarp), peak grouping (PeakDensity), and gap filling. It then performs blank subtraction (ratio-based filtering) and, for the retained features, extracts the best matching MS/MS spectra from the raw data in parallel.

    Parameters:
    - input_dir: directory containing .mzML files
    - output_dir: directory to save the output files
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

    Output files (written to output_dir):
    - feature_table.csv — feature quantification table (columns: feature_id, mz, rt_med, and per-sample intensities)
    - spectra.mgf — MS/MS spectra in MGF format, each spectrum’s TITLE matches a feature_id from feature_table.csv
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
    
    return _format_tool_result("data_preprocessing_xcms", [output_dir])



# ============================= feature filtering + KNN imputation =============================
@mcp.tool(
    name="feature_filtering_and_missing_value_imputation_knn",
    description="""[Category: missing_value_imputation]
    This tool performs feature-level filtering and KNN-based missing value imputation on metabolomics feature tables.

    Steps:
    1. Filter features based on presence ratio across samples
    2. Filter low-intensity features
    3. Apply KNN imputation to fill missing values

    Input (auto-detected in order):
    - Reads file: {input_dir}/ramclust_compound_intensities.csv (preferred — output from Stage 3 redundant feature filtering, columns: compound, sample1, sample2, ...)
    - Falls back to: {input_dir}/feature_table.csv (output from data_preprocessing_xcms step, columns: feature_id, mz, rt_med, sample1, sample2, ...)

    Parameters:
    - input_dir: directory containing the input feature table CSV (must contain ramclust_compound_intensities.csv or feature_table.csv)
    - output_dir: directory to save the filtered + imputed feature table and summary
    - min_presence: minimum fraction of non-missing values per feature (default 0.8, "80% rule")
    - min_intensity: minimum mean integrated peak area threshold (default 1000.0; 0 disables)
    - n_neighbors: number of neighbors for KNN imputation (default 5)

    Output files (written to output_dir):
    - feature_table_filtered_imputed.csv — filtered and KNN-imputed feature table
    - feature_filtering_and_missing_value_imputation_summary.txt — filtering statistics
    """
)
async def feature_filtering_and_missing_value_imputation_knn_tool(
    input_dir: str,
    output_dir: str,
    min_presence: float = 0.8,
    min_intensity: float = 1000.0,
    n_neighbors: int = 5
):
    feature_filtering_and_missing_value_imputation_KNN_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        min_presence=min_presence,
        min_intensity=min_intensity,
        n_neighbors=n_neighbors
    )

    return _format_tool_result("feature_filtering_and_missing_value_imputation_knn", [output_dir])



# ============================= statistical analysis (mixOmics) =============================
@mcp.tool(
    name="statistical_analysis_mixomics",
    description="""[Category: statistical_analysis]
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
    - Reads file: {input_dir}/feature_table_filtered_imputed.csv (output from feature_filtering_and_missing_value_imputation_knn step)
    - metadata_csv: full path to sample metadata CSV file (columns: Sample, Group)

    Parameters:
    - input_dir: path to the input directory containing feature_table_filtered_imputed.csv
    - metadata_csv: sample metadata CSV with group labels
    - output_dir: directory to save the statistical analysis results
    - ncomp_pca: number of PCA components (default 5)
    - ncomp_plsda: number of PLS-DA components (default 2)
    - scale_method: data scaling method (default "autoscale")
    - top_n_heatmap: number of top features to show in heatmap (default 50)
    - seed: random seed for reproducibility (default 123)
    - vip_threshold: VIP score threshold for feature selection (default 1.0)
    - pvalue_threshold: p-value threshold for differential analysis (default 0.05)
    - padj_threshold: adjusted p-value threshold (default 0.05)
    - log2fc_threshold: log2 fold change threshold for differential analysis (default 0.58, which corresponds to 1.5-fold change)
    - use_fdr: whether to use FDR correction for p-values (default True)

    Output files (written to output_dir):
    - differential_metabolites.csv — differential metabolites table (Feature, log2FC, pvalue, padj, VIP, mz, rt columns), used as input for extract_differential_features step
    - differential_metabolites_up.csv — upregulated differential features
    - differential_metabolites_down.csv — downregulated differential features
    - differential_summary.txt — count of differential metabolites
    - vip_scores.csv — VIP scores for all features (Feature, VIP columns)
    - vip_gt_1.csv — features with VIP > 1
    - volcano_results.csv — volcano plot data (Feature, log2FC, pvalue, padj, neglog10p, Significant)
    - pca_scores.csv — PCA sample scores
    - pca_plot.png — PCA scores plot
    - plsda_scores.csv — PLS-DA sample scores
    - plsda_plot.png — PLS-DA scores plot
    - plsda_cv_results.txt — PLS-DA cross-validation error rates
    - heatmap_top_vip.png — heatmap of top VIP features
    - sessionInfo.txt — R session info for reproducibility
    """
)
async def statistical_analysis_mixomics_tool(
    input_dir: str,
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
    log2fc_threshold: float = 0.58,
    use_fdr: bool = True
):
    statistical_analysis_mixomics_impl(
        input_dir=input_dir,
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

    return _format_tool_result("statistical_analysis_mixomics", [output_dir])



# ============================= extract differential features =============================
@mcp.tool(
    name="extract_differential_features",
    description="""[Category: statistical_analysis]
    This tool extracts differential metabolite features and their MS/MS spectra.

    Workflow:
    - Read differential_metabolites.csv (from statistical_analysis step)
    - Filter feature table by selected Feature IDs
    - Extract corresponding MGF spectra blocks from the full MGF file

    Parameters:
    - differential_csv: full path to differential metabolite table (typically {statistical_analysis_output_dir}/differential_metabolites.csv)
    - input_mgf: full path to the complete MS/MS spectra MGF file from XCMS preprocessing step (named spectra.mgf in the XCMS output directory, i.e. {xcms_output_dir}/spectra.mgf)
    - output_dir: directory to save extracted differential features files

    Output files (written to output_dir):
    - differential_feature_table.csv — feature table filtered to only differential features
    - differential_spectra.mgf — MGF file containing only spectra of differential features (used as input for spectral_annotation, molecular_networking_gnps, and molecular_networking_fbmn)
    """
)
async def extract_differential_features_tool(
    differential_csv: str,
    input_mgf: str,
    output_dir: str
):
    extract_differential_features_impl(
        differential_csv=differential_csv,
        input_mgf=input_mgf,
        output_dir=output_dir
    )

    return _format_tool_result("extract_differential_features", [output_dir])



# ============================= spectral annotation =============================
@mcp.tool(
    name="spectral_annotation",
    description="""[Category: library_matching]
    This tool performs MS/MS spectral annotation using multiple spectral libraries via R (Spectra + MetaboAnnotation).

    Workflow:
    - Load query spectra (MGF)
    - Search GNPS positive/negative libraries (MSP) + optionally MoNA (MSP) + spectraverse (MGF)
    - Perform cosine similarity matching across all libraries
    - Merge results, keeping the best match per query spectrum
    - Annotate feature table with compound names, SMILES, and KEGG compound IDs

    Input (hardcoded — input_dir must contain these exact filenames):
    - {input_dir}/differential_spectra.mgf — MS/MS spectra of differential features (from extract_differential_features step)
    - {input_dir}/differential_feature_table.csv — differential feature table (from extract_differential_features step)

    Parameters:
    - input_dir: path to the directory containing differential_spectra.mgf and differential_feature_table.csv
    - output_dir: path to the directory saving annotation results CSV files
    - precursor_ppm: precursor tolerance in ppm (default 100)
    - fragment_tol: fragment tolerance in Da (default 0.05)
    - min_cosine: minimum similarity score (default 0.5)
    - include_precursor: if True, require precursor m/z match with parallel processing; default True
    - use_mona: if True, search MoNA libraries (828 MB pos + 246 MB neg); default True
    - use_spectraverse: if True, search spectraverse library (1.3 GB); default True

    Output files (written to output_dir):
    - differential_feature_table_library_match.csv — raw annotation matches
    - differential_feature_table_library_match_clean&add.csv — cleaned annotation table with compound names and scores (used as input for kegg_compound_enrichment and molecular_networking_molnetenhancer)
    """
)
async def spectral_annotation_tool(
    input_dir: str,
    output_dir: str,
    precursor_ppm: float = 100,
    fragment_tol: float = 0.05,
    min_cosine: float = 0.5,
    include_precursor: bool = True,
    use_mona: bool = True,
    use_spectraverse: bool = True
):
    spectral_annotation_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        precursor_ppm=precursor_ppm,
        fragment_tol=fragment_tol,
        min_cosine=min_cosine,
        include_precursor=include_precursor,
        use_mona=use_mona,
        use_spectraverse=use_spectraverse
    )

    return _format_tool_result("spectral_annotation", [output_dir])



# ============================= pathway enrichment analysis =============================
@mcp.tool(
    name="kegg_compound_enrichment",
    description="""[Category: pathway_analysis]
    This tool performs KEGG compound pathway enrichment analysis (ORA-based) using R (clusterProfiler).

    Workflow:
    - Read differential metabolite table (KEGG compound IDs)
    - Automatically supplements missing KEGG IDs via KEGG REST API (in Python layer)
    - Optionally uses mzAnnotation results as supplementary KEGG ID source
    - Load KEGG compound → pathway mapping (local TSV file)
    - Perform over-representation analysis (ORA) using enricher()
    - Generate enrichment result table
    - Generate bubble plot, dotplot, and barplot of top enriched pathways

    Input (hardcoded — input_dir must contain this exact filename):
    - {input_dir}/differential_feature_table_library_match_clean&add.csv — annotated feature table from spectral_annotation step

    Parameters:
    - input_dir: directory containing differential_feature_table_library_match_clean&add.csv (output from spectral_annotation)
    - output_dir: directory to save enrichment results and plots
    - pvalue_cutoff: p-value cutoff for enrichment (default: 0.05)
    - padj_method: multiple testing correction method (default: BH)
    - qvalue_cutoff: q-value cutoff (default: 0.1)
    - min_gs: minimum gene set size (default: 3)
    - max_gs: maximum gene set size (default: 500)
    - top_n: number of top pathways to show in bubble plot (default: 15)
    - mzannotation_dir: optional path to mzAnnotation output for supplementary KEGG ID lookup

    Output files (written to output_dir):
    - kegg_compound_enrich.csv — enrichment result table
    - kegg_compound_bubble.png — bubble plot of top pathways
    - kegg_compound_dotplot.png — dotplot of top pathways
    - kegg_compound_barplot.png — barplot of top pathways
    """
)
async def kegg_compound_enrichment_tool(
    input_dir: str,
    output_dir: str,
    pvalue_cutoff: float = 0.05,
    padj_method: str = "BH",
    qvalue_cutoff: float = 0.1,
    min_gs: int = 3,
    max_gs: int = 500,
    top_n: int = 15,
    mzannotation_dir: str = None
):
    kegg_compound_enrich_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        pvalue_cutoff=pvalue_cutoff,
        padj_method=padj_method,
        qvalue_cutoff=qvalue_cutoff,
        min_gs=min_gs,
        max_gs=max_gs,
        top_n=top_n,
        mzannotation_dir=mzannotation_dir
    )

    return _format_tool_result("kegg_compound_enrichment", [output_dir])



# ============================= GNPS 分子网络 =============================
@mcp.tool(
    name="molecular_networking_gnps",
    description="""[Category: networking]
    GNPS (Global Natural Products Social) classical molecular networking tool.

    This tool builds a molecular network from MS/MS spectra using all-vs-all cosine
    similarity comparison, following the GNPS classical molecular networking method
    (Wang et al., Nature Biotechnology, 2016).

    Workflow:
    - Parse MGF file containing MS/MS spectra (from differential feature extraction step)
    - Compute all-vs-all greedy cosine similarity between spectra
    - Filter edges by minimum cosine score and minimum matched fragment peaks
    - Apply top-K edge filtering per node to reduce network complexity
    - Build molecular network graph using NetworkX
    - Detect connected components as "molecular families"
    - Export GraphML (for Cytoscape), edge table, node table, and summary statistics

    Molecular families can be used for:
    - Annotation propagation: known compounds within a family can aid identification of unknowns
    - Structural analogue discovery: co-clustered metabolites often share core structures
    - Downstream enhanced annotation (MolNetEnhancer)

    Parameters:
    - input_mgf: full path to the MGF file containing differential MS/MS spectra (typically {extract_differential_features_output_dir}/differential_spectra.mgf, i.e. the output of extract_differential_features step)
    - output_dir: directory to save the molecular network and result tables
    - min_cosine: minimum cosine similarity threshold (default 0.7, GNPS standard)
    - min_matched_peaks: minimum number of matched fragment peaks (default 6)
    - fragment_tol: fragment ion mass tolerance in Da (default 0.02, for Orbitrap high-res data)
    - top_k: maximum number of strongest edges to retain per node (default 10)
    - precursor_ppm: precursor ion mass tolerance in ppm for reference only (default 5)

    Output files (written to output_dir):
    - molecular_network.graphml: network graph file (Cytoscape compatible)
    - network_edges.csv: edge table with cosine scores and match statistics (used as input for molecular_networking_molnetenhancer)
    - network_nodes.csv: node table with molecular family assignments (used as input for molecular_networking_molnetenhancer)
    - network_clusters.csv: molecular family summary
    - network_summary.txt: network statistics summary
    - network_topology.png, degree_distribution.png, cosine_distribution.png, etc.
    """
)
async def molecular_networking_gnps_tool(
    input_mgf: str,
    output_dir: str,
    min_cosine: float = 0.7,
    min_matched_peaks: int = 6,
    fragment_tol: float = 0.02,
    top_k: int = 10,
    precursor_ppm: float = 5
):
    molecular_networking_gnps_impl(
        input_mgf=input_mgf,
        output_dir=output_dir,
        min_cosine=min_cosine,
        min_matched_peaks=min_matched_peaks,
        fragment_tol=fragment_tol,
        top_k=top_k,
        precursor_ppm=precursor_ppm
    )

    return _format_tool_result("molecular_networking_gnps", [output_dir])


# ============================= FBMN 特征基分子网络 =============================
@mcp.tool(
    name="molecular_networking_fbmn",
    description="""
    FBMN (Feature-Based Molecular Networking) tool — builds molecular networks
    that integrate MS/MS spectral similarity with quantitative feature information.

    Unlike classic GNPS which uses only MS/MS similarity, FBMN enriches the
    molecular network with quantitative data from the feature table (m/z, RT,
    sample intensities, group means, log2FC). This enables:
    - Identification of co-regulated metabolites within molecular families
    - Edge filtering by intensity profile correlation (Pearson r)
    - Node coloring by quantitative attributes (log2FC, group intensity)

    Reference: Nothias et al. Nature Methods, 2020, 17(9), 905-908.

    Parameters:
    - input_mgf: full path to differential MS/MS spectra MGF file (typically {extract_differential_features_output_dir}/differential_spectra.mgf)
    - input_feature_table: full path to feature quantification table CSV (typically {extract_differential_features_output_dir}/differential_feature_table.csv)
    - output_dir: directory to save FBMN network and result tables
    - metadata_csv: optional sample metadata CSV for group-based statistics (same file as used in statistical_analysis_mixomics)
    - min_cosine: minimum cosine similarity (default 0.7)
    - min_matched_peaks: minimum matched fragment peaks (default 4)
    - fragment_tol: fragment ion mass tolerance in Da (default 0.02)
    - top_k: max edges per node (default 10)
    - min_correlation: minimum Pearson r for intensity profile (default 0.0)

    Output files (written to output_dir):
    - fbmn_network.graphml: network graph with quantitative node attributes
    - fbmn_edges.csv: edge table with cosine + pearson_r scores (used as input for molecular_networking_molnetenhancer)
    - fbmn_nodes.csv: node table with mz, rt, group means, log2FC (used as input for molecular_networking_molnetenhancer)
    - fbmn_clusters.csv: molecular family summary
    - fbmn_summary.txt: network statistics
    """
)
async def molecular_networking_fbmn_tool(
    input_mgf: str,
    input_feature_table: str,
    output_dir: str,
    metadata_csv: str | None = None,
    min_cosine: float = 0.7,
    min_matched_peaks: int = 4,
    fragment_tol: float = 0.02,
    top_k: int = 10,
    min_correlation: float = 0.0,
):
    molecular_networking_fbmn_impl(
        input_mgf=input_mgf,
        input_feature_table=input_feature_table,
        output_dir=output_dir,
        metadata_csv=metadata_csv,
        min_cosine=min_cosine,
        min_matched_peaks=min_matched_peaks,
        fragment_tol=fragment_tol,
        top_k=top_k,
        min_correlation=min_correlation,
    )

    return _format_tool_result("molecular_networking_fbmn", [output_dir])


# ============================= MS2LDA Mass2Motif 发现 =============================
@mcp.tool(
    name="molecular_networking_ms2lda",
    description="""
    MS2LDA (Mass Spectrometry Latent Dirichlet Allocation) tool — discovers
    conserved fragmentation patterns (Mass2Motifs) from MS/MS spectra without
    requiring any spectral library.

    Uses topic modeling (LDA via sklearn) to find co-occurring fragment masses
    across spectra. Each discovered Mass2Motif represents a conserved chemical
    substructure or fragmentation pattern (e.g., sugar loss, amino acid residue,
    fatty acid chain).

    Reference: van der Hooft et al. PNAS, 2016, 113(48), 13738-13743.

    Parameters:
    - input_mgf: path to MS/MS spectra MGF file
    - output_dir: directory to save MS2LDA results
    - n_motifs: number of Mass2Motifs to discover (default 300)
    - fragment_tol: fragment binning tolerance in Da (default 0.005)
    - min_fragment_intensity: minimum relative fragment intensity (default 0.01)
    - n_iterations: LDA training iterations (default 1000)
    - random_seed: random seed for reproducibility (default 42)

    Outputs:
    - mass2motifs.csv: Mass2Motif details with top fragment masses
    - spectra_motif_scores.csv: spectrum × motif probability matrix
    - motif_fragment_distribution.csv: full motif × fragment distribution
    - ms2lda_summary.txt: summary statistics

    Notes:
    - Requires at least 20 spectra for meaningful results
    - n_motifs should be less than the number of spectra
    - Fragment mass differences within a motif often correspond to specific
      chemical transformations (e.g., 162.05 Da = hexose loss)
    """
)
async def molecular_networking_ms2lda_tool(
    input_mgf: str,
    output_dir: str,
    n_motifs: int = 300,
    fragment_tol: float = 0.005,
    min_fragment_intensity: float = 0.01,
    n_iterations: int = 1000,
    random_seed: int = 42,
):
    molecular_networking_ms2lda_impl(
        input_mgf=input_mgf,
        output_dir=output_dir,
        n_motifs=n_motifs,
        fragment_tol=fragment_tol,
        min_fragment_intensity=min_fragment_intensity,
        n_iterations=n_iterations,
        random_seed=random_seed,
    )

    return _format_tool_result("molecular_networking_ms2lda", [output_dir])


# ============================= MolNetEnhancer 增强注释 =============================
@mcp.tool(
    name="molecular_networking_molnetenhancer",
    description="""
    MolNetEnhancer tool — enhances molecular networks by integrating spectral
    library annotations with chemical classification and annotation propagation.

    Workflow:
    - Maps library annotations (compound names) to network nodes
    - Infers chemical categories from compound names (carbohydrates, lipids,
      flavonoids, terpenoids, alkaloids, amino acids/peptides, etc.)
    - Propagates annotations within molecular families: unannotated neighbors
      in the same molecular family inherit the consensus chemical category
    - Outputs an enhanced network ready for Cytoscape visualization

    Reference: Ernst et al. Metabolites, 2019, 9(7), 144.

    Parameters:
    - network_edges_csv: full path to edge table from GNPS/FBMN output (e.g. network_edges.csv or fbmn_edges.csv)
    - network_nodes_csv: full path to node table from GNPS/FBMN output (e.g. network_nodes.csv or fbmn_nodes.csv)
    - annotation_csv: full path to spectral annotation result CSV from spectral_annotation step (specifically the file differential_feature_table_library_match_clean&add.csv)
    - output_dir: directory to save enhanced network and tables
    - annotation_col: column name for compound names in annotation_csv (default "compound_name")
    - id_mapping_csv: optional path to feature_id -> compound_id mapping table. Bridges network node IDs (XCMS feature_id, e.g. FT00073) and annotation IDs (RAMClust compound_id, e.g. C0044). Usually the ramclust_clusters.csv from Stage 3 with columns: feature_id, cluster. If not provided, MolNetEnhancer assumes direct ID match between network nodes and annotation table.

    Output files (written to output_dir):
    - enhanced_network.graphml: network with chemical_category node attributes
    - enhanced_nodes.csv: node table with chemical_category and confidence
    - chemical_class_distribution.csv: chemical class distribution per family
    - annotation_propagation_log.csv: log of propagated annotations
    - molnetenhancer_summary.txt: summary statistics
    - chemical_class_distribution.png, family_chemical_consensus.png, annotation_propagation_summary.png, etc.

    Usage in Cytoscape:
    Open enhanced_network.graphml and map node fill color to
    "chemical_category" column to visualize the chemical class distribution
    across the molecular network.
    """
)
async def molecular_networking_molnetenhancer_tool(
    network_edges_csv: str,
    network_nodes_csv: str,
    annotation_csv: str | None,
    output_dir: str,
    annotation_col: str = "compound_name",
    id_mapping_csv: str | None = None,
):
    molecular_networking_molnetenhancer_impl(
        network_edges_csv=network_edges_csv,
        network_nodes_csv=network_nodes_csv,
        annotation_csv=annotation_csv,
        output_dir=output_dir,
        annotation_col=annotation_col,
        id_mapping_csv=id_mapping_csv,
    )

    return _format_tool_result("molecular_networking_molnetenhancer", [output_dir])


# ======================================================================================================================================

# ============================= ProteoWizard 数据转换 =============================
@mcp.tool(
    name="data_transformation_proteowizard",
    description="""
    Use ProteoWizard (msconvert) to perform complete data transformation pipeline
    on raw mass spectrometry data, supporting format conversion, peak picking
    (centroiding), spectrum filtering, and compression optimization.

    ProteoWizard is the most universal MS data conversion tool in metabolomics,
    supporting nearly all major vendor formats: Thermo (.raw), Agilent (.d),
    Bruker (.d), AB Sciex (.wiff), Waters (.raw), etc.

    Parameters:
    - input_dir: directory containing raw data files
    - output_dir: directory to save converted files
    - input_format: input file format (default .raw)
    - output_format: output file format (default mzML)
    - peak_picking: whether to perform centroiding (default True)
    - peak_picking_algorithm: peak picking algorithm (default "vendor")
    - peak_picking_ms_level: MS levels for peak picking (default "1-")
    - precision_64: use 64-bit precision (default True)
    - srfilter: spectrum filter string, e.g. "activation HCD" for MS2 only
    - file_pattern: file name pattern (default "*")
    - parallel: enable parallel processing (default False)
    - n_cores: number of parallel cores

    Outputs:
    - Converted files in output_dir
    """
)
async def data_transformation_proteowizard_tool(
    input_dir: str,
    output_dir: str,
    input_format: str = ".raw",
    output_format: str = "mzML",
    peak_picking: bool = True,
    peak_picking_algorithm: str = "vendor",
    peak_picking_ms_level: str = "1-",
    ms_level: str | None = None,
    mz_range: str | None = None,
    compression: bool = False,
    zlib_compression: bool = False,
    precision_64: bool = True,
    combine_spectra: bool = False,
    scan_summing: bool = False,
    sim_as_spectra: bool = True,
    srfilter: str | None = None,
    file_pattern: str = "*",
    parallel: bool = False,
    n_cores: int | None = None,
):
    data_transformation_proteowizard_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        input_format=input_format,
        output_format=output_format,
        peak_picking=peak_picking,
        peak_picking_algorithm=peak_picking_algorithm,
        peak_picking_ms_level=peak_picking_ms_level,
        ms_level=ms_level,
        mz_range=mz_range,
        compression=compression,
        zlib_compression=zlib_compression,
        precision_64=precision_64,
        combine_spectra=combine_spectra,
        scan_summing=scan_summing,
        sim_as_spectra=sim_as_spectra,
        srfilter=srfilter,
        file_pattern=file_pattern,
        parallel=parallel,
        n_cores=n_cores,
    )
    return _format_tool_result("data_transformation_proteowizard", [output_dir])


@mcp.tool(
    name="data_transformation_proteowizard_batch",
    description="""
    Batch data transformation: run ProteoWizard conversion pipeline on multiple
    input directories. Each input directory's results are saved in a subdirectory
    with the same name under output_base_dir.

    Parameters:
    - input_dirs: list of input directory paths
    - output_base_dir: output root directory
    - input_format: input file format (default .raw)
    - output_format: output file format (default mzML)
    - peak_picking: whether to perform centroiding (default True)

    Outputs:
    - Converted files in subdirectories under output_base_dir
    """
)
async def data_transformation_proteowizard_batch_tool(
    input_dirs: list[str],
    output_base_dir: str,
    input_format: str = ".raw",
    output_format: str = "mzML",
    peak_picking: bool = True,
):
    data_transformation_proteowizard_batch_impl(
        input_dirs=input_dirs,
        output_base_dir=output_base_dir,
        input_format=input_format,
        output_format=output_format,
        peak_picking=peak_picking,
    )
    return _format_tool_result("data_transformation_proteowizard_batch", [output_base_dir])


# ============================= OpenMS 峰拾取 =============================
@mcp.tool(
    name="peak_picking_openms",
    description="""
    [OpenMS 模块工具 - 步骤 1/4] 使用 OpenMS PeakPickerHiRes 进行高分辨 LC-MS 数据峰拾取（质心化），并自动导出 MGF 谱图。

    PeakPickerHiRes 实现适用于高分辨质谱数据（FT-ICR-MS, Orbitrap）的快速峰检测算法：
    在 profile 模式谱图中检测离子信号，通过样条拟合报告 m/z 和强度。

    ⚠️ 工具选择：
    - 如需完整预处理（峰拾取→特征检测→对齐→分组→导出），请使用 data_preprocessing_openms（一键端到端）
    - 本工具仅做峰拾取 + MGF 导出，适合只需 centroiding 的场景，或作为自定义管线的第一步
    - 后续步骤：feature_detection_openms → isotope_analysis_openms → peak_group_alignment_openms

    Reference: Pfeuffer, J. et al. OpenMS 3 enables reproducible analysis of
    large-scale mass spectrometry data. Nature Methods, 2024.

    Parameters:
    - input_dir: directory containing profile-mode .mzML files
    - output_dir: directory to save centroided .mzML files, peak table CSV, and MGF spectra
    - file_pattern: file name pattern (default "*.mzML")
    - signal_to_noise: signal-to-noise threshold (default 0.0 = auto)
    - spacing_difference_gap: minimum gap between consecutive peaks in raw data
    - spacing_difference: minimum difference between consecutive peaks
    - ms_levels: MS levels to process (None = all)
    - threads: number of threads
    - openms_path: path to OpenMS bin directory (default "" uses system PATH)

    Outputs:
    - Centroided .mzML files in output_dir
    - mgf/*.mgf — 每个样本的 MGF 谱图文件
    - feature_table_peakpicking.csv — 峰表
    """
)
async def peak_picking_openms_tool(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.mzML",
    signal_to_noise: float = 0.0,
    spacing_difference_gap: float = 4.0,
    spacing_difference: float = 1.5,
    missing: int = 1,
    ms_levels: str | None = None,
    threads: int | None = None,
    openms_path: str = "",
):
    peak_picking_openms_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        file_pattern=file_pattern,
        signal_to_noise=signal_to_noise,
        spacing_difference_gap=spacing_difference_gap,
        spacing_difference=spacing_difference,
        missing=missing,
        ms_levels=ms_levels,
        threads=threads,
        openms_path=openms_path,
    )
    return _format_tool_result("peak_picking_openms", [output_dir])


# ============================= OpenMS 特征检测 =============================
@mcp.tool(
    name="feature_detection_openms",
    description="""
    [OpenMS 模块工具 - 步骤 2/4] 使用 OpenMS FeatureFinderMetabo 对已质心化的 LC-MS 数据进行基于质量轨迹的特征检测。

    FeatureFinderMetabo 是 OpenMS 为代谢组学设计的核心特征检测算法：
    - 在 m/z 维度上连接连续的质谱信号，构建质量轨迹（mass traces）
    - 在 RT 维度上检测色谱峰
    - 自动过滤同位素峰、加合物峰和噪声信号
    - 将属于同一化合物的同位素峰组装为特征（feature）

    ⚠️ 工具选择：
    - 如需完整预处理，请使用 data_preprocessing_openms（一键端到端）
    - 本工具仅做特征检测，输入需为已质心化的 mzML（来自 peak_picking_openms）
    - 前置步骤：peak_picking_openms；后续步骤：isotope_analysis_openms → peak_group_alignment_openms

    Parameters:
    - input_dir: directory containing centroided .mzML files
    - output_dir: directory to save .featureXML feature files and per-file feature CSV
    - file_pattern: file name pattern (default "*.mzML")
    - mass_error: mass error in ppm (default 10.0)
    - intensity_threshold: minimum intensity (default 1000.0)
    - min_peak_width: minimum peak width in minutes (default 0.05)
    - max_peak_width: maximum peak width in minutes (default 0.5)
    - snr_threshold: signal-to-noise ratio threshold (default 3.0)
    - threads: number of threads
    - openms_path: path to OpenMS bin directory (default "" uses system PATH)

    Outputs:
    - .featureXML files in output_dir
    - *_features.csv — 每个文件的特征表
    """
)
async def feature_detection_openms_tool(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.mzML",
    mass_error: float = 10.0,
    intensity_threshold: float = 1000.0,
    min_peak_width: float = 0.05,
    max_peak_width: float = 0.5,
    snr_threshold: float = 3.0,
    threads: int | None = None,
    openms_path: str = "",
):
    feature_detection_openms_featurefinder_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        file_pattern=file_pattern,
        mass_error=mass_error,
        intensity_threshold=intensity_threshold,
        min_peak_width=min_peak_width,
        max_peak_width=max_peak_width,
        snr_threshold=snr_threshold,
        threads=threads,
        openms_path=openms_path,
    )
    return _format_tool_result("feature_detection_openms", [output_dir])


# ============================= OpenMS 同位素分析 =============================
@mcp.tool(
    name="isotope_analysis_openms",
    description="""
    [OpenMS 模块工具 - 步骤 3/4] 使用 OpenMS MetaboliteAdductDecharger 对已完成特征检测的数据进行电荷估计与加合物去卷积，识别同位素峰簇。

    该工具识别同一化合物的同位素峰簇（M0, M+1, M+2 等），基于特征间 m/z 差和加合物/电荷模型进行匹配。

    ⚠️ 工具选择：
    - 如需完整预处理，请使用 data_preprocessing_openms（一键端到端）
    - 本工具仅做同位素分析，输入需为 .featureXML 文件（来自 feature_detection_openms）
    - 前置步骤：peak_picking_openms → feature_detection_openms；后续步骤：peak_group_alignment_openms

    Parameters:
    - input_dir: directory containing .featureXML files from feature detection
    - output_dir: directory to save isotope analysis results
    - file_pattern: glob pattern to match input files (default "*.featureXML")
    - max_charge: maximum charge state to consider (default 3)
    - openms_path: path to OpenMS bin directory (default "" uses system PATH)

    Outputs:
    - *_charged.featureXML — 带电荷信息的特征文件
    - *_isotope_annotated.csv — 同位素注释特征表
    """
)
async def isotope_analysis_openms_tool(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.featureXML",
    max_charge: int = 3,
):
    isotope_analysis_openms_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        file_pattern=file_pattern,
        max_charge=max_charge,
    )
    return _format_tool_result("isotope_analysis_openms", [output_dir])


# ============================= OpenMS 峰组对齐 =============================
@mcp.tool(
    name="peak_group_alignment_openms",
    description="""
    [OpenMS 模块工具 - 步骤 4/4] 使用 OpenMS 工具链对多样本 LC-MS 特征进行保留时间对齐和跨样本峰组链接。

    处理流程：
    1. MapAlignerPoseClustering — 基于 PoseClustering 算法的 RT 对齐
    2. FeatureLinkerUnlabeled — 基于 m/z 和 RT 相似度的跨样本特征分组
    3. TextExporter — 导出合并定量峰表 CSV

    ⚠️ 工具选择：
    - 如需完整预处理，请使用 data_preprocessing_openms（一键端到端，内部包含本步骤）
    - 本工具是模块管线的最后一步，输入需为 .featureXML 文件
    - 前置步骤：peak_picking_openms → feature_detection_openms → (可选) isotope_analysis_openms → 本工具

    Parameters:
    - input_dir: directory containing .featureXML files
    - output_dir: directory to save alignment results
    - file_pattern: file name pattern (default "*.featureXML")
    - rt_max_difference: max RT difference for initial grouping (default 100.0 s)
    - mz_max_difference: max m/z difference for grouping (default 0.3 Da)
    - aligner_rt_max_difference: max RT difference for alignment (default 100.0 s)
    - aligner_mz_max_difference: max m/z difference for alignment (default 0.3 Da)
    - threads: number of threads
    - openms_path: path to OpenMS bin directory (default "" uses system PATH)

    Outputs:
    - feature_table_peakgroup.csv — 合并定量峰表
    - consensus_map.consensusXML — 共识特征图
    - aligned/*.featureXML — 对齐后的特征文件
    - trafo/*.trafoXML — RT 变换参数
    """
)
async def peak_group_alignment_openms_tool(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.featureXML",
    rt_max_difference: float = 100.0,
    mz_max_difference: float = 0.3,
    mz_unit: str = "Da",
    aligner_rt_max_difference: float = 100.0,
    aligner_mz_max_difference: float = 0.3,
    aligner_mz_unit: str = "Da",
    ignore_charge: bool = False,
    threads: int | None = None,
    openms_path: str = "",
):
    peak_group_alignment_openms_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        file_pattern=file_pattern,
        rt_max_difference=rt_max_difference,
        mz_max_difference=mz_max_difference,
        mz_unit=mz_unit,
        aligner_rt_max_difference=aligner_rt_max_difference,
        aligner_mz_max_difference=aligner_mz_max_difference,
        aligner_mz_unit=aligner_mz_unit,
        ignore_charge=ignore_charge,
        threads=threads,
        openms_path=openms_path,
    )
    return _format_tool_result("peak_group_alignment_openms", [output_dir])


# ============================= OpenMS 端到端全流程数据预处理 =============================
@mcp.tool(
    name="data_preprocessing_openms",
    description="""[Category: data_preprocessing]

    🔥 OpenMS 端到端全流程（ALL-IN-ONE）：一步完成从原始 mzML 到定量峰表 + MGF 谱图的完整预处理。

    ⚡ 一键式管线，自动串联以下步骤：
    1. PeakPickerHiRes — 高分辨峰检测（质心化）
    2. FileConverter — 将质心化 mzML 转为 MGF 谱图文件（每样本一个 .mgf）
    3. FeatureFinderMetabo — 代谢组特征检测（质量轨迹 + 色谱峰）
    4. MapAlignerPoseClustering — 多样本保留时间对齐
    5. FeatureLinkerUnlabeledQT — 跨样本特征链接（共识分组）
    6. TextExporter — 导出合并定量峰表 CSV

    ⚠️ 工具选择指南（重要）：
    ┌──────────────────────────────────────────────────────────────────┐
    │ 需求场景                                  → 选用工具             │
    ├──────────────────────────────────────────────────────────────────┤
    │ 完整预处理，一步出结果                     → data_preprocessing_openms（本工具）│
    │ 只需峰拾取（centroiding）+ MGF            → peak_picking_openms  │
    │ 只需特征检测（需已质心化的 mzML）           → feature_detection_openms │
    │ 只需同位素注释（需 featureXML）            → isotope_analysis_openms │
    │ 只需 RT 对齐 + 峰分组（需 featureXML）     → peak_group_alignment_openms │
    │ 自定义管线，逐步精细控制                   → 按序调用上述模块工具   │
    └──────────────────────────────────────────────────────────────────┘

    💡 本工具 vs OpenMS 模块工具：
    - data_preprocessing_openms（本工具）：bash 脚本一次性执行，固定参数少，适合标准流程快速出结果。输出 feature_table.csv + mgf/ 目录。
    - peak_picking_openms / feature_detection_openms / isotope_analysis_openms / peak_group_alignment_openms：Python 子进程逐步调用，每步独立、参数完整、有 docstring、有错误恢复。适合需要精细控制每个步骤参数的场景。

    参数：
    - input_dir (str): 输入目录，包含原始 .mzML 文件
    - output_dir (str): 输出目录，所有结果文件将写入此目录
    - threads (int, 默认 4): 并行线程数
    - mass_error_ppm (float, 默认 10.0): 质量容差（ppm），用于 FeatureFinderMetabo
    - openms_path (str, 默认 ""): OpenMS 可执行文件目录路径（如 "/home/user/anaconda/envs/openms_env/bin"），留空则使用系统 PATH

    输出文件（写入 output_dir）：
    - feature_table.csv — 合并后的定量峰表（所有样本的共识特征）
    - mgf/*.mgf — 每个样本的 MS/MS 谱图文件（可用于 GNPS/FBMN 分子网络、库匹配等下游分析）
    - mzML_centroid/*.mzML — 质心化后的中间文件
    - featureXML/*.featureXML — 特征检测中间文件
    - consensus/consensus.consensusXML — 共识特征图
    """
)
async def data_preprocessing_openms_tool(
    input_dir: str,
    output_dir: str,
    threads: int = 4,
    mass_error_ppm: float = 10.0,
    openms_path: str = "",
):
    data_preprocessing_openms_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        threads=threads,
        mass_error_ppm=mass_error_ppm,
        openms_path=openms_path,
    )
    return _format_tool_result("data_preprocessing_openms", [output_dir])


# ============================= MZmine 峰检测 (GridMass) =============================
@mcp.tool(
    name="peak_detection_mzmine_gridmass",
    description="""
    Use MZmine 3 GridMass algorithm for 2D peak detection on LC-MS data.

    GridMass is a grid-probe-based feature detection algorithm:
    - Places a uniform probe grid across the 2D chromatographic space (m/z x RT)
    - Each probe searches for local maxima in a local rectangular region
    - Probes converging to the same maximum are merged into one feature
    - Merged probes define m/z and time boundaries of the feature

    Suitable for high-resolution LC-MS untargeted metabolomics data.

    Parameters:
    - input_dir: directory containing .mzML files
    - output_dir: directory to save peak detection results
    - file_pattern: file name pattern (default "*.mzML")
    - ms_level: MS level for peak detection (default 1)
    - min_height: minimum peak height (default 1000.0)
    - mz_tolerance: m/z tolerance for merging (default 10.0 ppm)
    - min_peak_width: minimum peak width in minutes (default 0.05)
    - max_peak_width: maximum peak width in minutes (default 2.0)
    - threads: number of threads
    - mzuser_file: path to .mzuser file for MZmine.io authentication (required for GridMass + CSV export in MZmine 4.7+)

    Outputs:
    - Peak detection results in output_dir
    """
)
async def peak_detection_mzmine_gridmass_tool(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.mzML",
    ms_level: int = 1,
    min_height: float = 1000.0,
    mz_tolerance: float = 10.0,
    min_peak_width: float = 0.05,
    max_peak_width: float = 2.0,
    threads: int | None = None,
    mzuser_file: str | None = None,
):
    peak_detection_mzmine_gridmass_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        file_pattern=file_pattern,
        ms_level=ms_level,
        min_height=min_height,
        mz_tolerance=mz_tolerance,
        min_peak_width=min_peak_width,
        max_peak_width=max_peak_width,
        threads=threads,
        mzmine_user=mzuser_file,
    )
    return _format_tool_result("peak_detection_mzmine_gridmass", [output_dir])


# ============================= MZmine 峰检测 (ADAP) =============================
@mcp.tool(
    name="peak_detection_mzmine_adap",
    description="""
    Use MZmine 3 ADAP algorithm for advanced chromatographic peak detection.

    ADAP (Automated Data Analysis Pipeline) uses a two-step approach:
    1. Chromatogram Builder: connects consecutive scans to build EICs
    2. ADAP Resolver: resolves overlapping peaks using wavelet-based methods

    Suitable for complex LC-MS datasets with co-eluting compounds.

    Parameters:
    - input_dir: directory containing .mzML files
    - output_dir: directory to save peak detection results
    - file_pattern: file name pattern (default "*.mzML")
    - ms1_noise_level: MS1 noise level (default 1000.0)
    - ms2_noise_level: MS2 noise level (default 100.0)
    - min_consecutive_scans: minimum consecutive scans for EIC (default 5)
    - sn_threshold: signal-to-noise threshold (default 10.0)
    - min_feature_height: minimum feature height (default 10000.0)
    - peak_duration_min: minimum peak duration in minutes (default 0.01)
    - peak_duration_max: maximum peak duration in minutes (default 10.0)
    - mzuser_file: path to .mzuser file for MZmine.io authentication (required for Feature Resolver + CSV export in MZmine 4.7+)

    Outputs:
    - Peak detection results in output_dir
    """
)
async def peak_detection_mzmine_adap_tool(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.mzML",
    ms1_noise_level: float = 1000.0,
    ms2_noise_level: float = 100.0,
    min_consecutive_scans: int = 5,
    sn_threshold: float = 10.0,
    min_feature_height: float = 10000.0,
    peak_duration_min: float = 0.01,
    peak_duration_max: float = 10.0,
    threads: int | None = None,
    mzuser_file: str | None = None,
):
    peak_detection_mzmine_adap_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        file_pattern=file_pattern,
        ms1_noise_level=ms1_noise_level,
        ms2_noise_level=ms2_noise_level,
        min_consecutive_scans=min_consecutive_scans,
        sn_threshold=sn_threshold,
        min_feature_height=min_feature_height,
        peak_duration_min=peak_duration_min,
        peak_duration_max=peak_duration_max,
        threads=threads,
        mzmine_user=mzuser_file,
    )
    return _format_tool_result("peak_detection_mzmine_adap", [output_dir])


# ============================= MZmine 全流程数据预处理 =============================
@mcp.tool(
    name="data_preprocessing_mzmine",
    description="""
    MZmine complete LC-MS untargeted metabolomics data preprocessing pipeline.

    Workflow: peak detection (GridMass) -> RT alignment -> peak grouping -> gap filling

    Parameters:
    - input_dir: directory containing .mzML files
    - output_dir: directory to save preprocessing results
    - file_pattern: file name pattern (default "*.mzML")
    - ms1_noise_level: MS1 noise level (default 1000.0)
    - min_height: minimum peak height (default 1000.0)
    - mz_tolerance: m/z tolerance in ppm (default 10.0)
    - min_peak_width: minimum peak width in minutes (default 0.05)
    - max_peak_width: maximum peak width in minutes (default 2.0)
    - rt_tolerance: RT tolerance for alignment (default 0.2 min)
    - group_mz_tol: m/z tolerance for grouping (default 0.01)
    - group_rt_tol: RT tolerance for grouping (default 0.2 min)
    - mzuser_file: path to .mzuser file for MZmine.io authentication (required for GridMass + CSV export in MZmine 4.7+)

    Outputs:
    - Complete feature quantification table ready for statistical analysis
    """
)
async def data_preprocessing_mzmine_tool(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.mzML",
    ms1_noise_level: float = 1000.0,
    ms2_noise_level: float = 100.0,
    min_height: float = 1000.0,
    mz_tolerance: float = 10.0,
    min_peak_width: float = 0.05,
    max_peak_width: float = 2.0,
    rt_tolerance: float = 0.2,
    mz_tol_align: float = 0.01,
    group_mz_tol: float = 0.01,
    group_rt_tol: float = 0.2,
    mzuser_file: str | None = None,
):
    data_preprocessing_mzmine_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        file_pattern=file_pattern,
        ms1_noise_level=ms1_noise_level,
        ms2_noise_level=ms2_noise_level,
        min_height=min_height,
        mz_tolerance=mz_tolerance,
        min_peak_width=min_peak_width,
        max_peak_width=max_peak_width,
        rt_tolerance=rt_tolerance,
        mz_tol_align=mz_tol_align,
        group_mz_tol=group_mz_tol,
        group_rt_tol=group_rt_tol,
        mzmine_user=mzuser_file,
    )
    return _format_tool_result("data_preprocessing_mzmine", [output_dir])


# ============================= MZmine Join Aligner 特征对齐 =============================
@mcp.tool(
    name="align_features_mzmine_joint_aligner",
    description="""
    Use MZmine 3 Join Aligner for cross-sample feature alignment.

    The Join Aligner matches features across samples based on m/z and RT similarity
    with weighted scoring, creating a unified aligned feature table.

    Parameters:
    - input_dir: directory containing .mzML files
    - output_dir: directory to save alignment results
    - file_pattern: file name pattern (default "*.mzML")
    - align_mz_tol: m/z tolerance for alignment (default 0.01)
    - align_rt_tol: RT tolerance for alignment in min (default 0.5)
    - weight_mz: weight for m/z in scoring (default 5.0)
    - weight_rt: weight for RT in scoring (default 1.0)
    - require_same_charge: require same charge state for matching (default False)
    - threads: number of threads
    - mzuser_file: path to .mzuser file for MZmine.io authentication (required for GridMass + CSV export in MZmine 4.7+)

    Outputs:
    - Aligned feature table in output_dir
    """
)
async def align_features_mzmine_joint_aligner_tool(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.mzML",
    ms1_noise_level: float = 1000.0,
    min_height: float = 1000.0,
    mz_tolerance: float = 10.0,
    min_peak_width: float = 0.05,
    max_peak_width: float = 2.0,
    align_mz_tol: float = 0.01,
    align_rt_tol: float = 0.5,
    weight_mz: float = 5.0,
    weight_rt: float = 1.0,
    require_same_charge: bool = False,
    threads: int | None = None,
    mzuser_file: str | None = None,
):
    align_features_mzmine_joint_aligner_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        file_pattern=file_pattern,
        ms1_noise_level=ms1_noise_level,
        min_height=min_height,
        mz_tolerance=mz_tolerance,
        min_peak_width=min_peak_width,
        max_peak_width=max_peak_width,
        align_mz_tol=align_mz_tol,
        align_rt_tol=align_rt_tol,
        weight_mz=weight_mz,
        weight_rt=weight_rt,
        require_same_charge=require_same_charge,
        threads=threads,
        mzmine_user=mzuser_file,
    )
    return _format_tool_result("align_features_mzmine_joint_aligner", [output_dir])


# ============================= DeepMASS2 深度学习注释 =============================
@mcp.tool(
    name="deepmass_annotation",
    description="""
    Use DeepMASS2 for deep learning-based annotation of differential metabolite spectra.

    Unlike spectral_annotation (which uses GNPS library cosine matching and only
    identifies known compounds), this tool uses Spec2Vec semantic similarity search
    to predict structurally related candidate metabolites for completely unknown
    compounds.

    Parameters:
    - input_dir: directory containing differential_spectra.mgf file
    - output_dir: directory to save annotation result CSV files

    Outputs:
    - One CSV file per query spectrum containing: Title, MolecularFormula,
      CanonicalSMILES, InChIKey, Formula Score, Structure Score, Consensus Score, DeepMASS_raw
    """
)
async def deepmass_annotation_tool(
    input_dir: str,
    output_dir: str,
):
    deepmass_annotation_impl(
        input_dir=input_dir,
        output_dir=output_dir,
    )
    return _format_tool_result("deepmass_annotation", [output_dir])


# ============================= KPIC 基于核函数的峰检测 =============================
@mcp.tool(
    name="data_preprocessing_kpic",
    description="""
    Use KPIC (Kernel-based Peak Identification) for LC-MS metabolomics peak detection featuring pure ion chromatogram (PIC) extraction and kernel density smoothing.

    KPIC uses a tracking algorithm to extract pure ion chromatograms (PICs) rather than traditional EICs, which reduces isotope and adduct interference. Gaussian kernel smoothing is applied before peak detection via first-derivative zero-crossing.

    Characteristics:
    - More robust against noise and matrix effects compared to fixed-window methods
    - PICs are cleaner than EICs — fewer split peaks from isotopes and adducts
    - Suitable for complex matrices (serum, plant, microbial samples)

    Reference: Ji et al. "KPIC2: An effective framework for mass spectrometry-based metabolomics using pure ion chromatograms." Analytical Chemistry, 2017.

    Parameters:
    - input_dir: directory containing .mzML files
    - output_dir: directory to save peak detection results
    - file_pattern: file matching pattern (default "*.mzML")
    - ppm: mass accuracy in ppm for PIC m/z tolerance (default 10.0)
    - peak_width: expected peak width range in seconds (default 10.0)
    - sn_thresh: signal-to-noise ratio threshold (default 3.0)
    - min_intensity: minimum intensity threshold (default 1000.0)
    - min_scans: minimum consecutive scans for a valid PIC (default 5)
    - kernel_sigma: Gaussian kernel sigma for smoothing (default 2.0)

    Outputs:
    - CSV peak tables for each sample
    - merged peak table (all_peak_table.csv, all_peaks.csv)
    - summary statistics (kpic_summary.txt)
    """
)
async def data_preprocessing_kpic_tool(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.mzML",
    ppm: float = 10.0,
    peak_width: float = 10.0,
    sn_thresh: float = 3.0,
    min_intensity: float = 1000.0,
    min_scans: int = 5,
    kernel_sigma: float = 2.0,
):
    data_preprocessing_kpic_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        file_pattern=file_pattern,
        ppm=ppm,
        peak_width=peak_width,
        sn_thresh=sn_thresh,
        min_intensity=min_intensity,
        min_scans=min_scans,
        kernel_sigma=kernel_sigma,
    )
    return _format_tool_result("data_preprocessing_kpic", [output_dir])


# ============================= PITracer 纯离子示踪 =============================
@mcp.tool(
    name="data_preprocessing_pitracer",
    description="""
    Use PITracer (Pure Ion Tracer) algorithm for pure ion chromatogram extraction and peak detection in LC/TOF-MS metabolomics data.

    PITracer automatically estimates the relative mass difference tolerance from the data distribution, detects continuous "pure" ion traces in both m/z and RT dimensions, and filters out short/isolated ion traces (noise). It handles saturated peaks by applying a higher mass tolerance, preventing split peaks.

    Key advantages:
    - Auto-estimates mass tolerance — no manual ppm tuning needed
    - Correctly detects saturated peaks without generating split peaks
    - High recall (>99% with mass calibration) and precision
    - Handles ion suppression and matrix effects well

    Reference: Wang et al. "Ion Trace Detection Algorithm to Extract Pure Ion Chromatograms to Improve Untargeted Peak Detection Quality for LC/TOF-MS Based Metabolomics Data." Analytical Chemistry, 2015, 87, 3048–3055.

    Parameters:
    - input_dir: directory containing .mzML files
    - output_dir: directory to save peak detection results
    - file_pattern: file matching pattern (default "*.mzML")
    - min_trace_length: minimum consecutive scans for pure ion trace (default 5, ~2.5s)
    - min_intensity: minimum intensity threshold (default 1000.0)
    - saturation_intensity: intensity threshold for saturation detection (default 1,000,000)
    - saturation_mz_tol_factor: tolerance multiplier for saturated peaks (default 4.0)
    - mass_calibration_mz: optional reference metabolite m/z for mass calibration
    - sn_threshold: signal-to-noise ratio threshold (default 3.0)
    - min_peak_width: minimum peak width in seconds (default 2.5)
    - max_peak_width: maximum peak width in seconds (default 60.0)

    Outputs:
    - CSV peak tables for each sample
    - pure ion trace summaries (CSV)
    - merged peak table (all_peak_table.csv, all_peaks.csv)
    - summary statistics (pitracer_summary.txt)
    """
)
async def data_preprocessing_pitracer_tool(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.mzML",
    min_trace_length: int = 5,
    min_intensity: float = 1000.0,
    saturation_intensity: float = 1e6,
    saturation_mz_tol_factor: float = 4.0,
    mass_calibration_mz: float | None = None,
    sn_threshold: float = 3.0,
    min_peak_width: float = 2.5,
    max_peak_width: float = 60.0,
):
    data_preprocessing_pitracer_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        file_pattern=file_pattern,
        min_trace_length=min_trace_length,
        min_intensity=min_intensity,
        saturation_intensity=saturation_intensity,
        saturation_mz_tol_factor=saturation_mz_tol_factor,
        mass_calibration_mz=mass_calibration_mz,
        sn_threshold=sn_threshold,
        min_peak_width=min_peak_width,
        max_peak_width=max_peak_width,
    )
    return _format_tool_result("data_preprocessing_pitracer", [output_dir])


# ============================= TracMass 追踪算法峰检测 =============================
@mcp.tool(
    name="data_preprocessing_tracmass",
    description="""
    Use TracMass trace-based peak detection algorithm for LC-MS/GC-MS data. Modular processing with PIC tracking and dual zero-area filter convolution.

    TracMass uses a greedy nearest-neighbor tracking algorithm to extract pure ion chromatograms (PICs). Each PIC is then convolved with two zero-area filters of different widths (narrow and wide), combining the maximum response from both to detect peaks. Noise is estimated as the difference between the PIC and its Gaussian-smoothed version.

    Characteristics:
    - Modular design — each processing step can be independently tuned
    - Dual-filter approach catches both narrow and wide peaks
    - O(N log N) complexity — processes large files quickly
    - Transparent visual diagnostics (peak detection can be verified per chromatogram)
    - m/z tolerance model can scale with m/z^(1/2) for better low-mass accuracy

    Reference: Tengstrand et al. "TracMass 2—A Modular Suite of Tools for Processing Chromatography-Full Scan Mass Spectrometry Data." Analytical Chemistry, 2014, 86, 3435–3442.

    Parameters:
    - input_dir: directory containing .mzML files
    - output_dir: directory to save peak detection results
    - file_pattern: file matching pattern (default "*.mzML")
    - mz_tol_ppm: m/z tolerance for PIC tracking in ppm (default 10.0)
    - min_trace_length: minimum PIC length in scans (default 8)
    - narrow_filter_width: narrow zero-area filter width in data points (default 3.0)
    - wide_filter_width: wide zero-area filter width in data points (default 9.0)
    - min_intensity: minimum intensity threshold (default 1000.0)
    - sn_threshold: signal-to-noise ratio threshold (default 3.0)
    - min_peak_width: minimum peak width in seconds (default 3.0)
    - max_peak_width: maximum peak width in seconds (default 60.0)

    Outputs:
    - CSV peak tables for each sample
    - merged peak table (all_peak_table.csv, all_peaks.csv)
    - summary statistics (tracmass_summary.txt)
    """
)
async def data_preprocessing_tracmass_tool(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.mzML",
    mz_tol_ppm: float = 10.0,
    min_trace_length: int = 8,
    narrow_filter_width: float = 3.0,
    wide_filter_width: float = 9.0,
    min_intensity: float = 1000.0,
    sn_threshold: float = 3.0,
    min_peak_width: float = 3.0,
    max_peak_width: float = 60.0,
):
    data_preprocessing_tracmass_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        file_pattern=file_pattern,
        mz_tol_ppm=mz_tol_ppm,
        min_trace_length=min_trace_length,
        narrow_filter_width=narrow_filter_width,
        wide_filter_width=wide_filter_width,
        min_intensity=min_intensity,
        sn_threshold=sn_threshold,
        min_peak_width=min_peak_width,
        max_peak_width=max_peak_width,
    )
    return _format_tool_result("data_preprocessing_tracmass", [output_dir])


# ============================= PeakOnly 深度学习峰检测 =============================
@mcp.tool(
    name="data_preprocessing_peakonly",
    description="""
    Use PeakOnly deep learning-based peak detection for high-resolution LC-MS metabolomics data. Employs CNN models for ROI classification (noise/peak/uncertain) and peak boundary integration.

    PeakOnly uses two convolutional neural networks: one for classifying Regions of Interest (ROIs) into noise, peaks, or uncertain peaks, and a U-Net style network for determining precise peak boundaries and integration limits. When the deep learning model is unavailable, it falls back to a traditional heuristic classification based on peak shape features.

    Characteristics:
    - Reported ~97% precision — very low false positive rate compared to XCMS/MZmine
    - Deep learning automatically learns peak features — minimal manual parameter tuning
    - Processes ~2 minutes per sample
    - Works with centroided MS1 data (.mzML format)

    Reference: Melnikov et al. "Deep Learning for the Precise Peak Detection in High-Resolution LC-MS Data." Analytical Chemistry, 2020, 92, 588–592.

    Parameters:
    - input_dir: directory containing centroided .mzML files
    - output_dir: directory to save peak detection results
    - file_pattern: file matching pattern (default "*.mzML")
    - model_dir: directory containing peakonly model files (default: auto-detect)
    - ppm: mass accuracy in ppm for ROI m/z tolerance (default 10.0)
    - min_intensity: minimum intensity threshold (default 1000.0)
    - min_scans: minimum consecutive scans for ROI (default 5)
    - sn_threshold: signal-to-noise ratio threshold (default 2.0)
    - min_peak_width: minimum peak width in seconds (default 3.0)
    - max_peak_width: maximum peak width in seconds (default 60.0)
    - use_deep_learning: whether to use deep learning model (default True; falls back to heuristic if unavailable)

    Outputs:
    - CSV peak tables for each sample
    - ROI classification records (roi_classifications.csv)
    - merged peak table (all_peak_table.csv, all_peaks.csv)
    - summary statistics (peakonly_summary.txt)
    """
)
async def data_preprocessing_peakonly_tool(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.mzML",
    model_dir: str | None = None,
    ppm: float = 10.0,
    min_intensity: float = 1000.0,
    min_scans: int = 5,
    sn_threshold: float = 2.0,
    min_peak_width: float = 3.0,
    max_peak_width: float = 60.0,
    use_deep_learning: bool = True,
):
    data_preprocessing_peakonly_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        file_pattern=file_pattern,
        model_dir=model_dir,
        ppm=ppm,
        min_intensity=min_intensity,
        min_scans=min_scans,
        sn_threshold=sn_threshold,
        min_peak_width=min_peak_width,
        max_peak_width=max_peak_width,
        use_deep_learning=use_deep_learning,
    )
    return _format_tool_result("data_preprocessing_peakonly", [output_dir])


# ============================= CAMERA 冗余特征过滤 =============================
@mcp.tool(
    name="redundant_feature_filtering_camera",
    description="""
    Use CAMERA (Collection of Algorithms for MEtabolite pRofile Annotation) for redundant feature filtering and annotation of LC-MS metabolomics data.

    CAMERA annotates isotope peaks, adducts, and in-source fragments by grouping co-eluting signals into pseudospectra, then applying rule-based annotation. This identifies which features belong to the same metabolite, enabling downstream merging of redundant signals.

    Workflow:
    1. Pseudospectrum grouping (groupFWHM) — groups peaks by retention time window
    2. Isotope annotation (findIsotopes) — identifies 13C, 34S isotope peaks within pseudospectra
    3. EIC correlation verification (groupCorr) — validates co-elution via Pearson correlation
    4. Adduct annotation (findAdducts) — matches observed m/z to known adduct rules
    5. Neutral loss screening (findNeutralLoss) — detects H2O, CO2, NH3 losses
    6. Redundant feature marking — labels isotope peaks, in-source fragments, and multimers

    Reference: Kuhl et al. "CAMERA: an integrated strategy for compound spectra extraction and annotation of LC-MS data sets." Analytical Chemistry, 2012, 84(1), 283–289.

    Parameters:
    - input_dir: directory containing peak table CSV files (must have mz, rt, intensity columns)
    - output_dir: directory to save annotated peak tables and redundancy reports
    - file_pattern: file matching pattern (default "*.csv")
    - polarity: ionization mode — "positive" or "negative" (default "positive")
    - ppm: mass accuracy in ppm (default 10.0)
    - mzabs: absolute m/z tolerance in Da (default 0.01)
    - perfwhm: FWHM model peak width coefficient (default 0.6)
    - cor_eic_th: EIC Pearson correlation threshold for pseudospectrum validation (default 0.75)
    - sigma: standard deviation multiplier for RT window (default 6.0)
    - maxcharge: maximum charge state (default 3)
    - maxiso: maximum number of isotopes to annotate (default 4)
    - filter_by_ips: mark in-source products as redundant (default True)

    Outputs:
    - {sample}_camera_annotated.csv: peak table with pcgroup, isotopes, adduct, is_redundant columns
    - {sample}_camera_pcgroups.csv: pseudospectrum group summary
    - {sample}_camera_redundant.csv: list of redundant features
    - all_camera_annotated.csv: merged annotated peak table (per-sample, all samples concatenated)
    - feature_table_filtered.csv: ALIGNED-level feature table with redundant features removed (majority vote across samples). This is the primary input for downstream Stage 4 (Missing Value Imputation). Format matches XCMS feature_table.csv: feature_id, mz, rt_med, sample columns.
    - camera_summary.txt: statistics summary
    """
)
async def redundant_feature_filtering_camera_tool(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.csv",
    polarity: str = "positive",
    ppm: float = 10.0,
    mzabs: float = 0.01,
    perfwhm: float = 0.6,
    cor_eic_th: float = 0.75,
    sigma: float = 6.0,
    maxcharge: int = 3,
    maxiso: int = 4,
    filter_by_ips: bool = True,
):
    redundant_feature_filtering_camera_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        file_pattern=file_pattern,
        polarity=polarity,
        ppm=ppm,
        mzabs=mzabs,
        perfwhm=perfwhm,
        cor_eic_th=cor_eic_th,
        sigma=sigma,
        maxcharge=maxcharge,
        maxiso=maxiso,
        filter_by_ips=filter_by_ips,
    )
    return _format_tool_result("redundant_feature_filtering_camera", [output_dir])


# ============================= RAMClust 特征聚类 =============================
@mcp.tool(
    name="redundant_feature_filtering_ramclust",
    description="""
    Use RAMClust (R-based Mass Spectrometry Feature Clustering) to cluster redundant features into compound spectra based on retention time similarity and cross-sample intensity correlation.

    RAMClust groups features that originate from the same metabolite by combining RT similarity (exponential decay model) and correlational patterns of feature intensities across samples. Unlike CAMERA's rule-based approach, RAMClust is fully data-driven and does not require adduct rule tables.

    Workflow:
    1. Build feature × sample intensity matrix from multiple peak table CSVs
    2. Missing value imputation (1/2 minimum detection intensity)
    3. Blank filtering — remove features where sample/blank ratio < 3
    4. QC-CV filtering — remove features with high variation in QC samples
    5. Normalization (TIC, quantile, or none)
    6. Compute joint similarity matrix: S = (1-sr)*|correlation| + sr*RT_similarity
    7. Hierarchical clustering + dynamic tree cutting
    8. Spectrum collapse — merge member intensities into compound-level quantification
    9. Main peak inference — identify the most likely molecular ion per cluster

    Reference: Broeckling et al. "RAMClust: A Novel Feature Clustering Method Enables Spectral-Matching-Based Annotation for Metabolomics Data." Analytical Chemistry, 2014, 86(14), 6812–6817.

    Parameters:
    - input_dir: directory containing multiple sample peak table CSV files
    - output_dir: directory to save clustering results
    - file_pattern: file matching pattern (default "*.csv")
    - st: RT similarity decay factor sigma_t (default 5.0)
    - sr: correlation weight in joint distance, 0-1 (default 0.5)
    - maxt: maximum RT difference in minutes (default 2.0)
    - deep_split: dynamic tree cut depth 0-4, higher = more clusters (default 2)
    - min_module_size: minimum features per cluster (default 2)
    - cor_method: correlation method — "pearson" or "spearman" (default "pearson")
    - linkage_method: HCA linkage — "average", "complete", "single", "ward" (default "average")
    - normalize_method: normalization — "none", "TIC", "quantile" (default "none")
    - qc_tag: string tag to identify QC samples in filenames (default "QC")
    - blank_tag: string tag to identify blank samples in filenames (default "Blank")
    - cv_threshold: QC CV threshold for feature filtering (default 0.3)
    - collapse_method: spectrum collapse — "max", "sum", "mean", "median", "apex" (default "max")

    Outputs:
    - feature_intensity_matrix.csv: feature × sample intensity matrix
    - ramclust_clusters.csv: cluster assignment for each feature
    - ramclust_compound_spectra.csv: compound-level spectral summary
    - ramclust_compound_intensities.csv: compound × sample intensity matrix
    - ramclust_filtered_features.csv: features removed by blank/CV filtering
    - ramclust_summary.txt: statistics summary

    Notes:
    - Requires multiple sample files for correlation computation
    - At least 2 sample files are needed for meaningful clustering
    - QC and blank filtering are optional — will be skipped if no matching samples found
    """
)
async def redundant_feature_filtering_ramclust_tool(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.csv",
    st: float = 5.0,
    sr: float = 0.5,
    maxt: float = 2.0,
    deep_split: int = 2,
    min_module_size: int = 2,
    cor_method: str = "pearson",
    linkage_method: str = "average",
    normalize_method: str = "none",
    qc_tag: str | None = "QC",
    blank_tag: str | None = "Blank",
    cv_threshold: float = 0.3,
    feature_filter_blanks: bool = True,
    feature_filter_cv: bool = True,
    collapse_method: str = "max",
    max_features: int = 8000,
):
    redundant_feature_filtering_ramclust_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        file_pattern=file_pattern,
        st=st,
        sr=sr,
        maxt=maxt,
        deep_split=deep_split,
        min_module_size=min_module_size,
        cor_method=cor_method,
        linkage_method=linkage_method,
        normalize_method=normalize_method,
        qc_tag=qc_tag,
        blank_tag=blank_tag,
        cv_threshold=cv_threshold,
        feature_filter_blanks=feature_filter_blanks,
        feature_filter_cv=feature_filter_cv,
        collapse_method=collapse_method,
        max_features=max_features,
    )
    return _format_tool_result("redundant_feature_filtering_ramclust", [output_dir])


# ============================= mzAnnotation 精确质量注释 =============================
@mcp.tool(
    name="redundant_feature_filtering_mzannotation",
    description="""
    Use mzAnnotation for high-resolution mass spectrometry m/z putative annotation. Calculates possible molecular masses from observed m/z values by iterating through all known adduct, isotope, and chemical transformation rules.

    Unlike CAMERA (which relies on RT co-elution and pseudospectra) and RAMClust (which uses cross-sample correlation patterns), mzAnnotation performs pure mass-based annotation suitable for high-resolution instruments (Orbitrap, FT-ICR, Q-TOF with >30k resolution).

    Workflow:
    1. Load peak table CSV
    2. For each observed m/z, iterate through 40+ positive or 30+ negative adduct rules
    3. For each adduct, calculate possible neutral mass: M = (mz * |charge| - massdiff) / nmol
    4. Cross-predict: for each neutral mass, search for other features matching alternative adduct forms
    5. Isotope annotation: identify 13C, 15N, 34S, 37Cl, 81Br isotope peaks
    6. Chemical transformation annotation: methylation, acetylation, glucuronidation, etc.
    7. Score and rank hypotheses by mass error and adduct likelihood (oidscore)
    8. Mark redundant features (isotopes, in-source fragments, non-quasi-molecular ions)

    Reference: mzAnnotation R package (aberHRML/jasenfinch). https://aberhrml.github.io/mzAnnotation/

    Parameters:
    - input_dir: directory containing peak table CSV files
    - output_dir: directory to save annotation results
    - file_pattern: file matching pattern (default "*.csv")
    - polarity: ionization mode — "positive" or "negative" (default "positive")
    - ppm: mass accuracy in ppm for HRMS data (default 5.0)
    - mzabs: absolute m/z tolerance in Da (default 0.001)
    - max_annotations_per_feature: max annotations retained per feature (default 5)
    - include_isotopes: include isotope annotations (default True)
    - include_transformations: include chemical transformation annotations (default True)
    - filter_redundant_adducts: mark non-quasi-molecular features as redundant (default True)
    - mass_range: valid neutral mass range in Da, e.g. (50, 2000) (default None = auto)
    - charge_range: valid charge range (min, max) (default (1, 3))
    - min_oidscore: minimum adduct likelihood score (default 0.3)

    Outputs:
    - {sample}_mzannotation_annotated.csv: peak table with best_adduct, neutral_mass, is_redundant
    - {sample}_mzannotation_hypotheses.csv: all annotation hypotheses per feature
    - {sample}_mzannotation_redundant.csv: list of redundant features with reasons
    - all_mzannotation_annotated.csv: merged annotated peak table
    - mzannotation_summary.txt: statistics summary

    Notes:
    - Best suited for high-resolution MS data (sub-ppm mass accuracy)
    - For low-resolution data, increase ppm to 10-20 and mzabs to 0.01
    - The extended adduct rule table includes 45 positive-mode and 27 negative-mode adducts
    """
)
async def redundant_feature_filtering_mzannotation_tool(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.csv",
    polarity: str = "positive",
    ppm: float = 5.0,
    mzabs: float = 0.001,
    max_annotations_per_feature: int = 5,
    include_isotopes: bool = True,
    include_transformations: bool = True,
    filter_redundant_adducts: bool = True,
    mass_range_min: float | None = None,
    mass_range_max: float | None = None,
    charge_min: int = 1,
    charge_max: int = 3,
    min_oidscore: float = 0.3,
    max_features: int = 15000,
):
    mass_range = None
    if mass_range_min is not None and mass_range_max is not None:
        mass_range = (mass_range_min, mass_range_max)

    redundant_feature_filtering_mzannotation_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        file_pattern=file_pattern,
        polarity=polarity,
        ppm=ppm,
        mzabs=mzabs,
        max_annotations_per_feature=max_annotations_per_feature,
        include_isotopes=include_isotopes,
        include_transformations=include_transformations,
        filter_redundant_adducts=filter_redundant_adducts,
        mass_range=mass_range,
        charge_range=(charge_min, charge_max),
        min_oidscore=min_oidscore,
        max_features=max_features,
    )
    return _format_tool_result("redundant_feature_filtering_mzannotation", [output_dir])


# ============================= 冗余特征过滤综合管线 =============================
@mcp.tool(
    name="redundant_feature_filtering_pipeline",
    description="""[Category: redundant_feature_filtering]
    Run the complete redundant feature filtering pipeline: CAMERA → mzAnnotation → RAMClust.

    This pipeline applies three complementary redundant feature filtering approaches sequentially:
    1. CAMERA — rule-based annotation (isotopes, adducts, neutral losses) using pseudospectra
    2. mzAnnotation — high-resolution mass-based putative annotation using exact mass calculation
    3. RAMClust — data-driven clustering based on RT similarity and cross-sample intensity correlation

    Each tool's output is saved in its own subdirectory under output_dir. A combined redundant feature report is generated at the end.

    Use this pipeline when you need comprehensive redundant feature identification combining chromatographic (CAMERA), mass spectrometric (mzAnnotation), and statistical (RAMClust) evidence.

    Parameters:
    - input_dir: directory containing peak table CSV files
    - output_dir: root output directory (results saved in camera/, mzannotation/, ramclust/ subdirs)
    - file_pattern: file matching pattern (default "*.csv")
    - polarity: ionization mode — "positive" or "negative" (default "positive")

    Outputs:
    - output_dir/camera/: CAMERA annotated peak tables and pseudospectrum summaries
    - output_dir/mzannotation/: mzAnnotation hypotheses and redundancy reports
    - output_dir/ramclust/: RAMClust cluster assignments and compound spectra

    Notes:
    - Each stage runs independently; failure in one stage does not stop the pipeline
    - For parameter customization of individual tools, use the specific tool instead
    """
)
async def redundant_feature_filtering_pipeline_tool(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.csv",
    polarity: str = "positive",
):
    redundant_feature_filtering_pipeline_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        file_pattern=file_pattern,
        polarity=polarity,
    )
    return _format_tool_result("redundant_feature_filtering_pipeline", [output_dir])


# 用于挂起服务器，而非测试。这段代码的存在是必要的，不能注释掉
if __name__ == "__main__":
    mcp.run(transport="stdio")
    