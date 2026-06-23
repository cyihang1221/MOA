import json
import math
import os
import subprocess
import io
import contextlib
from pathlib import Path
from matchms.importing import load_from_mgf
from src.tools.convert_raw_to_mzml import (
    convert_raw_to_mzml_ThermoRawFileParser_impl,
    convert_raw_to_mzml_msconvert_impl,
    mzml_directory_to_mgf_impl,
)


def _greedy_peak_matches(
    query_mz: list[float],
    reference_mz: list[float],
    mz_tolerance: float,
) -> list[tuple[int, int]]:
    """
    在给定 m/z 容差下进行一对一贪心匹配，返回 (query_idx, reference_idx) 对。
    输入可无序，函数内部会按 m/z 排序后匹配。
    """
    if mz_tolerance <= 0:
        raise ValueError("mz_tolerance 必须大于 0。")

    q_sorted = sorted(enumerate(query_mz), key=lambda x: x[1])
    r_sorted = sorted(enumerate(reference_mz), key=lambda x: x[1])

    matches: list[tuple[int, int]] = []
    i = 0
    j = 0
    while i < len(q_sorted) and j < len(r_sorted):
        qi, qmz = q_sorted[i]
        rj, rmz = r_sorted[j]
        delta = qmz - rmz
        if abs(delta) <= mz_tolerance:
            matches.append((qi, rj))
            i += 1
            j += 1
        elif delta < 0:
            i += 1
        else:
            j += 1
    return matches


def _entropy(prob_vector: list[float]) -> float:
    return -sum(p * math.log(p) for p in prob_vector if p > 0)


class _WordVectorWrapper:
    """
    为仅有 KeyedVectors 的情况提供 .wv 属性，兼容 spec2vec 的模型访问方式。
    """

    def __init__(self, keyed_vectors):
        self.wv = keyed_vectors


# ============================= Cosine 相似度实现 =============================
def library_match_cosine_impl(
    query_vector: list[float],
    reference_vector: list[float]
) -> float:
    """
    计算两个向量的余弦相似度（Cosine Similarity）。
    返回值范围为 [-1, 1]，在质谱匹配场景中通常关注 [0, 1] 区间。
    """
    if len(query_vector) == 0 or len(reference_vector) == 0:
        raise ValueError("query_vector 和 reference_vector 不能为空。")

    if len(query_vector) != len(reference_vector):
        raise ValueError("query_vector 和 reference_vector 长度必须一致。")

    dot_product = sum(q * r for q, r in zip(query_vector, reference_vector))
    query_norm = math.sqrt(sum(q * q for q in query_vector))
    reference_norm = math.sqrt(sum(r * r for r in reference_vector))

    if query_norm == 0 or reference_norm == 0:
        raise ValueError("向量范数不能为 0，请检查输入是否全为 0。")

    cosine_score = dot_product / (query_norm * reference_norm)
    return float(cosine_score)


# ============================= Jaccard 相似度实现 =============================
def library_match_jaccard_impl(
    query_vector: list[float],
    reference_vector: list[float]
) -> float:
    """
    计算两个向量的 Jaccard 相似度。
    这里将非零元素视为“存在特征”，用于集合交并比计算。
    """
    if len(query_vector) == 0 or len(reference_vector) == 0:
        raise ValueError("query_vector 和 reference_vector 不能为空。")

    if len(query_vector) != len(reference_vector):
        raise ValueError("query_vector 和 reference_vector 长度必须一致。")

    query_set = {idx for idx, val in enumerate(query_vector) if val != 0}
    reference_set = {idx for idx, val in enumerate(reference_vector) if val != 0}

    union_size = len(query_set | reference_set)
    if union_size == 0:
        raise ValueError("两个向量均无非零特征，无法计算 Jaccard。")

    intersection_size = len(query_set & reference_set)
    jaccard_score = intersection_size / union_size
    return float(jaccard_score)


def library_match_jaccard_peaks_impl(
    query_mz: list[float],
    query_intensity: list[float],
    reference_mz: list[float],
    reference_intensity: list[float],
    mz_tolerance: float = 0.01,
) -> float:
    """
    峰级 Jaccard：以 m/z 容差匹配到的峰对作为交集，未匹配峰作为并集剩余部分。
    """
    _validate_spectrum_arrays(query_mz, query_intensity, "query")
    _validate_spectrum_arrays(reference_mz, reference_intensity, "reference")
    matches = _greedy_peak_matches(query_mz, reference_mz, mz_tolerance)
    inter = len(matches)
    union = len(query_mz) + len(reference_mz) - inter
    if union <= 0:
        raise ValueError("无法计算峰级 Jaccard，谱峰数量异常。")
    return float(inter / union)


