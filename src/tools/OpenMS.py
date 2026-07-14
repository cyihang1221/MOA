# OpenMS 质谱数据处理工具 —— 基于 OpenMS 的峰检测（PeakPicking）与特征提取管道
# 核心实现：PeakPickerHiRes 高分辨峰检测，适用于 Orbitrap / FT-ICR 等高分辨质谱数据
# OpenMS 通过 C++ 命令行工具执行，需提前安装 OpenMS 或通过 conda/pip 安装

import os
import subprocess
import tempfile
import glob
from typing import Optional
import csv
import xml.etree.ElementTree as ET
import base64
import struct
import re


# ============================= PeakPickerHiRes 峰检测 =============================
# OpenMS-PeakPicking
def peak_picking_openms_impl(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.mzML",
    signal_to_noise: float = 0.0,
    spacing_difference_gap: float = 4.0,
    spacing_difference: float = 1.5,
    missing: int = 1,
    ms_levels: Optional[str] = None,
    report_fwhm: bool = False,
    report_fwhm_unit: str = "relative",
    threads: Optional[int] = None,
    openms_path: str = "",
):
    """
    使用 OpenMS PeakPickerHiRes 对高分辨 LC-MS 数据进行峰检测（centroiding）。

    PeakPickerHiRes 实现了适用于高分辨质谱数据（FT-ICR-MS, Orbitrap）的快速峰检测算法：
    - 在 profile 模式质谱中检测离子信号
    - 通过三次样条插值重建峰形
    - 从样条最大值处报告 m/z 和强度
    - 信号检测基于可调信噪比阈值

    参考文献: Pfeuffer, J. et al. OpenMS 3 enables reproducible analysis of
              large-scale mass spectrometry data. Nature Methods, 2024.

    Parameters
    ----------
    input_dir : str
        包含 profile 模式 .mzML 文件的输入目录。
    output_dir : str
        输出目录，保存 centroided .mzML 文件、MGF 谱图文件和峰表 CSV。
    file_pattern : str, default="*.mzML"
        mzML 文件匹配模式。
    signal_to_noise : float, default=0.0
        峰检测的最小信噪比阈值。0.0 表示禁用 SNR 估计，会拾取所有信号。
    spacing_difference_gap : float, default=4.0
        峰扩展停止条件：当相邻点间距超过 spacing_difference_gap * min_spacing 时停止。
        0 表示禁用。不适用于色谱图。
    spacing_difference : float, default=1.5
        峰扩展期间相邻点间最大允许间距差（以峰顶与相邻点的最小间距的倍数表示）。
        0 表示禁用。
    missing : int, default=1
        向峰左侧或右侧扩展时允许的最大缺失点数。
    ms_levels : str, optional
        要进行峰检测的 MS 级别，如 "1"（仅 MS1）或 "1,2"（MS1+MS2）。
        不指定则自动检测所有未拾取的扫描。
    report_fwhm : bool, default=False
        是否在输出中添加 FWHM（半峰宽）元数据。
    report_fwhm_unit : str, default="relative"
        FWHM 单位："relative"（ppm）或 "absolute"（m/z）。
    threads : int, optional
        并行线程数，None 表示使用 OpenMS 默认值（1）。
    openms_path : str, default=""
        OpenMS 可执行文件所在目录路径。留空则使用系统 PATH 中的默认路径。
    """

    print(f"\n[OpenMS-PeakPickerHiRes] 开始高分辨峰检测...")
    print(f"  输入目录: {input_dir}")
    print(f"  信噪比阈值: {signal_to_noise}")
    print(f"  MS 级别: {ms_levels if ms_levels else '自动检测'}")

    os.makedirs(output_dir, exist_ok=True)
    input_abs = os.path.abspath(input_dir)
    output_abs = os.path.abspath(output_dir)

    # 创建 MGF 输出子目录
    mgf_dir = os.path.join(output_abs, "mgf")
    os.makedirs(mgf_dir, exist_ok=True)

    # 构建可执行文件路径
    peak_picker_bin = os.path.join(openms_path, "PeakPickerHiRes") if openms_path else "PeakPickerHiRes"
    file_converter_bin = os.path.join(openms_path, "FileConverter") if openms_path else "FileConverter"

    # 查找输入文件
    mzml_files = sorted(glob.glob(os.path.join(input_abs, file_pattern)))
    if not mzml_files:
        raise FileNotFoundError(f"在 {input_abs} 中未找到匹配 {file_pattern} 的 .mzML 文件")

    print(f"  找到 {len(mzml_files)} 个输入文件")

    # 收集所有峰数据用于构建统一特征表
    all_peaks = []  # list of dicts: {feature_id, filename, mz, rt, intensity, sn}

    for i, mzml_file in enumerate(mzml_files):
        basename = os.path.splitext(os.path.basename(mzml_file))[0]
        centroided_file = os.path.join(output_abs, f"{basename}_centroided.mzML")
        print(f"\n  处理文件 [{i+1}/{len(mzml_files)}]: {os.path.basename(mzml_file)}")

        # 构建 PeakPickerHiRes 命令
        cmd = [peak_picker_bin]
        cmd += ["-in", mzml_file]
        cmd += ["-out", centroided_file]
        cmd += ["-algorithm:signal_to_noise", str(signal_to_noise)]
        cmd += ["-algorithm:spacing_difference_gap", str(spacing_difference_gap)]
        cmd += ["-algorithm:spacing_difference", str(spacing_difference)]
        cmd += ["-algorithm:missing", str(missing)]

        if ms_levels is not None:
            cmd += ["-algorithm:ms_levels", str(ms_levels)]

        if report_fwhm:
            cmd += ["-algorithm:report_FWHM", "true"]
            cmd += ["-algorithm:report_FWHM_unit", report_fwhm_unit]

        if threads is not None:
            cmd += ["-threads", str(threads)]

        # 执行峰检测
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"  [警告] PeakPickerHiRes 返回非零退出码: {result.returncode}")
            if result.stderr:
                print(f"  stderr: {result.stderr[:500]}")
            # 不中断处理，尝试继续处理其他文件

        if os.path.exists(centroided_file):
            file_size = os.path.getsize(centroided_file) / (1024 * 1024)
            print(f"  输出: {os.path.basename(centroided_file)} ({file_size:.1f} MB)")

            # 从 centroided mzML 中提取峰数据
            peaks = _extract_peaks_from_mzml(centroided_file, basename)
            all_peaks.extend(peaks)
            print(f"  检测到 {len(peaks)} 个峰")

            # 将 centroided mzML 转换为 MGF（MS/MS 谱图）
            mgf_file = os.path.join(mgf_dir, f"{basename}.mgf")
            convert_cmd = [file_converter_bin]
            convert_cmd += ["-in", centroided_file]
            convert_cmd += ["-out", mgf_file]

            convert_result = subprocess.run(convert_cmd, capture_output=True, text=True)
            if convert_result.returncode == 0 and os.path.exists(mgf_file):
                mgf_size = os.path.getsize(mgf_file) / (1024 * 1024)
                print(f"  MGF 导出: {os.path.basename(mgf_file)} ({mgf_size:.1f} MB)")
            else:
                print(f"  [警告] FileConverter MGF 导出失败")
                if convert_result.stderr:
                    print(f"  stderr: {convert_result.stderr[:300]}")
        else:
            print(f"  [警告] 未生成输出文件，请检查 OpenMS 是否正确安装")

    # 导出统一特征表 CSV
    if all_peaks:
        feature_csv = os.path.join(output_abs, "feature_table_peakpicking.csv")
        _write_peak_table(all_peaks, feature_csv)
        print(f"\n✅ 峰表已保存: {feature_csv}")
        print(f"  总峰数: {len(all_peaks)}")
    else:
        print("\n[警告] 未检测到任何峰，未生成特征表")


