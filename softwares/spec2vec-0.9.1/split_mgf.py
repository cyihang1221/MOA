import argparse
import random
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Split one MGF file into train/val/test.")
    parser.add_argument(
        "--input-mgf",
        type=str,
        default="/home/chenyihang/massagent/agent_py_V2.0/database_file/spectraverse-1.0.1.mgf",
        help="Path to source MGF file.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="/home/chenyihang/massagent/agent_py_V2.0/database_file/splits",
        help="Directory to save split MGF files.",
    )
    parser.add_argument("--train-ratio", type=float, default=0.8, help="Train split ratio.")
    parser.add_argument("--val-ratio", type=float, default=0.1, help="Validation split ratio.")
    parser.add_argument("--test-ratio", type=float, default=0.1, help="Test split ratio.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")
    return parser.parse_args()


def read_mgf_blocks(mgf_path: Path) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    in_block = False

    with mgf_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            stripped = line.strip()
            if stripped == "BEGIN IONS":
                in_block = True
                current = [line]
            elif stripped == "END IONS" and in_block:
                current.append(line)
                blocks.append("".join(current))
                current = []
                in_block = False
            elif in_block:
                current.append(line)

    return blocks


def write_blocks(path: Path, blocks: list[str]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for block in blocks:
            f.write(block)
            if not block.endswith("\n"):
                f.write("\n")


def main() -> None:
    args = parse_args()
    input_mgf = Path(args.input_mgf)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_mgf.exists():
        raise FileNotFoundError(f"Input MGF not found: {input_mgf}")

    ratio_sum = args.train_ratio + args.val_ratio + args.test_ratio
    if abs(ratio_sum - 1.0) > 1e-8:
        raise ValueError(f"train/val/test ratio must sum to 1.0, got {ratio_sum}")

    blocks = read_mgf_blocks(input_mgf)
    total = len(blocks)
    if total == 0:
        raise ValueError("No spectra blocks found in input MGF.")

    random.seed(args.seed)
    random.shuffle(blocks)

    n_train = int(total * args.train_ratio)
    n_val = int(total * args.val_ratio)
    n_test = total - n_train - n_val

    train_blocks = blocks[:n_train]
    val_blocks = blocks[n_train:n_train + n_val]
    test_blocks = blocks[n_train + n_val:]

    train_path = output_dir / "train.mgf"
    val_path = output_dir / "val.mgf"
    test_path = output_dir / "test.mgf"

    write_blocks(train_path, train_blocks)
    write_blocks(val_path, val_blocks)
    write_blocks(test_path, test_blocks)

    print(f"[INFO] input: {input_mgf}")
    print(f"[INFO] total spectra: {total}")
    print(f"[INFO] train: {len(train_blocks)} -> {train_path}")
    print(f"[INFO] val:   {len(val_blocks)} -> {val_path}")
    print(f"[INFO] test:  {len(test_blocks)} -> {test_path}")
    print(f"[INFO] seed: {args.seed}")


if __name__ == "__main__":
    main()