def library_match_cosine_peaks_impl(
    query_mz: list[float],
    query_intensity: list[float],
    reference_mz: list[float],
    reference_intensity: list[float],
    mz_tolerance: float = 0.01,
    intensity_power: float = 0.5,
) -> float:
    """
    峰级 Cosine：先按 m/z 容差做一对一匹配，再计算加权点积/范数。
    intensity_power=0.5 常用于降低高强度峰主导效应。
    """
    _validate_spectrum_arrays(query_mz, query_intensity, "query")
    _validate_spectrum_arrays(reference_mz, reference_intensity, "reference")
    if intensity_power <= 0:
        raise ValueError("intensity_power 必须大于 0。")

    q_w = [max(0.0, float(i)) ** intensity_power for i in query_intensity]
    r_w = [max(0.0, float(i)) ** intensity_power for i in reference_intensity]
    matches = _greedy_peak_matches(query_mz, reference_mz, mz_tolerance)

    dot_product = sum(q_w[qi] * r_w[rj] for qi, rj in matches)
    q_norm = math.sqrt(sum(v * v for v in q_w))
    r_norm = math.sqrt(sum(v * v for v in r_w))
    if q_norm == 0 or r_norm == 0:
        raise ValueError("峰强度向量范数不能为 0。")
    return float(dot_product / (q_norm * r_norm))


# ============================= Spectral entropy 相似度实现 =============================
def library_match_spectral_entropy_impl(
    query_vector: list[float],
    reference_vector: list[float]
) -> float:
    """
    使用 ms-entropy 官方接口计算 Spectral Entropy 相似度。
    这里把向量索引映射为伪 m/z（1..N）并用很小容差进行逐位匹配。
    """
    if len(query_vector) == 0 or len(reference_vector) == 0:
        raise ValueError("query_vector 和 reference_vector 不能为空。")

    if len(query_vector) != len(reference_vector):
        raise ValueError("query_vector 和 reference_vector 长度必须一致。")

    if any(v < 0 for v in query_vector) or any(v < 0 for v in reference_vector):
        raise ValueError("Spectral entropy 输入向量不能包含负值。")

    import numpy as np
    from ms_entropy import calculate_entropy_similarity

    query_sum = float(sum(query_vector))
    reference_sum = float(sum(reference_vector))
    if query_sum == 0 or reference_sum == 0:
        raise ValueError("向量总强度不能为 0。")

    # 伪谱图：m/z 用索引表示，intensity 用原向量值
    query_peaks = np.asarray([[float(i + 1), float(v)] for i, v in enumerate(query_vector)], dtype=np.float32)
    reference_peaks = np.asarray([[float(i + 1), float(v)] for i, v in enumerate(reference_vector)], dtype=np.float32)

    similarity = calculate_entropy_similarity(
        query_peaks,
        reference_peaks,
        ms2_tolerance_in_da=1e-6,
        clean_spectra=False,
    )
    similarity = max(0.0, min(1.0, float(similarity)))
    return similarity


def library_match_spectral_entropy_peaks_impl(
    query_mz: list[float],
    query_intensity: list[float],
    reference_mz: list[float],
    reference_intensity: list[float],
    mz_tolerance: float = 0.01,
) -> float:
    """
    峰级 Spectral Entropy：按容差分箱后计算谱熵相似度。
    """
    _validate_spectrum_arrays(query_mz, query_intensity, "query")
    _validate_spectrum_arrays(reference_mz, reference_intensity, "reference")
    vq, vr = _binned_intensity_vectors(
        query_mz,
        query_intensity,
        reference_mz,
        reference_intensity,
        bin_size=max(mz_tolerance, 1e-4),
    )
    return library_match_spectral_entropy_impl(vq, vr)