def _extract_peaks_from_mzml(mzml_file: str, source_name: str) -> list:
    """
    从 centroided mzML 文件中提取峰数据。

    解析 mzML XML 格式，读取每个谱图的 m/z、强度和保留时间，
    提取谱图中的峰数据点。

    Parameters
    ----------
    mzml_file : str
        centroided mzML 文件路径。
    source_name : str
        来源文件名（不含扩展名），用于标注峰来源。

    Returns
    -------
    list of dict
        每个峰包含: feature_id, filename, mz, rt, intensity, ms_level
    """
    peaks = []

    try:
        # 注册命名空间以简化 XPath 查询
        ns = {
            'mzml': 'http://psi.hupo.org/ms/mzml',
        }

        # 解析 XML 树，使用 iterparse 以支持大文件流式处理
        context = ET.iterparse(mzml_file, events=('end',))

        current_spectrum = {}
        binary_data_arrays = []

        for event, elem in context:
            # 处理 </spectrum> 结束标签
            if elem.tag == '{http://psi.hupo.org/ms/mzml}spectrum':
                # 构建完整的谱图数据
                spectrum_data = {}
                spectrum_data['id'] = current_spectrum.get('id', '')
                spectrum_data['ms_level'] = current_spectrum.get('ms_level', 1)
                spectrum_data['rt'] = current_spectrum.get('rt', 0.0)

                # 解析二进制数据数组
                mz_array = None
                intensity_array = None

                for bda in current_spectrum.get('binary_data_arrays', []):
                    if bda.get('name') == 'm/z array':
                        mz_array = bda.get('values', [])
                    elif bda.get('name') == 'intensity array':
                        intensity_array = bda.get('values', [])

                if mz_array and intensity_array and len(mz_array) == len(intensity_array):
                    for j in range(len(mz_array)):
                        peak_id = f"{source_name}_spec{current_spectrum.get('index', 0)}_peak{j}"
                        peaks.append({
                            'feature_id': peak_id,
                            'filename': source_name,
                            'mz': mz_array[j],
                            'rt': spectrum_data['rt'],
                            'intensity': intensity_array[j],
                            'ms_level': spectrum_data['ms_level'],
                        })

                # 重置状态
                current_spectrum = {}
                elem.clear()

            # 解析 <cvParam> 元素
            elif elem.tag == '{http://psi.hupo.org/ms/mzml}cvParam':
                accession = elem.get('accession', '')
                value = elem.get('value', '')
                name = elem.get('name', '')

                if accession == 'MS:1000511':  # ms level
                    current_spectrum['ms_level'] = int(value)
                elif accession == 'MS:1000016':  # scan start time
                    current_spectrum['rt'] = float(value)
                    if 'unit' not in current_spectrum:
                        unit = elem.get('unitAccession', '')
                        if unit == 'UO:0000031':  # minutes
                            current_spectrum['rt'] *= 60.0  # 转换为秒

            # 解析 <binaryDataArray> 元素
            elif elem.tag == '{http://psi.hupo.org/ms/mzml}binaryDataArray':
                bda_info = {}
                # 查找关联的 cvParam
                for cv_param in elem.findall('{http://psi.hupo.org/ms/mzml}cvParam'):
                    accession = cv_param.get('accession', '')
                    name = cv_param.get('name', '')
                    if accession in ('MS:1000514', 'MS:1000523'):
                        bda_info['name'] = 'm/z array'
                    elif accession in ('MS:1000515', 'MS:1000521'):
                        bda_info['name'] = 'intensity array'

                # 解析二进制数据
                binary_elem = elem.find('{http://psi.hupo.org/ms/mzml}binary')
                if binary_elem is not None and 'name' in bda_info:
                    try:
                        encoded = binary_elem.text.strip()
                        decoded = base64.b64decode(encoded)
                        # 确定精度：64-bit 或 32-bit
                        precision = 64
                        for cv_param in elem.findall('{http://psi.hupo.org/ms/mzml}cvParam'):
                            if cv_param.get('accession') == 'MS:1000523':
                                precision = 64
                            elif cv_param.get('accession') == 'MS:1000521':
                                precision = 32

                        if precision == 64:
                            values = list(struct.unpack(f'<{len(decoded)//8}d', decoded))
                        else:
                            values = list(struct.unpack(f'<{len(decoded)//4}f', decoded))

                        bda_info['values'] = values
                    except Exception:
                        bda_info['values'] = []

                if 'binary_data_arrays' not in current_spectrum:
                    current_spectrum['binary_data_arrays'] = []
                current_spectrum['binary_data_arrays'].append(bda_info)

                elem.clear()

            # 记录谱图索引（用于生成唯一 ID）
            elif elem.tag == '{http://psi.hupo.org/ms/mzml}spectrumList':
                pass  # spectrumList 不需要特殊处理

    except ET.ParseError as e:
        print(f"  [警告] XML 解析错误: {e}")

    # 为每个峰添加索引
    for idx, peak in enumerate(peaks):
        peak['index'] = idx

    return peaks


