import tempfile
import subprocess
import os


# ============================= CAMERA 实现 =============================
def filter_redundant_features_camera_impl(
    input_rds: str,
    output_rds: str
) -> str:
   
    r_script = f'''
    library(CAMERA)
    library(xcms)

    # 读取 xcms 数据
    xdata <- readRDS("{input_rds}")

    # 标注特征
    an <- xsAnnotate(xdata)

    # 根据特征宽度（FWHM）进行分组
    an <- groupFWHM(an)

    # 找到同位素特征
    an <- findIsotopes(an)

    # 去除冗余的特征（即只保留最具代表性的特征）
    an <- groupCorr(an)

    # 保存处理后的数据
    saveRDS(an, "{output_rds}")
    '''

    # 使用 tempfile 创建一个临时的 R 脚本文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.R', delete=False) as f:
        f.write(r_script)
        r_file = f.name

    try:
        # 执行 R 脚本
        subprocess.run(["Rscript", r_file], check=True)
    finally:
        # 删除临时 R 脚本文件
        os.unlink(r_file)


# ============================= RAMClustR 实现 =============================
def filter_redundant_features_ramclustr_impl(
    input_rds: str,
    output_rds: str
) -> str:
    
    r_script = f'''
    library(RAMClustR)
    library(xcms)

    # 读取 xcms 处理后的数据
    xdata <- readRDS("{input_rds}")

    # 使用 RAMClustR 进行冗余特征过滤
    filtered_data <- filter_redundant_features(xdata)

    # 保存过滤后的数据
    saveRDS(filtered_data, "{output_rds}")
    '''

    # 使用 tempfile 创建一个临时的 R 脚本文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.R', delete=False) as f:
        f.write(r_script)
        r_file = f.name

    try:
        # 执行 R 脚本
        subprocess.run(["Rscript", r_file], check=True)
    finally:
        # 删除临时 R 脚本文件
        os.unlink(r_file)