# ============================= Spec2Vec 相似度实现 =============================
def library_match_spec2vec_impl(
    query_mz: list[float],
    query_intensity: list[float],
    reference_mz: list[float],
    reference_intensity: list[float],
    model_path: str | None = None,
    precursor_mz: float | None = None,
    reference_precursor_mz: float | None = None,
    n_decimals: int = 2
) -> float:
    """
    基于真实 Spec2Vec 模型计算两条谱图的相似度。
    模型路径默认从环境变量 SPEC2VEC_MODEL_PATH 读取。
    """
    _validate_spectrum_arrays(query_mz, query_intensity, "query")
    _validate_spectrum_arrays(reference_mz, reference_intensity, "reference")

    resolved_model_path = model_path or os.getenv("SPEC2VEC_MODEL_PATH")
    if not resolved_model_path:
        raise ValueError("未提供 Spec2Vec 模型路径，请传入 model_path 或在 .env 中设置 SPEC2VEC_MODEL_PATH。")

    model_file = Path(resolved_model_path)
    if not model_file.exists():
        raise FileNotFoundError(f"Spec2Vec 模型文件不存在: {resolved_model_path}")

    sink = io.StringIO()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        from gensim.models import KeyedVectors, Word2Vec
        from spec2vec import Spec2Vec, SpectrumDocument

        if model_file.suffix in {".kv", ".bin"}:
            kv_model = KeyedVectors.load(str(model_file), mmap="r")
            model = _WordVectorWrapper(kv_model)
        else:
            model = Word2Vec.load(str(model_file))

        from matchms.filtering import normalize_intensities

        query_spectrum = _build_spectrum(query_mz, query_intensity, precursor_mz)
        reference_spectrum = _build_spectrum(
            reference_mz, reference_intensity, reference_precursor_mz
        )
        query_spectrum = normalize_intensities(query_spectrum)
        reference_spectrum = normalize_intensities(reference_spectrum)
        if query_spectrum is None or reference_spectrum is None:
            raise ValueError("Spec2Vec：归一化后谱图无效，请检查峰表。")

        scorer = Spec2Vec(model=model)
        query_doc = SpectrumDocument(query_spectrum, n_decimals=n_decimals)
        reference_doc = SpectrumDocument(reference_spectrum, n_decimals=n_decimals)

        return float(scorer.pair(query_doc, reference_doc))


# ============================= MS2DeepScore 相似度实现 =============================
def library_match_ms2deepscore_impl(
    query_mz: list[float],
    query_intensity: list[float],
    reference_mz: list[float],
    reference_intensity: list[float],
    model_path: str | None = None,
    precursor_mz: float | None = None,
    reference_precursor_mz: float | None = None,
    ionmode: str = "positive",
) -> float:
    """
    基于真实 MS2DeepScore 模型计算两条谱图的相似度。
    模型路径默认从环境变量 MS2DEEPSCORE_MODEL_PATH 读取。
    """
    _validate_spectrum_arrays(query_mz, query_intensity, "query")
    _validate_spectrum_arrays(reference_mz, reference_intensity, "reference")

    resolved_model_path = model_path or os.getenv("MS2DEEPSCORE_MODEL_PATH")
    if not resolved_model_path:
        raise ValueError("未提供 MS2DeepScore 模型路径，请传入 model_path 或在 .env 中设置 MS2DEEPSCORE_MODEL_PATH。")

    model_file = Path(resolved_model_path)
    if not model_file.exists():
        raise FileNotFoundError(f"MS2DeepScore 模型文件不存在: {resolved_model_path}")

    query_spectrum = _build_spectrum(query_mz, query_intensity, precursor_mz, ionmode=ionmode)
    reference_spectrum = _build_spectrum(reference_mz, reference_intensity, reference_precursor_mz, ionmode=ionmode)

    # ms2deepscore 推理过程会输出 tqdm 进度条到 stdout/stderr，
    # 在 MCP stdio 场景下会污染 JSONRPC 通道，因此这里做静默重定向。
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        from ms2deepscore import MS2DeepScore
        model = _load_ms2deepscore_model_compat(str(model_file))
        scorer = MS2DeepScore(model)
        score = float(scorer.pair(query_spectrum, reference_spectrum))
    return score


# ============================= BLINK 相似度实现 =============================
def library_match_blink_impl(
    query_mz: list[float],
    query_intensity: list[float],
    reference_mz: list[float],
    reference_intensity: list[float],
    mz_tolerance: float = 0.01
) -> float:
    """
    使用 BLINK 库官方接口计算相似度（alignment-free sparse binning）。
    返回 BLINK 结果中的 mzi 分数（1x1 稀疏矩阵的 [0,0] 元素）。
    """
    if len(query_mz) == 0 or len(reference_mz) == 0:
        raise ValueError("query_mz 和 reference_mz 不能为空。")

    if len(query_mz) != len(query_intensity):
        raise ValueError("query_mz 和 query_intensity 长度必须一致。")

    if len(reference_mz) != len(reference_intensity):
        raise ValueError("reference_mz 和 reference_intensity 长度必须一致。")

    if mz_tolerance <= 0:
        raise ValueError("mz_tolerance 必须大于 0。")

    if any(v < 0 for v in query_intensity) or any(v < 0 for v in reference_intensity):
        raise ValueError("峰强度不能为负值。")

    import numpy as np
    import blink

    q_array = np.asarray(list(zip(query_mz, query_intensity)), dtype=float)
    r_array = np.asarray(list(zip(reference_mz, reference_intensity)), dtype=float)

    discretized = blink.discretize_spectra(
        mzis_s1=[q_array],
        mzis_s2=[r_array],
        precursor_mzs_s1=[0.0],
        precursor_mzs_s2=[0.0],
        tolerance=float(mz_tolerance),
        bin_width=max(float(mz_tolerance) / 10.0, 1e-4),
        intensity_power=0.5,
        mass_diffs=[0],
        network_score=False,
        trim_empty=False,
        remove_duplicates=False,
    )
    score_dict = blink.score_sparse_spectra(discretized, gpu=False)
    # BLINK 返回的 mzi/mzc 是稀疏矩阵；单谱对场景下 shape 为 (1,1)
    blink_score = float(score_dict["mzi"][0, 0])
    blink_score = max(0.0, min(1.0, blink_score))
    return blink_score


