"""特征过滤与 KNN 填补：纯 numpy 实现，避免 sklearn/numpy 版本冲突。"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd


def _knn_impute_sample_matrix(matrix: np.ndarray, n_neighbors: int = 5) -> np.ndarray:
    data = matrix.astype(float).copy()
    n_rows, _ = data.shape
    k = max(1, int(n_neighbors))

    for row_idx in range(n_rows):
        row = data[row_idx]
        missing_cols = np.where(np.isnan(row))[0]
        if missing_cols.size == 0:
            continue

        neighbor_dists: list[tuple[float, int]] = []
        for other_idx in range(n_rows):
            if other_idx == row_idx:
                continue
            other = data[other_idx]
            both = ~np.isnan(row) & ~np.isnan(other)
            if not both.any():
                continue
            dist = float(np.linalg.norm(row[both] - other[both]))
            neighbor_dists.append((dist, other_idx))

        neighbor_dists.sort(key=lambda item: item[0])
        for col_idx in missing_cols:
            values: list[float] = []
            for _, other_idx in neighbor_dists:
                val = data[other_idx, col_idx]
                if not np.isnan(val):
                    values.append(float(val))
                if len(values) >= k:
                    break
            if values:
                row[col_idx] = float(np.mean(values[:k]))
            else:
                col_vals = data[:, col_idx]
                col_vals = col_vals[~np.isnan(col_vals)]
                if col_vals.size:
                    row[col_idx] = float(np.mean(col_vals))
        data[row_idx] = row

    return data


def run_feature_filtering_knn(
    input_dir: str,
    output_dir: str,
    *,
    min_presence: float = 0.5,
    min_intensity: float = 0.0,
    n_neighbors: int = 5,
) -> Path:
    input_path = Path(input_dir).resolve()
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    table_path = input_path / "feature_table.csv"
    if not table_path.is_file():
        raise FileNotFoundError(f"未找到 feature_table.csv: {table_path}")

    df = pd.read_csv(table_path)
    required_cols = ["feature_id", "mz", "rt_med"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    sample_cols = [c for c in df.columns if c not in required_cols]
    if not sample_cols:
        raise ValueError("No sample columns found.")

    df[sample_cols] = df[sample_cols].apply(pd.to_numeric, errors="coerce")
    n_before = df.shape[0]

    presence_ratio = df[sample_cols].notna().sum(axis=1) / len(sample_cols)
    df = df[presence_ratio >= min_presence].copy()
    n_after_presence = df.shape[0]

    mean_intensity = df[sample_cols].mean(axis=1, skipna=True)
    df = df[mean_intensity >= min_intensity].copy()
    n_after_intensity = df.shape[0]

    imputed = _knn_impute_sample_matrix(
        df[sample_cols].to_numpy(),
        n_neighbors=n_neighbors,
    )
    df[sample_cols] = imputed

    out_csv = output_path / "feature_table_filtered_imputed.csv"
    df.to_csv(out_csv, index=False)

    summary_txt = output_path / "feature_filtering_and_missing_value_imputation_summary.txt"
    summary_lines = [
        "Feature Filtering Summary",
        "=========================",
        f"Input features: {n_before}",
        f"After presence filtering: {n_after_presence}",
        f"After intensity filtering: {n_after_intensity}",
        f"min_presence: {min_presence}",
        f"min_intensity: {min_intensity}",
        f"KNN neighbors: {n_neighbors}",
        f"Final output: {out_csv}",
        "Imputation: numpy KNN (no sklearn)",
    ]
    summary_txt.write_text("\n".join(summary_lines), encoding="utf-8")
    return out_csv