def _write_peak_table(peaks: list, output_csv: str):
    """
    将峰列表写入 CSV 文件。

    Parameters
    ----------
    peaks : list of dict
        峰数据列表。
    output_csv : str
        输出 CSV 文件路径。
    """
    if not peaks:
        return

    fieldnames = ['feature_id', 'filename', 'mz', 'rt', 'intensity', 'ms_level']

    with open(output_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(peaks)


# ============================= FeatureFinderMetabo 特征检测 =============================
# OpenMS-FeatureFinderMetabo
def feature_detection_openms_featurefinder_impl(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.mzML",
    mass_error: float = 10.0,
    intensity_threshold: float = 1000.0,
    min_peak_width: float = 0.05,
    max_peak_width: float = 0.5,
    snr_threshold: float = 3.0,
    threads: Optional[int] = None,
    openms_path: str = "",
):
    """
    使用 OpenMS FeatureFinderMetabo 对 LC-MS 数据进行基于质量轨迹的特征检测。

    FeatureFinderMetabo 是 OpenMS 为代谢组学设计的核心特征检测算法：
    - 在 m/z 维度上连接连续的质谱信号，构建质量轨迹（mass traces）
    - 在 RT 维度上检测色谱峰
    - 自动过滤同位素峰、加合物峰和噪声信号
    - 将属于同一化合物的同位素峰组装为特征（feature）

    适用于高分辨 LC-MS 非靶向代谢组学数据（Orbitrap, Q-TOF 等）。

    Parameters
    ----------
    input_dir : str
        包含 centroided .mzML 文件的输入目录。
    output_dir : str
        输出目录，保存特征表 CSV 和 featureXML 文件。
    file_pattern : str, default="*.mzML"
        mzML 文件匹配模式。
    mass_error : float, default=10.0
        质量容差（ppm），用于连接相邻扫描中属于同一质量轨迹的信号。
    intensity_threshold : float, default=1000.0
        最小强度阈值，低于此值的信号被忽略。
    min_peak_width : float, default=0.05
        最小色谱峰宽度（分钟）。
    max_peak_width : float, default=0.5
        最大色谱峰宽度（分钟）。
    snr_threshold : float, default=3.0
        信噪比阈值，低于此值的特征被过滤。
    threads : int, optional
        并行线程数。
    openms_path : str, default=""
        OpenMS 可执行文件所在目录路径。
    """

    print(f"\n[OpenMS-FeatureFinderMetabo] 开始代谢组特征检测...")
    print(f"  输入目录: {input_dir}")
    print(f"  质量容差: {mass_error} ppm")
    print(f"  强度阈值: {intensity_threshold}")
    print(f"  峰宽范围: {min_peak_width} - {max_peak_width} min")

    os.makedirs(output_dir, exist_ok=True)
    input_abs = os.path.abspath(input_dir)
    output_abs = os.path.abspath(output_dir)

    feature_finder_bin = os.path.join(openms_path, "FeatureFinderMetabo") if openms_path else "FeatureFinderMetabo"
    text_exporter_bin = os.path.join(openms_path, "TextExporter") if openms_path else "TextExporter"

    mzml_files = sorted(glob.glob(os.path.join(input_abs, file_pattern)))
    if not mzml_files:
        raise FileNotFoundError(f"在 {input_abs} 中未找到匹配 {file_pattern} 的 .mzML 文件")

    print(f"  找到 {len(mzml_files)} 个输入文件")

    for i, mzml_file in enumerate(mzml_files):
        basename = os.path.splitext(os.path.basename(mzml_file))[0]
        feature_xml = os.path.join(output_abs, f"{basename}.featureXML")
        feature_csv = os.path.join(output_abs, f"{basename}_features.csv")

        print(f"\n  处理文件 [{i+1}/{len(mzml_files)}]: {os.path.basename(mzml_file)}")

        # Step 1: FeatureFinderMetabo（OpenMS 3.x 参数名）
        cmd = [feature_finder_bin]
        cmd += ["-in", mzml_file]
        cmd += ["-out", feature_xml]
        cmd += ["-algorithm:mtd:mass_error_ppm", str(mass_error)]
        cmd += ["-algorithm:common:noise_threshold_int", str(intensity_threshold)]
        cmd += ["-algorithm:common:chrom_fwhm", str((min_peak_width + max_peak_width) / 2 * 60)]
        cmd += ["-algorithm:common:chrom_peak_snr", str(snr_threshold)]

        if threads is not None:
            cmd += ["-threads", str(threads)]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"  [警告] FeatureFinderMetabo 返回非零退出码: {result.returncode}")
            if result.stderr:
                print(f"  stderr: {result.stderr[:500]}")
            continue

        if not os.path.exists(feature_xml):
            print(f"  [警告] 未生成 featureXML 文件")
            continue

        print(f"  featureXML 已生成: {os.path.basename(feature_xml)}")

        # Step 2: TextExporter 将 featureXML 转换为 CSV
        export_cmd = [text_exporter_bin]
        export_cmd += ["-in", feature_xml]
        export_cmd += ["-out", feature_csv]
        export_cmd += ["-no_ids"]

        export_result = subprocess.run(export_cmd, capture_output=True, text=True)

        if export_result.returncode == 0 and os.path.exists(feature_csv):
            print(f"  特征表已导出: {os.path.basename(feature_csv)}")
        else:
            print(f"  [警告] TextExporter 导出失败（featureXML 文件仍可用）")

    print(f"\n✅ FeatureFinderMetabo 处理完成，输出目录: {output_abs}")