# ============================= MS-BERT 相似度实现 =============================
def library_match_msbert_impl(
    query_mz: list[float],
    query_intensity: list[float],
    reference_mz: list[float],
    reference_intensity: list[float],
    script_path: str | None = None,
    model_path: str | None = None,
    precursor_mz: float | None = None,
    reference_precursor_mz: float | None = None,
    timeout_sec: int = 120
) -> float:
    """
    外部脚本推理版模板：
    - 通过 subprocess 调用你自己的 MS-BERT 推理脚本
    - 推理脚本需输出 JSON: {"score": 0.123}

    脚本路径默认读取环境变量 MSBERT_INFER_SCRIPT；
    模型路径默认读取环境变量 MSBERT_MODEL_PATH。
    """
    _validate_spectrum_arrays(query_mz, query_intensity, "query")
    _validate_spectrum_arrays(reference_mz, reference_intensity, "reference")

    resolved_script_path = script_path or os.getenv("MSBERT_INFER_SCRIPT")
    resolved_model_path = model_path or os.getenv("MSBERT_MODEL_PATH")

    if not resolved_script_path:
        raise ValueError("未提供 MS-BERT 推理脚本路径，请传入 script_path 或在 .env 中设置 MSBERT_INFER_SCRIPT。")

    script_file = Path(resolved_script_path)
    if not script_file.exists():
        raise FileNotFoundError(f"MS-BERT 推理脚本不存在: {resolved_script_path}")

    payload = {
        "query": {
            "mz": query_mz,
            "intensity": query_intensity,
            "precursor_mz": precursor_mz,
        },
        "reference": {
            "mz": reference_mz,
            "intensity": reference_intensity,
            "precursor_mz": reference_precursor_mz,
        },
        "model_path": resolved_model_path,
    }

    result = subprocess.run(
        ["python", str(script_file)],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=True,
        timeout=timeout_sec,
    )

    try:
        output = json.loads(result.stdout.strip())
        score = float(output["score"])
    except Exception as exc:
        raise ValueError(f"MS-BERT 脚本输出格式错误，需返回 JSON 且包含 score 字段。stdout={result.stdout}") from exc

    return score


def load_peaks_from_mgf(mgf_path: str, spectrum_index: int = 0) -> tuple[list[float], list[float], float | None]:
    """
    从 MGF 文件中按索引读取一条谱图的 m/z、强度与前体 m/z（若存在）。
    """
    from matchms.importing import load_from_mgf

    path = Path(mgf_path)
    if not path.exists():
        raise FileNotFoundError(f"MGF 文件不存在: {mgf_path}")

    if spectrum_index < 0:
        raise ValueError(f"spectrum_index 不能为负: {spectrum_index}")

    spec = None
    for idx, candidate in enumerate(load_from_mgf(str(path))):
        if idx == spectrum_index:
            spec = candidate
            break
    if spec is None:
        raise ValueError(
            f"spectrum_index 越界或文件过短: {spectrum_index}（流式读取未找到该序号，"
            f"大文件请使用较小的 spectrum_index）"
        )
    mz = list(spec.peaks.mz)
    intensity = list(spec.peaks.intensities)
    precursor = None
    meta = spec.metadata or {}
    for key in ("precursor_mz", "parent_mass"):
        if key in meta and meta[key] is not None:
            try:
                precursor = float(meta[key])
            except (TypeError, ValueError):
                precursor = None
            break
    return mz, intensity, precursor


