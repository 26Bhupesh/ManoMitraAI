"""
Standalone script: load knowledge_seed.json into a persistent ChromaDB collection.

Usage (from backend/app or with PYTHONPATH):
  python ingest_data.py

Requires: chromadb, sentence-transformers (see requirements.txt).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
COLLECTION_NAME = "support_knowledge"


def load_seed_items(seed_path: Path) -> list[dict]:
    raw = seed_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("knowledge_seed.json must be a JSON array of objects")
    for i, item in enumerate(data):
        for key in ("topic", "language", "header", "content"):
            if key not in item:
                raise ValueError(f"Item {i} missing key {key!r}")
    return data


def ingest(
    seed_path: Path,
    chroma_path: Path,
    reset: bool,
) -> None:
    items = load_seed_items(seed_path)
    logger.info("Loaded %d knowledge items from %s", len(items), seed_path)

    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=MODEL_NAME)
    client = chromadb.PersistentClient(path=str(chroma_path))

    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
            logger.info("Removed existing collection %r", COLLECTION_NAME)
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"embedding_model": MODEL_NAME},
    )

    if not reset and collection.count() > 0:
        logger.warning(
            "Collection %r already has %d documents. Use --reset to replace.",
            COLLECTION_NAME,
            collection.count(),
        )

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    for i, item in enumerate(items):
        topic = str(item["topic"])
        language = str(item["language"])
        header = str(item["header"])
        content = str(item["content"])
        doc_id = f"{topic}_{language}_{i}"
        ids.append(doc_id)
        documents.append(f"{header}\n{content}")
        metadatas.append(
            {
                "topic": topic,
                "language": language,
                "header": header,
                "content": content,
            }
        )

    batch_size = 64
    for start in range(0, len(ids), batch_size):
        end = min(start + batch_size, len(ids))
        collection.upsert(
            ids=ids[start:end],
            documents=documents[start:end],
            metadatas=metadatas[start:end],
        )

    logger.info(
        "Ingested %d documents into %r at %s",
        collection.count(),
        COLLECTION_NAME,
        chroma_path,
    )


def main() -> int:
    default_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Ingest knowledge_seed.json into ChromaDB")
    parser.add_argument(
        "--seed",
        type=Path,
        default=default_dir / "knowledge" / "knowledge_seed.json",
        help="Path to knowledge_seed.json",
    )
    parser.add_argument(
        "--chroma-path",
        type=Path,
        default=default_dir / "chroma_support",
        help="Persistent ChromaDB directory",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing collection before ingesting",
    )
    args = parser.parse_args()

    if not args.seed.is_file():
        logger.error("Seed file not found: %s", args.seed)
        return 1

    args.chroma_path.mkdir(parents=True, exist_ok=True)

    try:
        ingest(args.seed, args.chroma_path, reset=args.reset)
    except Exception as e:
        logger.exception("Ingest failed: %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