# ============================= IsotopeTools 同位素分析 =============================
# OpenMS-IsotopeTools（OpenMS ≥ 3.0 使用 MetaboliteAdductDecharger，旧版用 FeatureDeconvolution）
def _filter_featurexml_top_intensity(input_path: str, output_path: str, top_n: int):
    """按强度排序，保留 top-N 个特征，写入过滤后的 featureXML。"""
    tree = ET.parse(input_path)
    root = tree.getroot()
    ns = {"fm": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}

    # 收集 feature 元素及其强度
    features = []
    feature_list_el = root.find("featureList")
    if feature_list_el is None:
        return False

    for f in feature_list_el.findall("feature"):
        intensity_el = f.find("intensity")
        intensity = float(intensity_el.text) if intensity_el is not None and intensity_el.text else 0.0
        features.append((intensity, f))

    if len(features) <= top_n:
        return False  # 不需要过滤

    # 按强度降序排序，保留 top-N
    features.sort(key=lambda x: x[0], reverse=True)
    top_features = features[:top_n]

    # 从 featureList 中移除所有 feature，再添加 top-N
    for f in feature_list_el.findall("feature"):
        feature_list_el.remove(f)
    for _, f in top_features:
        feature_list_el.append(f)

    feature_list_el.set("count", str(len(top_features)))
    tree.write(output_path, encoding="ISO-8859-1", xml_declaration=True)
    return True