def _load_ms2deepscore_model_compat(model_path: str):
    """
    兼容两类 ms2deepscore 模型文件格式：
    1) 旧格式：包含 model_params + model_state_dict（ms2deepscore.load_model 直接支持）
    2) 新格式：包含 settings_json + state_dict（如官方 zenodo 模型）
    """
    from ms2deepscore.models import SiameseSpectralModel, load_model
    from ms2deepscore.SettingsMS2Deepscore import SettingsMS2Deepscore
    import torch
    import numpy as np

    try:
        return load_model(model_path)
    except KeyError:
        # 继续尝试新格式
        pass

    checkpoint = torch.load(model_path, map_location="cpu")
    if not isinstance(checkpoint, dict):
        raise ValueError("MS2DeepScore 模型文件格式错误：checkpoint 不是 dict。")

    if "settings_json" not in checkpoint or "state_dict" not in checkpoint:
        raise ValueError(
            "MS2DeepScore 模型文件缺少必要字段，期望包含 "
            "'settings_json' 和 'state_dict'（或旧格式 model_params/model_state_dict）。"
        )

    settings_json = checkpoint["settings_json"]
    if isinstance(settings_json, str):
        settings_dict = json.loads(settings_json)
    elif isinstance(settings_json, dict):
        settings_dict = settings_json
    else:
        raise ValueError("settings_json 字段格式不支持，应为 JSON 字符串或 dict。")

    # 按当前 ms2deepscore 版本的默认设置类型进行自动转换
    default_settings = SettingsMS2Deepscore(validate_settings=False)
    for key, value in list(settings_dict.items()):
        if not hasattr(default_settings, key):
            continue
        expected_value = getattr(default_settings, key)
        expected_type = type(expected_value)

        if expected_type is tuple and isinstance(value, list):
            settings_dict[key] = tuple(value)
        elif isinstance(expected_value, np.ndarray) and isinstance(value, list):
            settings_dict[key] = np.asarray(value)

    model = SiameseSpectralModel(
        settings=SettingsMS2Deepscore(**settings_dict, validate_settings=False)
    )
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model


def _binned_intensity_vectors(
    query_mz: list[float],
    query_intensity: list[float],
    reference_mz: list[float],
    reference_intensity: list[float],
    bin_size: float = 0.1,
) -> tuple[list[float], list[float]]:
    if not query_mz or not reference_mz:
        raise ValueError("用于分箱的 m/z 列表不能为空。")
    mz_min = min(min(query_mz), min(reference_mz)) - bin_size
    mz_max = max(max(query_mz), max(reference_mz)) + bin_size
    n_bins = max(1, int(math.ceil((mz_max - mz_min) / bin_size)))
    q_vec = [0.0] * n_bins
    r_vec = [0.0] * n_bins
    for m, i in zip(query_mz, query_intensity):
        idx = int((m - mz_min) / bin_size)
        if 0 <= idx < n_bins:
            q_vec[idx] += float(i)
    for m, i in zip(reference_mz, reference_intensity):
        idx = int((m - mz_min) / bin_size)
        if 0 <= idx < n_bins:
            r_vec[idx] += float(i)
    return q_vec, r_vec


