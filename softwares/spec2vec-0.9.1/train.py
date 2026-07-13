import argparse
import random
import statistics
from pathlib import Path

import numpy as np
from gensim.models import Word2Vec
from gensim.models.callbacks import CallbackAny2Vec
from matchms import SpectrumProcessor
from matchms.filtering.default_pipelines import DEFAULT_FILTERS
from matchms.importing import load_from_mgf
from spec2vec import Spec2Vec, SpectrumDocument
from spec2vec.model_building import learning_rates_to_gensim_style, set_spec2vec_defaults


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train Spec2Vec model and evaluate on val/test MGF.")
    parser.add_argument(
        "--mgf",
        type=str,
        default="",
        help="Legacy single MGF path for training. Prefer --train-mgf.",
    )
    parser.add_argument(
        "--train-mgf",
        type=str,
        default="",
        help="Path to training MGF file.",
    )
    parser.add_argument(
        "--val-mgf",
        type=str,
        default="",
        help="Path to validation MGF file for automatic evaluation.",
    )
    parser.add_argument(
        "--test-mgf",
        type=str,
        default="",
        help="Path to test MGF file for automatic evaluation.",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="/home/chenyihang/massagent/agent_py_V2.0/softwares/spec2vec-0.9.1/models/spec2vec.model",
        help="Path to output Word2Vec model file.",
    )
    parser.add_argument(
        "--n-decimals",
        type=int,
        default=2,
        help="Decimals used in SpectrumDocument tokenization.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Number of workers for training.",
    )
    parser.add_argument(
        "--max-spectra",
        type=int,
        default=0,
        help="Optional cap on number of spectra to load (0 means all).",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=30,
        help="Total training epochs.",
    )
    parser.add_argument(
        "--save-every",
        type=int,
        default=10,
        help="Save checkpoint every N epochs.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility.",
    )
    parser.add_argument(
        "--debug-pairs",
        type=int,
        default=20,
        help="Number of random document pairs for score sanity check per epoch.",
    )
    parser.add_argument(
        "--eval-max-query",
        type=int,
        default=300,
        help="Max number of query spectra used in val/test evaluation (for speed).",
    )
    parser.add_argument(
        "--allowed-missing-percentage",
        type=float,
        default=50.0,
        help="Spec2Vec allowed_missing_percentage for evaluation.",
    )
    return parser.parse_args()


