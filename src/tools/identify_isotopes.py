import tempfile
import subprocess
import os


def identify_isotopes_openms_IsotopeTools_impl(input_rds: str, output_rds: str) -> str:
    r_script = f'''
    library(OpenMS)
    library(data.table)

    # 读取峰检测+冗余过滤后的特征数据
    feature_data <- readRDS("{input_rds}")

    # 构造 OpenMS 适配格式
    feature_df <- data.table(
      id = 1:nrow(feature_data),
      mz = feature_data$mz,
      rt = feature_data$rt,
      intensity = feature_data$intensity
    )

    # OpenMS-IsotopeTools 同位素识别
    iso_result <- isotopeFeatureFinder(
      features = feature_df,
      charge = 1,
      mz_tol = 0.01,
      rt_tol = 5
    )

    # 保存结果
    saveRDS(iso_result, "{output_rds}")
    '''

    with tempfile.NamedTemporaryFile(mode='w', suffix='.R', delete=False) as f:
        f.write(r_script)
        r_file = f.name

    try:
        subprocess.run(["Rscript", r_file], check=True)
    finally:
        os.unlink(r_file)
