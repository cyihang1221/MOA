import argparse
from pathlib import Path

from matchms import SpectrumProcessor
from matchms.filtering.default_pipelines import DEFAULT_FILTERS
from matchms.importing import load_from_mgf
from spec2vec import SpectrumDocument
from spec2vec.model_building import train_new_word2vec_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train Spec2Vec model from an MGF file.")
    parser.add_argument(
        "--mgf",
        type=str,
        default="/home/chenyihang/massagent/agent_py_V2.0/database_file/spectraverse-1.0.1.mgf",
        help="Path to input MGF file.",
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mgf_path = Path(args.mgf)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not mgf_path.exists():
        raise FileNotFoundError(f"MGF file not found: {mgf_path}")

    spectra_iter = load_from_mgf(str(mgf_path))
    if args.max_spectra > 0:
        spectra = []
        for idx, spectrum in enumerate(spectra_iter):
            if idx >= args.max_spectra:
                break
            spectra.append(spectrum)
    else:
        spectra = list(spectra_iter)

    if not spectra:
        raise ValueError("No spectra loaded from the MGF file.")

    processor = SpectrumProcessor(DEFAULT_FILTERS)
    spectra_cleaned, _ = processor.process_spectra(spectra)
    spectra_cleaned = [s for s in spectra_cleaned if s is not None]

    if not spectra_cleaned:
        raise ValueError("No spectra left after filtering.")

    documents = [SpectrumDocument(s, n_decimals=args.n_decimals) for s in spectra_cleaned]

    train_new_word2vec_model(
        documents,
        iterations=[10, 20, 30],
        filename=str(out_path),
        workers=args.workers,
        progress_logger=True,
    )

    print(f"Training done. Model saved to: {out_path}")
    print(f"Usable .env line: SPEC2VEC_MODEL_PATH=\"{out_path}\"")


if __name__ == "__main__":
    main()