def isotope_analysis_openms_impl(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.featureXML",
    max_charge: int = 3,
    max_features: int = 0,
    openms_path: str = "",
):
    """
    使用 OpenMS 同位素分析工具链对已完成特征检测的数据进行电荷估计与加合物去卷积。

    OpenMS 3.x 起，原先的 FeatureDeconvolution 已合并入 MetaboliteAdductDecharger，
    本函数使用 MetaboliteFeatureDeconvolution 算法完成电荷状态估计。
    该工具识别同一化合物的同位素峰簇（M0, M+1, M+2 等），
    基于特征间 m/z 差和加合物/电荷模型进行匹配。

    Parameters
    ----------
    input_dir : str
        包含 featureXML 文件的输入目录。
    output_dir : str
        输出目录。
    file_pattern : str, default="*.featureXML"
        用于匹配输入文件的 glob 模式。
    max_charge : int, default=3
        最大电荷数。
    max_features : int, default=0
        按强度保留的 top-N 特征数。0 表示不过滤，使用全部特征。
        MetaboliteAdductDecharger 的图优化对大特征集（>5000）非常慢，
        建议设为 2000~5000。低强度特征的同位素信噪比本身不可靠。
    openms_path : str, default=""
        OpenMS 可执行文件所在目录路径。需 OpenMS ≥ 3.0。
    """

    featurexml_list = sorted(glob.glob(os.path.join(input_dir, file_pattern)))

    if not featurexml_list:
        print(f"\n[OpenMS-IsotopeTools] 警告：在 {input_dir} 中未找到匹配 {file_pattern} 的文件")
        return

    print(f"\n[OpenMS-IsotopeTools] 开始同位素分析，共 {len(featurexml_list)} 个文件（{input_dir}/*{file_pattern}）...")
    if max_features > 0:
        print(f"  强度预过滤: 保留 top-{max_features} 特征")

    os.makedirs(output_dir, exist_ok=True)
    decharger_bin = os.path.join(openms_path, "MetaboliteAdductDecharger") if openms_path else "MetaboliteAdductDecharger"
    text_exporter_bin = os.path.join(openms_path, "TextExporter") if openms_path else "TextExporter"

    for i, fm in enumerate(featurexml_list, 1):
        input_abs = os.path.abspath(fm)
        basename = os.path.splitext(os.path.basename(fm))[0]
        tmp_dir = output_dir

        print(f"\n  [{i}/{len(featurexml_list)}] {os.path.basename(fm)}")

        # 可选：强度预过滤
        if max_features > 0:
            filtered_fm = os.path.join(tmp_dir, f"{basename}_top{max_features}.featureXML")
            filtered = _filter_featurexml_top_intensity(input_abs, filtered_fm, max_features)
            if filtered:
                processing_fm = filtered_fm
                print(f"    强度过滤: 保留 top-{max_features} 特征")
            else:
                processing_fm = input_abs
        else:
            processing_fm = input_abs

        # Step 1: 电荷估计 + 加合物去卷积 — MetaboliteAdductDecharger（OpenMS 3.x）
        charged_fm = os.path.join(output_dir, f"{basename}_charged.featureXML")

        cmd = [decharger_bin]
        cmd += ["-in", processing_fm]
        cmd += ["-out_fm", charged_fm]
        cmd += ["-algorithm:MetaboliteFeatureDeconvolution:charge_min", "1"]
        cmd += ["-algorithm:MetaboliteFeatureDeconvolution:charge_max", str(max_charge)]
        cmd += ["-algorithm:MetaboliteFeatureDeconvolution:q_try", "feature"]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"    [警告] MetaboliteAdductDecharger 失败 (rc={result.returncode}): {result.stderr[:300]}")
            continue

        print(f"    电荷估计完成: {os.path.basename(charged_fm)}")

        # Step 2: 导出 CSV
        output_csv = os.path.join(output_dir, f"{basename}_isotope_annotated.csv")

        export_cmd = [text_exporter_bin]
        export_cmd += ["-in", charged_fm]
        export_cmd += ["-out", output_csv]

        subprocess.run(export_cmd, capture_output=True, text=True)

    print(f"\n✅ 同位素分析完成，输出目录: {output_dir}")


