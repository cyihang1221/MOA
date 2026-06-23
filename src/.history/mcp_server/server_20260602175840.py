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



# ============================= xcms: data preprocessing =============================
@mcp.tool(
    name="data_preprocessing_xcms",
    description="""
    This tool processes untargeted LC-MS/MS data using XCMS with standard steps: peak picking (centWave), retention time alignment (Obiwarp), peak grouping (PeakDensity), and gap filling. It then performs blank subtraction (ratio-based filtering) and, for the retained features, extracts the best matching MS/MS spectra from the raw data in parallel. The final outputs are a feature quantification table (CSV) and the corresponding MS/MS spectra (MGF), ready for structural annotation with tools like DeepMass.

    Parameters:
    - input_dir: directory containing .mzML files
    - output_dir: directory to save the feature table file and MS/MS spectra MGF file
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
    - input_dir: directory containing input feature table CSV
    - output_dir: directory to save the filtered + imputed feature table and summary
    - min_presence: minimum fraction of non-missing values per feature (default 0.5)
    - min_intensity: minimum mean intensity threshold (default 0.0)
    - n_neighbors: number of neighbors for KNN imputation (default 5)

    Outputs:
    - filtered + imputed feature table (CSV)
    - summary text file
    """
)
async def feature_filtering_and_missing_value_imputation_knn_tool(
    input_dir: str,
    output_dir: str,
    min_presence: float = 0.5,
    min_intensity: float = 0.0,
    n_neighbors: int = 5
):
    feature_filtering_and_missing_value_imputation_KNN_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        min_presence=min_presence,
        min_intensity=min_intensity,
        n_neighbors=n_neighbors
    )

    return (
        f"Feature filtering and KNN imputation completed.\n"
        f"Input: {input_dir}\n"
        f"Output: {output_dir}\n"
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
    - input_dir: path to the input directory containing the feature table CSV after filtering and imputation.
    - metadata_csv: sample metadata CSV with group labels
    - output_dir: directory to save the statistical analysis results
    Parameters:
    - ncomp_pca: number of PCA components (default 5)
    - ncomp_plsda: number of PLS-DA components (default 2)
    - scale_method: data scaling method (default "autoscale")
    - top_n_heatmap: number of top features to show in heatmap (default 50)
    - seed: random seed for reproducibility (default 123)
    - vip_threshold: VIP score threshold for feature selection (default 1.0)
    - pvalue_threshold: p-value threshold for differential analysis (default 0.05)
    - padj_threshold: adjusted p-value threshold (default 0.05)
    - log2fc_threshold: log2 fold change threshold for differential analysis (default 0.58, which corresponds to 1.5-fold change)
    - use_fdr: whether to use FDR correction for p-values (default False)

    Key outputs:
    - PCA / PLS-DA plots
    - VIP scores
    - differential metabolites
    - volcano plot
    - heatmap of top features
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
    use_fdr: bool = False
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

    return (
        f"Statistical analysis completed using mixOmics.\n"
        f"Input feature table: {input_dir}\n"
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

    Parameters:
    - differential_csv: differential metabolite table
    - input_mgf: full MS/MS spectra file (MGF)
    - output_dir: directory to save extracted differential features files

    Outputs:
    - output_dir/differential_feature_table.csv: filtered feature table with only differential features
    - output_dir/differential_spectra.mgf: MGF file containing spectra of differential features
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

    return (
        f"Differential feature extraction completed.\n"
        f"Input differential metabolites: {differential_csv}\n"
        f"Input MGF: {input_mgf}\n"
        f"Output directory: {output_dir}"
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

    Parameters:
    - input_dir: path to the directory containing extracted differential features files
    - output_dir: path to the directory saving annotation results CSV file
    - precursor_ppm: precursor tolerance in ppm (default 100)
    - fragment_tol: fragment tolerance in Da (default 0.2)
    - min_cosine: minimum similarity score (default 0.2)

    Outputs:
    - annotated feature table CSV
    """
)
async def spectral_annotation_tool(
    input_dir: str,
    output_dir: str,
    precursor_ppm: float = 100,
    fragment_tol: float = 0.2,
    min_cosine: float = 0.2
):
    spectral_annotation_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        precursor_ppm=precursor_ppm,
        fragment_tol=fragment_tol,
        min_cosine=min_cosine
    )

    return (
        f"Spectral annotation completed.\n"
        f"Input directory: {input_dir}\n"
        f"Output directory: {output_dir}\n"
    )




# 用于挂起服务器，而非测试。这段代码的存在是必要的，不能注释掉
if __name__ == "__main__":
    mcp.run(transport="stdio")
    