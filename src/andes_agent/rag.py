"""RAG sobre Qdrant: fragmentación por sección, embeddings (Foundry) y búsqueda con cita de fuente."""
from __future__ import annotations

import hashlib
import math
import re
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from qdrant_client import QdrantClient, models

from .foundry import ClienteFoundry
from .settings import DIR_POLITICAS, Settings, get_settings


class Embedder(Protocol):
    dim: int

    def embed(self, textos: list[str]) -> list[list[float]]: ...


class FoundryEmbedder:
    def __init__(self, foundry: ClienteFoundry, dim: int):
        self.foundry, self.dim = foundry, dim

    def embed(self, textos: list[str]) -> list[list[float]]:
        return self.foundry.embeddings(textos)


class HashEmbedder:
    """Bolsa de palabras con hashing: determinista y sin red. Solo para desarrollo y pruebas."""

    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, textos: list[str]) -> list[list[float]]:
        return [self._uno(t) for t in textos]

    def _uno(self, texto: str) -> list[float]:
        plano = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
        v = [0.0] * self.dim
        for tok in re.findall(r"\w+", plano):
            v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.dim] += 1.0
        norma = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norma for x in v]


@dataclass(frozen=True)
class Fragmento:
    fuente: str
    seccion: str
    texto: str


def fragmentar(ruta: Path) -> list[Fragmento]:
    """Un fragmento por encabezado '## '."""
    fragmentos = []
    for bloque in re.split(r"^## ", ruta.read_text(encoding="utf-8"), flags=re.M)[1:]:
        titulo, _, cuerpo = bloque.partition("\n")
        fragmentos.append(Fragmento(ruta.name, titulo.strip(), cuerpo.strip()))
    return fragmentos


def crear_qdrant(s: Settings | None = None) -> QdrantClient:
    s = s or get_settings()
    return QdrantClient(url=s.qdrant_url, api_key=s.qdrant_api_key or None)


def crear_embedder(s: Settings | None = None) -> Embedder:
    s = s or get_settings()
    if s.embeddings_provider == "hash":
        return HashEmbedder()
    return FoundryEmbedder(ClienteFoundry(s), s.embedding_dim)


class RepositorioPoliticas:
    def __init__(self, qdrant: QdrantClient, embedder: Embedder, coleccion: str):
        self.qdrant, self.embedder, self.coleccion = qdrant, embedder, coleccion

    def indexar(self, directorio: Path = DIR_POLITICAS) -> int:
        fragmentos = [f for ruta in sorted(directorio.glob("*.md")) for f in fragmentar(ruta)]
        if self.qdrant.collection_exists(self.coleccion):
            self.qdrant.delete_collection(self.coleccion)
        self.qdrant.create_collection(
            self.coleccion,
            vectors_config=models.VectorParams(size=self.embedder.dim, distance=models.Distance.COSINE),
        )
        vectores = self.embedder.embed([f"{f.seccion}\n{f.texto}" for f in fragmentos])
        self.qdrant.upsert(
            self.coleccion,
            points=[
                models.PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{f.fuente}#{f.seccion}")),
                    vector=v,
                    payload={"fuente": f.fuente, "seccion": f.seccion, "texto": f.texto},
                )
                for f, v in zip(fragmentos, vectores)
            ],
        )
        return len(fragmentos)

    def buscar(self, consulta: str, k: int = 3, umbral: float = 0.0) -> list[dict[str, Any]]:
        vector = self.embedder.embed([consulta])[0]
        puntos = self.qdrant.query_points(
            self.coleccion, query=vector, limit=k, with_payload=True, score_threshold=umbral or None
        ).points
        return [
            {
                "fuente": p.payload["fuente"],
                "seccion": p.payload["seccion"],
                "texto": p.payload["texto"],
                "score": round(p.score, 3),
            }
            for p in puntos
        ]
