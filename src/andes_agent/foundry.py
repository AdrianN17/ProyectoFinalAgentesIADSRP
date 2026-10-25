"""Cliente de Azure AI Foundry (modelos desplegados en el recurso): chat estructurado y embeddings."""
from __future__ import annotations

from functools import lru_cache
from typing import TypeVar

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI
from pydantic import BaseModel

from .errores import ErrorConfiguracion
from .settings import Settings, get_settings

T = TypeVar("T", bound=BaseModel)
ALCANCE_COGNITIVE = "https://cognitiveservices.azure.com/.default"


@lru_cache
def _cliente_openai(endpoint: str, api_key: str, api_version: str) -> AzureOpenAI:
    if not endpoint:
        raise ErrorConfiguracion("Falta AZURE_OPENAI_ENDPOINT (endpoint del recurso en Azure AI Foundry).")
    if api_key:
        return AzureOpenAI(azure_endpoint=endpoint, api_key=api_key, api_version=api_version)
    proveedor = get_bearer_token_provider(DefaultAzureCredential(), ALCANCE_COGNITIVE)
    return AzureOpenAI(azure_endpoint=endpoint, azure_ad_token_provider=proveedor, api_version=api_version)


class ClienteFoundry:
    def __init__(self, settings: Settings | None = None):
        self.s = settings or get_settings()
        self.client = _cliente_openai(self.s.openai_endpoint, self.s.openai_api_key, self.s.openai_api_version)

    def estructurado(self, sistema: str, usuario: str, modelo: type[T]) -> T:
        """Salida validada contra un esquema Pydantic (structured outputs). Lanza si no valida."""
        r = self.client.chat.completions.parse(
            model=self.s.chat_deployment,
            messages=[{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
            response_format=modelo,
        )
        parsed = r.choices[0].message.parsed
        if parsed is None:
            raise ValueError("El modelo no devolvió una salida estructurada válida.")
        return parsed

    def texto(self, sistema: str, usuario: str) -> str:
        r = self.client.chat.completions.create(
            model=self.s.chat_deployment,
            messages=[{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
        )
        return (r.choices[0].message.content or "").strip()

    def embeddings(self, textos: list[str]) -> list[list[float]]:
        r = self.client.embeddings.create(model=self.s.embedding_deployment, input=textos)
        return [d.embedding for d in sorted(r.data, key=lambda d: d.index)]