def library_match_pair_from_mgf_impl(
    method: str,
    query_mgf_path: str,
    reference_mgf_path: str,
    query_spectrum_index: int = 0,
    reference_spectrum_index: int = 0,
    mz_tolerance: float = 0.01,
    bin_size: float = 0.1,
    model_path: str | None = None,
    precursor_mz: float | None = None,
    reference_precursor_mz: float | None = None,
    n_decimals: int = 2,
    output_dir: str | None = None,
) -> str:
    """
    从两个 MGF 文件各取一条谱图，按 method 计算相似度并返回可读摘要。
    method 支持:
    - blink, spec2vec, ms2deepscore
    - cosine_binned, spectral_entropy_binned, jaccard_binned（向量分箱版）
    - cosine_peak, spectral_entropy_peak, jaccard_peak（峰级容差版，更完整）
    自然语言别名（均映射为峰级实现，便于与 MGF 峰表对齐）:
    - cosine, jaccard, spectral entropy
    若提供 output_dir，多轮不同 method 的摘要会**追加**到同目录
    library_match_pair_results.txt，便于横向对比；各行列出规范化后的
    method（如 jaccard_peak、cosine_peak）。
    """
    method_raw = " ".join(
        method.strip().lower().replace("-", " ").replace("_", " ").split()
    )
    method_alias = {
        "blink": "blink",
        "spec2vec": "spec2vec",
        "ms2deepscore": "ms2deepscore",
        "ms2deep score": "ms2deepscore",
        # 用户常用自然语言写法 -> 默认映射到峰级实现（更适合质谱对比）
        "cosine": "cosine_peak",
        "jaccard": "jaccard_peak",
        "spectral entropy": "spectral_entropy_peak",
        # 显式实现名（峰级/分箱）也保留
        "cosine peak": "cosine_peak",
        "jaccard peak": "jaccard_peak",
        "spectral entropy peak": "spectral_entropy_peak",
        "cosine binned": "cosine_binned",
        "jaccard binned": "jaccard_binned",
        "spectral entropy binned": "spectral_entropy_binned",
    }
    method_norm = method_alias.get(method_raw, method_raw.replace(" ", "_"))
    if method_norm == "ms2deepscore":
        # TensorFlow/PyTorch/matchms 在导入和推理时可能向 stdout/stderr 打印日志，
        # 在 MCP stdio 场景下会污染 JSONRPC 通道，因此在该分支做整体静默。
        sink = io.StringIO()
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            q_mz, q_i, q_pre = load_peaks_from_mgf(query_mgf_path, query_spectrum_index)
            r_mz, r_i, r_pre = load_peaks_from_mgf(reference_mgf_path, reference_spectrum_index)
            q_pre = precursor_mz if precursor_mz is not None else q_pre
            r_pre = reference_precursor_mz if reference_precursor_mz is not None else r_pre
            score = library_match_ms2deepscore_impl(
                q_mz, q_i, r_mz, r_i, model_path, q_pre, r_pre
            )
    else:
        q_mz, q_i, q_pre = load_peaks_from_mgf(query_mgf_path, query_spectrum_index)
        r_mz, r_i, r_pre = load_peaks_from_mgf(reference_mgf_path, reference_spectrum_index)
        q_pre = precursor_mz if precursor_mz is not None else q_pre
        r_pre = reference_precursor_mz if reference_precursor_mz is not None else r_pre

    if method_norm == "blink":
        score = library_match_blink_impl(q_mz, q_i, r_mz, r_i, mz_tolerance)
    elif method_norm == "spec2vec":
        score = library_match_spec2vec_impl(
            q_mz, q_i, r_mz, r_i, model_path, q_pre, r_pre, n_decimals
        )
    elif method_norm == "ms2deepscore":
        pass
    elif method_norm == "cosine_binned":
        vq, vr = _binned_intensity_vectors(q_mz, q_i, r_mz, r_i, bin_size)
        score = library_match_cosine_impl(vq, vr)
    elif method_norm == "spectral_entropy_binned":
        vq, vr = _binned_intensity_vectors(q_mz, q_i, r_mz, r_i, bin_size)
        score = library_match_spectral_entropy_impl(vq, vr)
    elif method_norm == "jaccard_binned":
        vq, vr = _binned_intensity_vectors(q_mz, q_i, r_mz, r_i, bin_size)
        score = library_match_jaccard_impl(vq, vr)
    elif method_norm == "cosine_peak":
        score = library_match_cosine_peaks_impl(q_mz, q_i, r_mz, r_i, mz_tolerance=mz_tolerance)
    elif method_norm == "spectral_entropy_peak":
        score = library_match_spectral_entropy_peaks_impl(q_mz, q_i, r_mz, r_i, mz_tolerance=mz_tolerance)
    elif method_norm == "jaccard_peak":
        score = library_match_jaccard_peaks_impl(q_mz, q_i, r_mz, r_i, mz_tolerance=mz_tolerance)
    else:
        raise ValueError(
            f"未知 method={method!r}，请使用 blink/spec2vec/ms2deepscore/"
            f"cosine|jaccard|spectral entropy（默认峰级）或显式方法名 "
            f"cosine_binned/spectral_entropy_binned/jaccard_binned/"
            f"cosine_peak/spectral_entropy_peak/jaccard_peak"
        )

    line = (
        f"method={method_norm}, score={score:.6f}, "
        f"query={query_mgf_path}[{query_spectrum_index}] n_peaks={len(q_mz)}, "
        f"reference={reference_mgf_path}[{reference_spectrum_index}] n_peaks={len(r_mz)}"
    )
    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        log_file = out_path / "library_match_pair_results.txt"
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        line += f" | appended -> {log_file}"
    return line


