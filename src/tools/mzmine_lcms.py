import tempfile
import subprocess
import os

def mzmine_lcms_datapreprocess_impl(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.mzML",
    mz_tolerance: float = 0.01,
    rt_tolerance: float = 0.2,
    min_intensity: float = 1000.0,
    sn_threshold: float = 3.0,
    min_matched_samples: int = 2,
    min_peak_width: float = 0.05,
    max_peak_width: float = 2.0
) -> str:
    """
    LC-MS 非靶向数据预处理流程：mzML → 峰检测 → 冗余过滤 → RT对齐 → 同位素识别 → 峰分组 → 缺失填充
    """
    os.makedirs(output_dir, exist_ok=True)
    result_csv = os.path.join(output_dir, "mzmine_LCMS_peak_list.csv")

    mzmine_script = f'''<?xml version="1.0" encoding="UTF-8"?>
<mzmine_batch>
    <!-- 1. 导入原始数据 -->
    <task type="raw_data_import">
        <filename_pattern>{input_dir}/{file_pattern}</filename_pattern>
    </task>

    <!-- 2. 峰检测 -->
    <task type="gridmass_peak_detection">
        <mz_tolerance>{mz_tolerance}</mz_tolerance>
        <rt_tolerance>{rt_tolerance}</rt_tolerance>
        <min_intensity>{min_intensity}</min_intensity>
        <sn_threshold>{sn_threshold}</sn_threshold>
        <peak_duration_min>{min_peak_width}</peak_duration_min>
        <peak_duration_max>{max_peak_width}</peak_duration_max>
    </task>

    <!-- 3. 冗余特征过滤 -->
    <task type="filter_peaks">
        <filter>duplicates</filter>
        <mz_tolerance>{mz_tolerance}</mz_tolerance>
        <rt_tolerance>{rt_tolerance}</rt_tolerance>
        <keep_highest>true</keep_highest>
    </task>

    <!-- 4. 保留时间对齐 -->
    <task type="retention_time_alignment">
        <algorithm>JOINT</algorithm>
        <mz_tolerance>{mz_tolerance}</mz_tolerance>
        <rt_tolerance>{rt_tolerance}</rt_tolerance>
    </task>

    <!-- 5. 同位素注释 -->
    <task type="isotope_annotation">
        <mz_tolerance>{mz_tolerance}</mz_tolerance>
        <rt_tolerance>{rt_tolerance}</rt_tolerance>
        <max_isotopes>3</max_isotopes>
    </task>

    <!-- 6. 峰分组（谱峰对齐） -->
    <task type="peak_grouping">
        <algorithm>JOINT</algorithm>
        <mz_tolerance>{mz_tolerance}</mz_tolerance>
        <rt_tolerance>{rt_tolerance}</rt_tolerance>
        <min_matched_samples>{min_matched_samples}</min_matched_samples>
    </task>

    <!-- 7. 缺失峰填充 -->
    <task type="gap_fill">
        <algorithm>JOINT</algorithm>
        <mz_tolerance>{mz_tolerance}</mz_tolerance>
        <rt_tolerance>{rt_tolerance}</rt_tolerance>
    </task>

    <!-- 8. 导出结果 -->
    <task type="export_peak_list_csv">
        <filename>{result_csv}</filename>
        <export_header>true</export_header>
    </task>
</mzmine_batch>
    '''

    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        f.write(mzmine_script)
        script_file = f.name

    try:
        subprocess.run(
            ['mzmine', '--batch', script_file],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
    finally:
        os.unlink(script_file)
