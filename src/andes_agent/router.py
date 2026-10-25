"""Router híbrido: reglas primero; si la confianza es baja, Foundry (salida estructurada); si no, CLARIFY."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from .parser import Solicitud

Destino = Literal["RAG", "SQL", "TOOLS", "CLARIFY", "DIRECT"]
Intencion = Literal["liberacion", "stock", "credito", "historial", "politica", "ninguna"]
UMBRAL_CONFIANZA = 0.6

SISTEMA_ROUTER = (
    "Clasificas solicitudes de ventas a crédito de AndesSupply. Devuelve destino e intención.\n"
    "- TOOLS: liberar venta (liberacion), stock de un SKU (stock), estado de crédito de un cliente (credito).\n"
    "- SQL: historial de ventas/pagos de un cliente (historial).\n"
    "- RAG: preguntas sobre políticas o reglas (politica).\n"
    "- DIRECT: saludos o preguntas sobre qué puedes hacer (ninguna).\n"
    "- CLARIFY: si falta información o es ambiguo (ninguna).\n"
    "confianza en [0,1]. No inventes datos."
)


class SalidaRouter(BaseModel):
    destino: Destino
    intencion: Intencion
    confianza: float = Field(ge=0, le=1)
    motivo: str


@dataclass(frozen=True)
class Ruta:
    destino: Destino
    intencion: Intencion
    confianza: float
    motivo: str
    origen: str  # "reglas" | "llm"


class LlmEstructurado(Protocol):
    def estructurado(self, sistema: str, usuario: str, modelo: type[SalidaRouter]) -> SalidaRouter: ...


def _norm(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()


def _tiene(texto: str, palabras: list[str]) -> bool:
    return any(re.search(r"\b" + p, texto) for p in palabras)


def enrutar_por_reglas(texto: str, sol: Solicitud) -> Ruta:
    t = _norm(texto)
    if _tiene(t, ["hola", "buenas", "gracias", "que puedes", "ayuda"]) and not (sol.cliente_id or sol.sku):
        return Ruta("DIRECT", "ninguna", 0.9, "saludo o consulta general", "reglas")

    verbos = _tiene(t, ["liber", "solicita", "pide", "pidio", "despach", "vender", "venta de"])
    # "necesita/quiere" solo cuentan como pedido de venta si hay SKU y cantidad ("quiero saber el stock" no lo es)
    pedido_implicito = _tiene(t, ["necesit", "quier", "requier"]) and bool(sol.sku and sol.cantidad)
    if (verbos and (sol.cliente_id or sol.sku)) or pedido_implicito:
        if sol.cliente_id and sol.sku and sol.cantidad:
            return Ruta("TOOLS", "liberacion", 0.9, "liberación con cliente, SKU y cantidad", "reglas")
        return Ruta("CLARIFY", "ninguna", 0.9, "liberación sin cliente, SKU o cantidad completos", "reglas")
    # Una pregunta explícita sobre la política gana aunque mencione a un cliente ("¿qué dice la política de hold?")
    if _tiene(t, ["politica", "normativa", "procedimiento", "reglamento"]):
        return Ruta("RAG", "politica", 0.8, "pregunta explícita de política", "reglas")
    if sol.cliente_id and _tiene(t, ["historial", "pagos", "facturas", "compras", "vencid"]):
        return Ruta("SQL", "historial", 0.85, "historial de ventas/pagos del cliente", "reglas")
    if sol.sku and _tiene(t, ["stock", "disponib", "inventario", "unidades", "existencias"]):
        return Ruta("TOOLS", "stock", 0.85, "consulta de stock de un SKU", "reglas")
    if sol.cliente_id and _tiene(t, ["linea", "credito", "hold", "exposicion", "limite", "deuda", "estado"]):
        return Ruta("TOOLS", "credito", 0.85, "estado de crédito del cliente", "reglas")
    if not (sol.cliente_id or sol.sku) and _tiene(
        t, ["politica", "norma", "procedimiento", "escalam", "requisitos", "condiciones", "plazo", "como se", "cuando se"]
    ):
        return Ruta("RAG", "politica", 0.8, "pregunta de política", "reglas")
    return Ruta("CLARIFY", "ninguna", 0.3, "sin señales claras", "reglas")


def _datos_completos(r: Ruta, sol: Solicitud) -> bool:
    """Validación determinista de lo que sugiere el modelo: nunca se confía a ciegas."""
    requisitos = {
        "liberacion": bool(sol.cliente_id and sol.sku and sol.cantidad),
        "stock": bool(sol.sku),
        "credito": bool(sol.cliente_id),
        "historial": bool(sol.cliente_id),
        "politica": True,
        "ninguna": True,
    }
    return requisitos[r.intencion]


class Router:
    def __init__(self, llm: LlmEstructurado | None = None, umbral: float = UMBRAL_CONFIANZA):
        self.llm, self.umbral = llm, umbral

    def decidir(self, texto: str, sol: Solicitud) -> Ruta:
        ruta = enrutar_por_reglas(texto, sol)
        if ruta.confianza >= self.umbral:
            return ruta
        if self.llm is None:
            return Ruta("CLARIFY", "ninguna", ruta.confianza, "baja confianza y sin LLM", "reglas")
        try:
            s = self.llm.estructurado(SISTEMA_ROUTER, texto, SalidaRouter)
        except Exception as e:  # noqa: BLE001 - el LLM es opcional; ante fallo se pide aclaración
            return Ruta("CLARIFY", "ninguna", 0.0, f"LLM no disponible: {type(e).__name__}", "reglas")
        ruta_llm = Ruta(s.destino, s.intencion, s.confianza, s.motivo, "llm")
        if s.confianza < self.umbral or not _datos_completos(ruta_llm, sol):
            return Ruta("CLARIFY", "ninguna", s.confianza, "baja confianza o datos incompletos", "llm")
        return ruta_llm
