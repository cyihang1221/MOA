import tempfile
import subprocess
import os


# ============================= CAMERA 实现 =============================
def filter_redundant_features_camera_impl(
    input_file: str,    # 可以是：.rds / .featureXML / .csv
    output_rds: str
) -> str:
    """
    自动识别输入格式：
    - .rds: XCMS 对象
    - .csv: MZmine / PeakOnly
    - .featureXML: OpenMS
    不支持：.mzmine
    """
    ext = os.path.splitext(input_file)[1].lower()

    # ===================== 自动判断读取逻辑 =====================
    if ext == ".rds":
        # XCMS 格式
        read_code = f'xdata <- readRDS("{input_file}")'

    elif ext == ".featurexml":
        # OpenMS 格式
        read_code = f'''
        library(xcms)
        library(MSnbase)
        # 读取 OpenMS 特征并转为 XCMS 对象
        peaks <- read.table("{input_file}", header=TRUE, sep="\\t", check.names=FALSE)
        xdata <- new("xcmsSet")
        xdata@peaks <- as.matrix(peaks[, c("mz", "rt", "into", "maxo", "sn", "sample")])
        '''

    elif ext == ".csv":
        # MZmine / PeakOnly / 通用 CSV
        read_code = f'''
        library(xcms)
        library(MSnbase)
        peaks <- read.csv("{input_file}", check.names=FALSE)
        xdata <- new("xcmsSet")
        xdata@peaks <- as.matrix(peaks[, c("mz", "rt", "into", "maxo", "sn", "sample")])
        '''

    elif ext == ".mzmine":
        # MZmine 项目文件 → 提示使用 CSV
        raise ValueError("不支持直接读取 .mzmine 文件，请传入 MZmine 导出的 .csv 峰表")

    else:
        raise ValueError(f"不支持的输入格式：{ext}，请使用 .rds / .csv / .featureXML")

    # ===================== CAMERA 核心流程 =====================
    r_script = f'''
    library(CAMERA)
    library(xcms)

    {read_code}

    # CAMERA 去冗余
    an <- xsAnnotate(xdata)
    an <- groupFWHM(an)
    an <- findIsotopes(an)
    an <- groupCorr(an)

    # 输出完整对象
    saveRDS(an, "{output_rds}")
    '''

    # 执行脚本
    with tempfile.NamedTemporaryFile(mode='w', suffix='.R', delete=False) as f:
        f.write(r_script)
        r_file = f.name

    try:
        subprocess.run(["Rscript", r_file], check=True)
    finally:
        os.unlink(r_file) 


# ============================= RAMClustR 实现 =============================
def filter_redundant_features_ramclustr_impl(
    input_file: str,
    output_rds: str
) -> str:
    """
    自动识别输入格式：
    - .rds: XCMS 对象
    - .csv: MZmine / PeakOnly
    - .featureXML: OpenMS
    不支持：.mzmine
    """
    ext = os.path.splitext(input_file)[1].lower()

    # ===================== 自动判断输入格式 =====================
    if ext == ".rds":
        # 读取 XCMS 输出的 rds
        read_code = f'''
        library(xcms)
        xdata <- readRDS("{input_file}")
        peak_table <- chromPeaks(xdata)
        '''

    elif ext == ".csv":
        # 读取通用 CSV
        read_code = f'''
        peak_table <- read.csv("{input_file}", check.names = FALSE)
        '''

    elif ext == ".featurexml":
        # OpenMS featureXML 转为表格
        read_code = f'''
        library(MSnbase)
        f <- readFeatureXML("{input_file}")
        peak_table <- as.data.frame(f)
        '''

    elif ext == ".mzmine":
        # MZmine 项目文件 → 提示使用 CSV
        raise ValueError("不支持直接读取 .mzmine 文件，请传入 MZmine 导出的 .csv 峰表")
    
    else:
        raise ValueError(f"不支持的输入格式：{ext}，请使用 .rds / .csv / .featureXML")

    # ===================== RAMClustR 核心流程 =====================
    r_script = f'''
    library(RAMClustR)
    library(xcms)

    {read_code}

    # 构造 RAMClustR 需要的输入数据
    # 必须包含：mz, rt, intensity (into)
    df <- data.frame(
      mz = peak_table[,"mz"],
      rt = peak_table[,"rt"],
      into = peak_table[,"into"]
    )

    # 运行 RAMClust 聚类（去同位素/加合物/冗余）
    ramclust <- ramclustR(
      ms = df,
      pheno = data.frame(sample = rep(1, nrow(df))),
      st = NULL,
      sampNames = NULL,
      usePheno = FALSE,
      rtmax = 1,
      mzdec = 4,
      rtdec = 2
    )

    # 保存完整 RAMClust 对象（等价于 XCMS rds）
    saveRDS(ramclust, "{output_rds}")
    '''

    # 写入并运行 R 脚本
    with tempfile.NamedTemporaryFile(mode='w', suffix='.R', delete=False) as f:
        f.write(r_script)
        r_file = f.name

    try:
        subprocess.run(["Rscript", r_file], check=True)
    finally:
        os.unlink(r_file)


# ============================= mzAnnotation 实现 =============================
def filter_redundant_features_mzannotation_impl(
    input_file: str,
    output_rds: str
) -> str:
    """
    自动识别输入格式：
    - .rds: XCMS 对象
    - .csv: MZmine / PeakOnly
    - .featureXML: OpenMS
    不支持：.mzmine
    """
    ext = os.path.splitext(input_file)[1].lower()

    # ===================== 自动判断输入格式 =====================
    if ext == ".rds":
        read_code = f'''
        library(xcms)
        xdata <- readRDS("{input_file}")
        peak_table <- chromPeaks(xdata)
        '''

    elif ext == ".csv":
        read_code = f'''
        peak_table <- read.csv("{input_file}", check.names = FALSE)
        '''

    elif ext == ".featurexml":
        read_code = f'''
        library(MSnbase)
        f <- readFeatureXML("{input_file}")
        peak_table <- as.data.frame(f)
        '''

    elif ext == ".mzmine":
        raise ValueError("不支持直接读取 .mzmine 文件，请传入 MZmine 导出的 .csv 峰表")

    else:
        raise ValueError(f"不支持格式：{ext}，请用 .rds / .csv / .featureXML")

    # ===================== mzAnnotation 冗余过滤 =====================
    r_script = f'''
    library(mzAnnotation)
    library(xcms)

    {read_code}

    # 构建标准输入
    df <- data.frame(
        mz = peak_table[,"mz"],
        rt = peak_table[,"rt"],
        intensity = peak_table[,"into"]
    )

    # mzAnnotation 过滤冗余特征
    filtered <- filterFeatures(
        df,
        ppm = 10,                # 质量偏差
        rt_window = 0.1,         # 保留时间窗口
        remove_isotopes = TRUE,  # 去除同位素
        remove_adducts = TRUE,    # 去除加合物
        keep_best = TRUE         # 只保留强度最高的代表峰
    )

    # 保存完整过滤结果
    saveRDS(filtered, "{output_rds}")
    '''

    # 运行脚本
    with tempfile.NamedTemporaryFile(mode='w', suffix='.R', delete=False) as f:
        f.write(r_script)
        r_file = f.name

    try:
        subprocess.run(["Rscript", r_file], check=True)
    finally:
        os.unlink(r_file)
