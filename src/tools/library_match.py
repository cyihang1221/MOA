import math


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


# ============================= Spectral entropy 相似度实现 =============================
def library_match_spectral_entropy_impl(
    query_vector: list[float],
    reference_vector: list[float]
) -> float:
    """
    计算两个谱图向量的 Spectral Entropy 相似度。
    采用常见的 1 - (2*H(m) - H(p) - H(q)) / ln(4) 形式，输出范围约为 [0, 1]。
    """
    if len(query_vector) == 0 or len(reference_vector) == 0:
        raise ValueError("query_vector 和 reference_vector 不能为空。")

    if len(query_vector) != len(reference_vector):
        raise ValueError("query_vector 和 reference_vector 长度必须一致。")

    if any(v < 0 for v in query_vector) or any(v < 0 for v in reference_vector):
        raise ValueError("Spectral entropy 输入向量不能包含负值。")

    query_sum = sum(query_vector)
    reference_sum = sum(reference_vector)
    if query_sum == 0 or reference_sum == 0:
        raise ValueError("向量总强度不能为 0。")

    query_prob = [v / query_sum for v in query_vector]
    reference_prob = [v / reference_sum for v in reference_vector]
    mixed_prob = [(p + q) / 2 for p, q in zip(query_prob, reference_prob)]

    def _entropy(prob_vector: list[float]) -> float:
        return -sum(p * math.log(p) for p in prob_vector if p > 0)

    h_query = _entropy(query_prob)
    h_reference = _entropy(reference_prob)
    h_mixed = _entropy(mixed_prob)

    # 2*H(m)-H(p)-H(q) 理论范围为 [0, ln(4)]，归一化后得到 [0, 1]
    divergence = 2 * h_mixed - h_query - h_reference
    similarity = 1.0 - (divergence / math.log(4))

    # 数值误差下做裁剪
    similarity = max(0.0, min(1.0, similarity))
    return float(similarity)


# ============================= Spec2Vec 相似度实现 =============================
def library_match_spec2vec_impl(
    query_embedding: list[float],
    reference_embedding: list[float]
) -> float:
    """
    计算 Spec2Vec 嵌入向量的相似度。
    实现上使用嵌入向量的 Cosine 相似度。
    """
    return library_match_cosine_impl(query_embedding, reference_embedding)


# ============================= MS2DeepScore 相似度实现 =============================
def library_match_ms2deepscore_impl(
    query_embedding: list[float],
    reference_embedding: list[float]
) -> float:
    """
    计算 MS2DeepScore 嵌入向量的相似度。
    实现上使用嵌入向量的 Cosine 相似度。
    """
    return library_match_cosine_impl(query_embedding, reference_embedding)


# ============================= BLINK 相似度实现 =============================
def library_match_blink_impl(
    query_mz: list[float],
    query_intensity: list[float],
    reference_mz: list[float],
    reference_intensity: list[float],
    mz_tolerance: float = 0.01
) -> float:
    """
    计算 BLINK 风格的快速谱图匹配分数。
    核心思想：在 m/z 容差内对峰进行快速匹配，并对匹配峰强度做归一化点积。
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

    q_norm = math.sqrt(sum(i * i for i in query_intensity))
    r_norm = math.sqrt(sum(i * i for i in reference_intensity))
    if q_norm == 0 or r_norm == 0:
        raise ValueError("峰强度向量范数不能为 0。")

    # 双指针匹配（输入通常按 m/z 升序；为稳妥这里先排序）
    q_pairs = sorted(zip(query_mz, query_intensity), key=lambda x: x[0])
    r_pairs = sorted(zip(reference_mz, reference_intensity), key=lambda x: x[0])

    i = 0
    j = 0
    dot_product = 0.0

    while i < len(q_pairs) and j < len(r_pairs):
        q_mz, q_int = q_pairs[i]
        r_mz, r_int = r_pairs[j]
        delta = q_mz - r_mz

        if abs(delta) <= mz_tolerance:
            dot_product += q_int * r_int
            i += 1
            j += 1
        elif delta < 0:
            i += 1
        else:
            j += 1

    blink_score = dot_product / (q_norm * r_norm)
    blink_score = max(0.0, min(1.0, blink_score))
    return float(blink_score)


# ============================= MS-BERT 相似度实现 =============================
def library_match_msbert_impl(
    query_embedding: list[float],
    reference_embedding: list[float]
) -> float:
    """
    计算 MS-BERT 嵌入向量的相似度。
    实现上使用嵌入向量的 Cosine 相似度。
    """
    return library_match_cosine_impl(query_embedding, reference_embedding)