def library_match_full_workflow_impl(
    raw_input_dir: str,
    mzml_output_dir: str,
    mgf_output_dir: str,
    reference_mgf_path: str,
    method: str = "ms2deepscore",
    converter: str = "thermo",
    query_mgf_path: str | None = None,
    query_spectrum_index: int = 0,
    reference_spectrum_index: int = 0,
    mz_tolerance: float = 0.01,
    bin_size: float = 0.1,
    model_path: str | None = None,
    precursor_mz: float | None = None,
    reference_precursor_mz: float | None = None,
    n_decimals: int = 2,
    output_dir: str | None = None,
) -> str:
    """
    【只使用 MS2DeepScore 的完整一站式库匹配流程】

    只使用 MS2DeepScore 方法（强制），不再支持其他 method。
    1. raw → mzML (ThermoRawFileParser)
    2. mzML → MGF (只提取 MS2 谱图)
    3. 对 query MGF 中的**所有**谱图与 reference MGF 中的**所有**谱图进行全量匹配
    4. 只保留 score > 0.5 的高分匹配
    5. 输出两个独立文件：
       - ms2deepscore_full_match.json（所有匹配）
       - ms2deepscore_high_score_summary.txt（仅高分结果，可读格式）

    关键修复：
    - 使用 add_ionmode 确保谱图有 'positive' ionmode（解决 "Feature should be ['positive'] or ['negative'], not None" 错误）
    - 不再错误使用 SpectrumDocument（那是 Spec2Vec 专用的）
    - 所有计算过程 stdout 被重定向，防止 MCP JSON-RPC 解析报错
    """
    import json
    import io
    import contextlib
    from pathlib import Path
    from matchms.importing import load_from_mgf
    from matchms.filtering import normalize_intensities
    from ms2deepscore import MS2DeepScore
    from ms2deepscore.models import load_model

    # 强制使用 MS2DeepScore
    if method.lower() not in {"ms2deepscore", "ms2deep score"}:
        print("[WARNING] library_match_full_workflow_impl 已强制使用 MS2DeepScore，忽略传入的 method 参数")

    model_path = model_path or os.getenv("MS2DEEPSCORE_MODEL_PATH")
    if not model_path or not Path(model_path).exists():
        raise FileNotFoundError(f"MS2DeepScore 模型文件不存在: {model_path}")

    print(f"[LIBRARY_MATCH] 开始完整 MS2DeepScore 库匹配流程...")
    print(f"   Model: {model_path}")
    print(f"   Reference: {reference_mgf_path}")

    # Step 1: raw → mzML
    if converter.lower() == "thermo":
        convert_raw_to_mzml_ThermoRawFileParser_impl(raw_input_dir, mzml_output_dir)
    else:
        convert_raw_to_mzml_msconvert_impl(raw_input_dir, mzml_output_dir)
    print(f"[LIBRARY_MATCH] raw → mzML 完成 → {mzml_output_dir}")

    # Step 2: mzML → MGF
    mgf_summary = mzml_directory_to_mgf_impl(mzml_output_dir, mgf_output_dir, ms_level=2)
    print(f"[LIBRARY_MATCH] mzML → MGF 完成\n{mgf_summary}")

    # Step 3: 确定 query MGF
    resolved_query_mgf = query_mgf_path
    if not resolved_query_mgf:
        mgf_candidates = sorted(Path(mgf_output_dir).glob("*.mgf"))
        if not mgf_candidates:
            raise FileNotFoundError(f"未在 {mgf_output_dir} 生成任何 .mgf 文件")
        resolved_query_mgf = str(mgf_candidates[0])
        print(f"[LIBRARY_MATCH] 自动选择 query_mgf: {resolved_query_mgf}")

    # Step 4: MS2DeepScore 匹配（核心库匹配逻辑 - 修复 ionmode + 使用正确 Spectrum 对象）
    # 必须为谱图设置 ionmode，否则 MS2DeepScore 会报 "Feature should be ['positive'] or ['negative'], not None"
    query_spectra = list(load_from_mgf(resolved_query_mgf))
    reference_spectra = list(load_from_mgf(reference_mgf_path))

    # 直接设置 ionmode 元数据（解决 "Feature should be ['positive'] or ['negative'], not None"）
    # matchms Spectrum 对象允许直接修改 metadata
    def prepare_spectrum(spectrum):
        if spectrum is None:
            return None
        spectrum = normalize_intensities(spectrum)
        # 确保至少有 5 个峰（避免空谱图）
        if len(spectrum.peaks.mz) < 5:
            return None
        # 强制设置 ionmode（MS2DeepScore 模型需要这个字段）
        if not spectrum.get("ionmode"):
            spectrum.set("ionmode", "positive")
        return spectrum

    query_spectra = [s for s in (prepare_spectrum(s) for s in query_spectra) if s is not None]
    reference_spectra = [s for s in (prepare_spectrum(s) for s in reference_spectra) if s is not None]

    # 使用兼容加载函数解决 'model_params' 错误
    try:
        model = _load_ms2deepscore_model_compat(model_path)
    except Exception as e:
        raise RuntimeError(f"加载 MS2DeepScore 模型失败: {e}. 请检查模型文件是否为有效 .pt 文件。") from e

    scorer = MS2DeepScore(model)

    results = []
    high_score_results = []  # 只保留 score > 0.5 的结果

    print(f"[LIBRARY_MATCH] 开始对 {len(query_spectra)} 条 query 谱图与 {len(reference_spectra)} 条参考谱图进行全量匹配... (这可能需要较长时间)")

    # 使用重定向避免 MCP JSON-RPC 解析错误（大量 print 会导致客户端解析失败）
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        for i, query_spec in enumerate(query_spectra):
            for j, ref_spec in enumerate(reference_spectra):
                try:
                    score = float(scorer.pair(query_spec, ref_spec))
                except Exception as pair_err:
                    score = 0.0  # 如果某对失败，跳过但不中断整个流程
                    print(f"  Warning: pair({i},{j}) failed: {pair_err}")

                entry = {
                    "query_index": i,
                    "query_title": str(query_spec.get("title", f"query_{i}")),
                    "reference_index": j,
                    "reference_title": str(ref_spec.get("title", f"ref_{j}")),
                    "score": round(score, 6)
                }
                results.append(entry)

                if score > 0.5:
                    high_score_results.append(entry)

    print(f"[LIBRARY_MATCH] 共计算 {len(results)} 对匹配，结果中得分 > 0.5 的有 {len(high_score_results)} 对")

    # 保存结果到独立文件
    output_path = Path(output_dir or "workspace/library_match_results")
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 1. 完整结果（所有 pair）
    json_file = output_path / "ms2deepscore_full_match.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 2. 高分结果总结（只保留 score > 0.5）
    high_score_file = output_path / "ms2deepscore_high_score_summary.txt"
    with open(high_score_file, "w", encoding="utf-8") as f:
        f.write("=== MS2DeepScore 库匹配结果 (仅保留 score > 0.5) ===\n\n")
        f.write(f"Query MGF: {resolved_query_mgf} ({len(query_spectra)} spectra)\n")
        f.write(f"Reference MGF: {reference_mgf_path} ({len(reference_spectra)} spectra)\n")
        f.write(f"Total pairs calculated: {len(results)}\n")
        f.write(f"High score matches (score > 0.5): {len(high_score_results)}\n\n")
        f.write("=== 高分匹配列表 (按分数降序) ===\n\n")

        if high_score_results:
            sorted_high = sorted(high_score_results, key=lambda x: x["score"], reverse=True)
            for item in sorted_high:
                f.write(f"score = {item['score']:.6f}\n")
                f.write(f"  Query : {item['query_title']}\n")
                f.write(f"  Ref   : {item['reference_title']}\n")
                f.write("-" * 60 + "\n")
        else:
            f.write("未找到任何 score > 0.5 的匹配。\n")

    summary = f"""
MS2DeepScore 完整库匹配完成！
- 处理 query 谱图数量: {len(query_spectra)}
- 参考谱图数量: {len(reference_spectra)}
- 总匹配对数: {len(results)}
- 得分 > 0.5 的匹配数量: {len(high_score_results)}

结果文件已保存：
  • {json_file} （所有匹配的完整 JSON）
  • {high_score_file} （仅保留 score>0.5 的可读总结）
"""
    print(summary)
    if high_score_results:
        print(f"找到 {len(high_score_results)} 个得分大于 0.5 的匹配，已保存到 {high_score_file}")
    else:
        print("警告：本次匹配中没有得分大于 0.5 的结果。请检查谱图质量或降低阈值。")
    return summary


def _validate_spectrum_arrays(mz: list[float], intensity: list[float], prefix: str) -> None:
    if not mz or not intensity:
        raise ValueError(f"{prefix}_mz 和 {prefix}_intensity 不能为空。")
    if len(mz) != len(intensity):
        raise ValueError(f"{prefix}_mz 和 {prefix}_intensity 长度必须一致。")
    if any(i < 0 for i in intensity):
        raise ValueError(f"{prefix}_intensity 不能包含负值。")


def _build_spectrum(
    mz: list[float],
    intensity: list[float],
    precursor_mz: float | None,
    ionmode: str = "positive",
):
    from matchms import Spectrum
    import numpy as np

    metadata = {}
    if precursor_mz is not None:
        metadata["precursor_mz"] = precursor_mz
    metadata["ionmode"] = ionmode
    mz_array = np.asarray(mz, dtype=np.float64)
    intensity_array = np.asarray(intensity, dtype=np.float64)
    return Spectrum(mz=mz_array, intensities=intensity_array, metadata=metadata)