class DebugTrainingCallback(CallbackAny2Vec):
    """Verbose callback: print loss, embedding stats and score sanity checks."""

    def __init__(self, documents: list[SpectrumDocument], total_epochs: int, debug_pairs: int):
        self.epoch = 0
        self.total_epochs = total_epochs
        self.prev_loss = 0.0
        self.documents = documents
        self.debug_pairs = debug_pairs
        self.rng = random.Random(42)

    def on_epoch_end(self, model: Word2Vec):
        self.epoch += 1
        loss = model.get_latest_training_loss()
        delta_loss = loss - self.prev_loss
        self.prev_loss = loss

        vectors = model.wv.vectors
        vec_norms = np.linalg.norm(vectors, axis=1)

        print(f"\n[DEBUG] ===== Epoch {self.epoch}/{self.total_epochs} =====")
        print(f"[DEBUG] cumulative_loss={loss:.2f}, delta_loss={delta_loss:.2f}")
        print(
            "[DEBUG] embedding_norm: "
            f"mean={vec_norms.mean():.4f}, std={vec_norms.std():.4f}, "
            f"min={vec_norms.min():.4f}, max={vec_norms.max():.4f}"
        )

        # 输出几个高频 token 的近邻，便于快速观察学习是否稳定
        top_tokens = model.wv.index_to_key[:3]
        for token in top_tokens:
            neighbors = model.wv.most_similar(token, topn=5)
            neigh_str = ", ".join([f"{w}:{s:.3f}" for w, s in neighbors])
            print(f"[DEBUG] neighbors({token}) -> {neigh_str}")

        # 快速 sanity check：随机抽样文档对的 Spec2Vec 分数分布
        if len(self.documents) >= 2 and self.debug_pairs > 0:
            # 当前 spec2vec 版本内部会访问 model.wv，因此这里应传 Word2Vec 对象本身
            scorer = Spec2Vec(model=model, allowed_missing_percentage=50.0)
            sampled_scores = []
            n_pairs = min(self.debug_pairs, len(self.documents) // 2)
            for _ in range(n_pairs):
                d1, d2 = self.rng.sample(self.documents, 2)
                sampled_scores.append(float(scorer.pair(d1, d2)))
            print(
                "[DEBUG] random_pair_scores: "
                f"n={len(sampled_scores)}, "
                f"mean={statistics.mean(sampled_scores):.4f}, "
                f"median={statistics.median(sampled_scores):.4f}, "
                f"min={min(sampled_scores):.4f}, max={max(sampled_scores):.4f}"
            )


class PeriodicSaverCallback(CallbackAny2Vec):
    """Save model every N epochs and at last epoch."""

    def __init__(self, out_path: Path, total_epochs: int, save_every: int):
        self.epoch = 0
        self.out_path = out_path
        self.total_epochs = total_epochs
        self.save_every = max(1, save_every)

    def on_epoch_end(self, model: Word2Vec):
        self.epoch += 1
        should_save = (self.epoch % self.save_every == 0) or (self.epoch == self.total_epochs)
        if not should_save:
            return
        if self.epoch == self.total_epochs:
            save_path = self.out_path
        else:
            save_path = self.out_path.with_name(f"{self.out_path.stem}_iter_{self.epoch}{self.out_path.suffix}")
        print(f"[DEBUG] saving checkpoint -> {save_path}")
        model.save(str(save_path))


def load_and_clean_spectra(mgf_path: Path, max_spectra: int = 0):
    if not mgf_path.exists():
        raise FileNotFoundError(f"MGF file not found: {mgf_path}")

    spectra_iter = load_from_mgf(str(mgf_path))
    if max_spectra > 0:
        spectra = []
        for idx, spectrum in enumerate(spectra_iter):
            if idx >= max_spectra:
                break
            spectra.append(spectrum)
    else:
        spectra = list(spectra_iter)

    if not spectra:
        raise ValueError(f"No spectra loaded from {mgf_path}")

    processor = SpectrumProcessor(DEFAULT_FILTERS)
    spectra_cleaned, _ = processor.process_spectra(spectra)
    spectra_cleaned = [s for s in spectra_cleaned if s is not None]
    if not spectra_cleaned:
        raise ValueError(f"No spectra left after filtering for {mgf_path}")
    return spectra_cleaned


def get_label(spectrum):
    metadata = spectrum.metadata if spectrum.metadata is not None else {}
    for key in ("inchikey", "inchikey14", "smiles", "formula", "compound_name", "name", "title"):
        value = metadata.get(key)
        if value:
            return str(value)
    return None


def evaluate_retrieval(model: Word2Vec, reference_spectra: list, query_spectra: list, n_decimals: int,
                       allowed_missing_percentage: float, max_query: int, seed: int, split_name: str):
    if not reference_spectra or not query_spectra:
        print(f"[EVAL-{split_name}] skipped: empty spectra list.")
        return

    scorer = Spec2Vec(model=model, allowed_missing_percentage=allowed_missing_percentage)
    reference_docs = [SpectrumDocument(s, n_decimals=n_decimals) for s in reference_spectra]

    rng = random.Random(seed)
    if max_query > 0 and len(query_spectra) > max_query:
        query_spectra = rng.sample(query_spectra, max_query)

    total = 0
    valid = 0
    hit1 = 0
    hit5 = 0
    hit10 = 0
    mrr_sum = 0.0

    for q_spec in query_spectra:
        total += 1
        q_label = get_label(q_spec)
        if q_label is None:
            continue

        q_doc = SpectrumDocument(q_spec, n_decimals=n_decimals)
        scored = []
        for ref_spec, ref_doc in zip(reference_spectra, reference_docs):
            ref_label = get_label(ref_spec)
            if ref_label is None:
                continue
            score = float(scorer.pair(q_doc, ref_doc))
            scored.append((score, ref_label))

        if not scored:
            continue

        valid += 1
        scored.sort(key=lambda x: x[0], reverse=True)
        ranked_labels = [lbl for _, lbl in scored]

        try:
            rank = ranked_labels.index(q_label) + 1
            mrr_sum += 1.0 / rank
            if rank <= 1:
                hit1 += 1
            if rank <= 5:
                hit5 += 1
            if rank <= 10:
                hit10 += 1
        except ValueError:
            pass

    if valid == 0:
        print(f"[EVAL-{split_name}] skipped: no valid labeled queries (total={total}).")
        return

    print(f"[EVAL-{split_name}] queries_total={total}, queries_valid={valid}")
    print(f"[EVAL-{split_name}] top1={hit1/valid:.4f}, top5={hit5/valid:.4f}, top10={hit10/valid:.4f}, mrr={mrr_sum/valid:.4f}")


def main() -> None:
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)

    if args.train_mgf:
        train_mgf_path = Path(args.train_mgf)
    elif args.mgf:
        train_mgf_path = Path(args.mgf)
    else:
        train_mgf_path = Path("/home/chenyihang/massagent/agent_py_V2.0/database_file/spectraverse-1.0.1.mgf")

    val_mgf_path = Path(args.val_mgf) if args.val_mgf else None
    test_mgf_path = Path(args.test_mgf) if args.test_mgf else None

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    spectra_cleaned = load_and_clean_spectra(train_mgf_path, args.max_spectra)
    print(f"[INFO] train mgf: {train_mgf_path}")
    print(f"[INFO] loaded spectra count: {len(spectra_cleaned)}")

    print(f"[INFO] cleaned spectra count: {len(spectra_cleaned)}")
    peak_counts = [len(s.peaks.mz) for s in spectra_cleaned]
    print(
        "[INFO] peaks per spectrum: "
        f"mean={statistics.mean(peak_counts):.2f}, "
        f"median={statistics.median(peak_counts):.2f}, "
        f"min={min(peak_counts)}, max={max(peak_counts)}"
    )

    documents = [SpectrumDocument(s, n_decimals=args.n_decimals) for s in spectra_cleaned]
    doc_lens = [len(doc.words) for doc in documents]
    print(
        "[INFO] document length stats: "
        f"mean={statistics.mean(doc_lens):.2f}, "
        f"median={statistics.median(doc_lens):.2f}, "
        f"min={min(doc_lens)}, max={max(doc_lens)}"
    )
    print(f"[INFO] epochs={args.epochs}, save_every={args.save_every}, workers={args.workers}")

    # 使用 spec2vec 默认参数并转换为 gensim 风格
    settings = set_spec2vec_defaults(workers=args.workers)
    settings = learning_rates_to_gensim_style(args.epochs, **settings)

    callbacks = [
        DebugTrainingCallback(documents=documents, total_epochs=args.epochs, debug_pairs=args.debug_pairs),
        PeriodicSaverCallback(out_path=out_path, total_epochs=args.epochs, save_every=args.save_every),
    ]

    model = Word2Vec(
        documents,
        callbacks=callbacks,
        **settings,
    )

    print(f"[INFO] final vocabulary size: {len(model.wv.index_to_key)}")
    print(f"[INFO] vector size: {model.vector_size}")

    # 自动评估：以 train 作为 reference，在 val/test 上检索
    if val_mgf_path:
        val_spectra = load_and_clean_spectra(val_mgf_path, 0)
        evaluate_retrieval(
            model=model,
            reference_spectra=spectra_cleaned,
            query_spectra=val_spectra,
            n_decimals=args.n_decimals,
            allowed_missing_percentage=args.allowed_missing_percentage,
            max_query=args.eval_max_query,
            seed=args.seed,
            split_name="VAL",
        )

    if test_mgf_path:
        test_spectra = load_and_clean_spectra(test_mgf_path, 0)
        evaluate_retrieval(
            model=model,
            reference_spectra=spectra_cleaned,
            query_spectra=test_spectra,
            n_decimals=args.n_decimals,
            allowed_missing_percentage=args.allowed_missing_percentage,
            max_query=args.eval_max_query,
            seed=args.seed,
            split_name="TEST",
        )

    print(f"Training done. Model saved to: {out_path}")
    print(f"Usable .env line: SPEC2VEC_MODEL_PATH=\"{out_path}\"")


if __name__ == "__main__":
    main()