# ============================= PeakGroup 峰组对齐与特征分组 =============================
# OpenMS-PeakGroup
def peak_group_alignment_openms_impl(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.featureXML",
    rt_max_difference: float = 100.0,
    mz_max_difference: float = 0.3,
    mz_unit: str = "Da",
    aligner_rt_max_difference: float = 100.0,
    aligner_mz_max_difference: float = 0.3,
    aligner_mz_unit: str = "Da",
    max_num_peaks_considered: int = -1,
    second_nearest_gap: float = 2.0,
    ignore_charge: bool = False,
    use_identifications: bool = False,
    threads: Optional[int] = None,
    openms_path: str = "",
):
    """
    使用 OpenMS 工具链对多样本 LC-MS 特征进行保留时间对齐和峰组跨越样本分组。

    处理流程:
    1. MapAlignerPoseClustering: 基于 PoseClustering 算法对多个特征图进行保留时间对齐
       - 在特征图中找到对应的 landmark 特征对
       - 通过聚类估计非线性 RT 变换
       - 输出对齐后的 featureXML 和变换参数 trafoXML

    2. FeatureLinkerUnlabeled (QT): 将对齐后的特征跨样本分组
       - 基于 m/z 和 RT 相似度将不同样本中代表同一代谢物的特征归入同一组
       - 使用 QT（Quality Threshold）聚类确保分组质量
       - 输出 consensusXML（共识特征图）

    参考:
    - Kenar, E. et al. Mol. Cell. Proteomics, 2014, 13(1), 348-359.
    - Pfeuffer, J. et al. Nature Methods, 2024.

    适用于：
    - 多样本 LC-MS 非靶向代谢组学中校正保留时间漂移
    - 将多个样本中代表同一化合物的特征归入同一行
    - 作为后续统计分析和差异分析的基础

    Parameters
    ----------
    input_dir : str
        输入目录，包含 .featureXML 文件（来自 FeatureFinderMetabo 等特征检测工具）。
    output_dir : str
        输出目录，保存对齐后的特征文件和共识特征表。
    file_pattern : str, default="*.featureXML"
        featureXML 文件匹配模式。
    rt_max_difference : float, default=100.0
        特征链接时的最大 RT 距离（秒），超过此值的特征永远不会被配对。
    mz_max_difference : float, default=0.3
        特征链接时的最大 m/z 距离。
    mz_unit : str, default="Da"
        m/z 距离单位："Da"（道尔顿）或 "ppm"。
    aligner_rt_max_difference : float, default=100.0
        RT 对齐时的最大 RT 距离（秒）。
    aligner_mz_max_difference : float, default=0.3
        RT 对齐时的最大 m/z 距离。
    aligner_mz_unit : str, default="Da"
        RT 对齐时的 m/z 距离单位："Da" 或 "ppm"。
    max_num_peaks_considered : int, default=-1
        RT 对齐时每个图谱考虑的最大特征数，-1 表示全部使用。
    second_nearest_gap : float, default=2.0
        特征链接时，只有当最近邻距离乘以该因子仍小于第二近邻距离时，
        才认为匹配可靠。值越大越严格。
    ignore_charge : bool, default=False
        特征链接时是否忽略电荷状态。False 表示要求相同电荷。
    use_identifications : bool, default=False
        是否使用肽段鉴定信息辅助特征链接。
    threads : int, optional
        并行线程数。
    openms_path : str, default=""
        OpenMS 可执行文件所在目录路径。留空则使用系统 PATH 中的默认路径。
    """

    print(f"\n[OpenMS-PeakGroup] 开始峰组对齐与特征分组...")
    print(f"  输入目录: {input_dir}")
    print(f"  RT 对齐容差: {aligner_rt_max_difference}s, m/z: {aligner_mz_max_difference}{aligner_mz_unit}")
    print(f"  链接容差: RT={rt_max_difference}s, m/z={mz_max_difference}{mz_unit}")

    os.makedirs(output_dir, exist_ok=True)
    input_abs = os.path.abspath(input_dir)
    output_abs = os.path.abspath(output_dir)

    # 构建可执行文件路径
    map_aligner_bin = os.path.join(openms_path, "MapAlignerPoseClustering") if openms_path else "MapAlignerPoseClustering"
    feature_linker_bin = os.path.join(openms_path, "FeatureLinkerUnlabeled") if openms_path else "FeatureLinkerUnlabeled"
    text_exporter_bin = os.path.join(openms_path, "TextExporter") if openms_path else "TextExporter"

    # 查找输入文件
    feature_files = sorted(glob.glob(os.path.join(input_abs, file_pattern)))
    if not feature_files:
        raise FileNotFoundError(f"在 {input_abs} 中未找到匹配 {file_pattern} 的 featureXML 文件")

    if len(feature_files) < 2:
        raise ValueError(f"至少需要 2 个 featureXML 文件进行对齐，当前找到 {len(feature_files)} 个")

    print(f"  找到 {len(feature_files)} 个特征文件")

    # 中间文件路径
    aligned_dir = os.path.join(output_abs, "aligned")
    os.makedirs(aligned_dir, exist_ok=True)

    trafo_dir = os.path.join(output_abs, "trafo")
    os.makedirs(trafo_dir, exist_ok=True)

    aligned_files = []
    trafo_files = []

    # =========================== Step 1: MapAlignerPoseClustering ===========================
    print(f"\n  [Step 1/2] MapAlignerPoseClustering: 保留时间对齐...")

    for i, feat_file in enumerate(feature_files):
        basename = os.path.splitext(os.path.basename(feat_file))[0]
        aligned_out = os.path.join(aligned_dir, f"{basename}_aligned.featureXML")
        trafo_out = os.path.join(trafo_dir, f"{basename}.trafoXML")

        aligned_files.append(aligned_out)
        trafo_files.append(trafo_out)

    # MapAlignerPoseClustering 一次性处理所有文件
    align_cmd = [map_aligner_bin]
    for feat_file in feature_files:
        align_cmd += ["-in", feat_file]
    for aligned_file in aligned_files:
        align_cmd += ["-out", aligned_file]
    for trafo_file in trafo_files:
        align_cmd += ["-trafo_out", trafo_file]

    align_cmd += ["-algorithm:pairfinder:distance_RT:max_difference", str(aligner_rt_max_difference)]
    align_cmd += ["-algorithm:pairfinder:distance_MZ:max_difference", str(aligner_mz_max_difference)]
    align_cmd += ["-algorithm:pairfinder:distance_MZ:unit", aligner_mz_unit]
    align_cmd += ["-algorithm:max_num_peaks_considered", str(max_num_peaks_considered)]

    if threads is not None:
        align_cmd += ["-threads", str(threads)]

    print(f"  对齐 {len(feature_files)} 个特征图...")
    result = subprocess.run(align_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  [警告] MapAlignerPoseClustering 返回非零退出码: {result.returncode}")
        if result.stderr:
            print(f"  stderr: {result.stderr[:500]}")
        print(f"  尝试跳过对齐步骤，直接进行特征链接...")
        # 使用原始文件进行链接
        aligned_files = list(feature_files)
    else:
        print(f"  ✅ RT 对齐完成，变换文件已保存至: {trafo_dir}")

    # ========================= Step 2: FeatureLinkerUnlabeled ===========================
    print(f"\n  [Step 2/2] FeatureLinkerUnlabeled: 跨样本特征分组...")

    consensus_xml = os.path.join(output_abs, "consensus_map.consensusXML")
    consensus_csv = os.path.join(output_abs, "feature_table_peakgroup.csv")

    link_cmd = [feature_linker_bin]
    for aligned_file in aligned_files:
        link_cmd += ["-in", aligned_file]
    link_cmd += ["-out", consensus_xml]

    # 距离参数
    link_cmd += ["-algorithm:distance_RT:max_difference", str(rt_max_difference)]
    link_cmd += ["-algorithm:distance_RT:exponent", "1.0"]
    link_cmd += ["-algorithm:distance_RT:weight", "1.0"]
    link_cmd += ["-algorithm:distance_MZ:max_difference", str(mz_max_difference)]
    link_cmd += ["-algorithm:distance_MZ:unit", mz_unit]
    link_cmd += ["-algorithm:distance_MZ:exponent", "2.0"]
    link_cmd += ["-algorithm:distance_MZ:weight", "1.0"]
    link_cmd += ["-algorithm:distance_intensity:weight", "0.0"]

    # 链接参数
    link_cmd += ["-algorithm:second_nearest_gap", str(second_nearest_gap)]
    link_cmd += ["-algorithm:use_identifications", str(use_identifications).lower()]
    link_cmd += ["-algorithm:ignore_charge", str(ignore_charge).lower()]

    if threads is not None:
        link_cmd += ["-threads", str(threads)]

    result = subprocess.run(link_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  [错误] FeatureLinkerUnlabeled 失败: {result.returncode}")
        if result.stderr:
            print(f"  stderr: {result.stderr[:500]}")
        return

    if not os.path.exists(consensus_xml):
        print(f"  [错误] 未生成 consensusXML 文件")
        return

    print(f"  ✅ 特征分组完成: {os.path.basename(consensus_xml)}")

    # ====================== Step 3: TextExporter 导出 CSV ======================
    print(f"\n  [导出] 共识特征表 → CSV...")

    export_cmd = [text_exporter_bin]
    export_cmd += ["-in", consensus_xml]
    export_cmd += ["-out", consensus_csv]

    export_result = subprocess.run(export_cmd, capture_output=True, text=True)

    if export_result.returncode == 0 and os.path.exists(consensus_csv):
        print(f"  ✅ 共识特征表已导出: {os.path.basename(consensus_csv)}")
    else:
        print(f"  [警告] TextExporter 导出失败（consensusXML 文件仍可用）")

    # ============================ 输出汇总 ============================
    print(f"\n✅ OpenMS-PeakGroup 处理完成")
    print(f"  对齐特征文件: {aligned_dir}")
    print(f"  RT 变换参数: {trafo_dir}")
    print(f"  共识特征图: {consensus_xml}")
    if os.path.exists(consensus_csv):
        print(f"  共识特征表: {consensus_csv}")


if __name__ == "__main__":
    input_base = "/data2/luxiang/MOA/inputspace"
    output_base = "/data2/luxiang/MOA/outputspace"
    openms_bin = "/home/luxiang/anaconda/envs/openms_env/bin"

    # PeakPickerHiRes: 峰拾取（centroiding）
    # peak_picking_openms_impl(
    #     input_dir=f"{input_base}/mzml",
    #     output_dir=f"{output_base}/peak_detection/peak_picking_openms",
    #     openms_path=openms_bin,
    # )

    # FeatureFinderMetabo: 特征检测
    # feature_detection_openms_featurefinder_impl(
    #     input_dir=f"{output_base}/data_conversion/mzml",
    #     output_dir=f"{output_base}/peak_detection/feature_detection_openms",
    #     file_pattern="*.mzML",
    #     openms_path=openms_bin,
    # )

    # IsotopeTools: 同位素分析
    isotope_analysis_openms_impl(
        input_dir=f"{output_base}/peak_detection/feature_detection_openms",
        output_dir=f"{output_base}/isotope_identification/isotope_openms",
        max_charge=3,
        max_features=2000,
        openms_path=openms_bin,
    )

    # PeakGroup: 峰组对齐
    # peak_group_alignment_openms_impl(
    #     input_dir=f"{output_base}/peak_detection/feature_detection_openms",
    #     output_dir=f"{output_base}/peak_alignment/peak_group_openms",
    #     openms_path=openms_bin,
    # )
