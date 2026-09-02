#!/usr/bin/env python3
"""重建 LlamaIndex 文献向量库（softwares_database_RAG）。

默认写到网页使用的工作区根目录（``resolve_literature_dirs``）。
``preload_retriever`` 只在 persist 目录不存在时建索引，所以必须先删旧库。

用法（需已配置 LLM_MODEL_TYPE=DashScope 或 openai，以及 LLM_API_KEY）：

    conda activate MOA
    python scripts/rebuild_literature_rag.py --force
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
B_ROOT = ROOT / "MassOmics-Agent-B"


def _normalize_embed_env() -> None:
    mt = (os.getenv("LLM_MODEL_TYPE") or "").strip()
    if mt.lower() == "dashscope" and mt != "DashScope":
        os.environ["LLM_MODEL_TYPE"] = "DashScope"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="", help="softwares_database 路径")
    parser.add_argument("--persist", default="", help="softwares_database_RAG 输出路径")
    parser.add_argument("--force", action="store_true", help="删除已有 persist 后重建")
    parser.add_argument(
        "--include-raw",
        action="store_true",
        help="索引 paper_methods_raw（体积大、对作图帮助有限）",
    )
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT))
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
    _normalize_embed_env()

    from web_frontend.backend.literature_paths import resolve_literature_dirs

    persist, source = resolve_literature_dirs(ROOT)
    if args.source:
        source = str(Path(args.source).resolve())
    if args.persist:
        persist = str(Path(args.persist).resolve())

    persist_path = Path(persist)
    source_path = Path(source)
    if not source_path.is_dir():
        print(f"文献目录不存在: {source_path}", file=sys.stderr)
        return 2
    if persist_path.exists() and not args.force:
        print(
            f"已存在索引 {persist_path}。重建必须加 --force（会删除该目录）。",
            file=sys.stderr,
        )
        return 2

    exclude = ["*/paper_fetch_cache/*", "*/.git/*"]
    if not args.include_raw:
        exclude.append("*/paper_methods_raw/*")

    rag_src = B_ROOT if (B_ROOT / "src" / "build_RAG_private.py").is_file() else ROOT
    sys.path.insert(0, str(rag_src))
    from src.build_RAG_private import preload_retriever  # type: ignore

    if persist_path.exists():
        print(f"删除旧索引 {persist_path}")
        shutil.rmtree(persist_path)

    print(f"SOURCE={source_path}")
    print(f"PERSIST={persist_path}")
    print(f"embed LLM_MODEL_TYPE={os.getenv('LLM_MODEL_TYPE')}")
    print(f"exclude={exclude}")
    print("开始建索引（需 embedding API，可能需数十分钟）…")
    kwargs = {
        "PERSIST_DIR": str(persist_path),
        "SOURCE_DIR": str(source_path),
        "similarity_top_k": args.top_k,
    }
    try:
        preload_retriever(exclude=exclude, **kwargs)
    except TypeError:
        preload_retriever(**kwargs)
    if not (persist_path / "docstore.json").is_file():
        print("建索引结束但没有 docstore.json", file=sys.stderr)
        return 1
    print(f"完成: {persist_path / 'docstore.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
