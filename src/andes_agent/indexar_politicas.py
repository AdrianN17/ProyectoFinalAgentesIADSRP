"""Indexa los documentos de política en Qdrant usando embeddings de Azure AI Foundry."""
from __future__ import annotations

from .rag import RepositorioPoliticas, crear_embedder, crear_qdrant
from .settings import get_settings


def main() -> None:
    s = get_settings()
    repo = RepositorioPoliticas(crear_qdrant(s), crear_embedder(s), s.qdrant_collection)
    n = repo.indexar()
    print(f"{n} fragmentos indexados en la colección '{s.qdrant_collection}' ({s.qdrant_url}).")


if __name__ == "__main__":
    main()
