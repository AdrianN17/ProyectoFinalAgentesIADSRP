"""Configuración desde variables de entorno (.env). Sin secretos en el código."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

RAIZ = Path(__file__).resolve().parents[2]
DIR_POLITICAS = RAIZ / "data" / "politicas"


def _bool(nombre: str, defecto: bool) -> bool:
    return os.getenv(nombre, str(defecto)).strip().lower() in {"1", "true", "yes", "si", "sí"}


@dataclass(frozen=True)
class Settings:
    openai_endpoint: str
    openai_api_key: str
    openai_api_version: str
    chat_deployment: str
    embedding_deployment: str
    embedding_dim: int
    use_llm: bool
    embeddings_provider: str

    sql_server: str
    sql_database: str
    sql_auth: str
    sql_user: str
    sql_password: str
    sql_driver: str

    qdrant_url: str
    qdrant_api_key: str
    qdrant_collection: str

    simular_fallos: int


@lru_cache
def get_settings() -> Settings:
    e = os.getenv
    return Settings(
        openai_endpoint=e("AZURE_OPENAI_ENDPOINT", ""),
        openai_api_key=e("AZURE_OPENAI_API_KEY", ""),
        openai_api_version=e("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        chat_deployment=e("FOUNDRY_CHAT_DEPLOYMENT", "gpt-4o-mini"),
        embedding_deployment=e("FOUNDRY_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"),
        embedding_dim=int(e("EMBEDDING_DIM", "1536")),
        use_llm=_bool("USE_LLM", True),
        embeddings_provider=e("EMBEDDINGS_PROVIDER", "foundry").lower(),
        sql_server=e("AZURE_SQL_SERVER", ""),
        sql_database=e("AZURE_SQL_DATABASE", ""),
        sql_auth=e("AZURE_SQL_AUTH", "entra").lower(),
        sql_user=e("AZURE_SQL_USER", ""),
        sql_password=e("AZURE_SQL_PASSWORD", ""),
        sql_driver=e("AZURE_SQL_DRIVER", "ODBC Driver 18 for SQL Server"),
        qdrant_url=e("QDRANT_URL", "http://localhost:6333"),
        qdrant_api_key=e("QDRANT_API_KEY", ""),
        qdrant_collection=e("QDRANT_COLLECTION", "politicas_andes"),
        simular_fallos=int(e("SIMULAR_FALLOS_FUENTES", "0")),
    )
