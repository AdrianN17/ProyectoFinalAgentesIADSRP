"""Extracción determinista de cliente, SKU y cantidad desde el texto."""
from __future__ import annotations

import re
from dataclasses import dataclass

CLIENTE_RE = re.compile(r"\bC-\d{4}\b")
SKU_RE = re.compile(r"\b[A-Z]{2,6}-[A-Z0-9]{2,8}\b")


@dataclass(frozen=True)
class Solicitud:
    cliente_id: str | None = None
    sku: str | None = None
    cantidad: int | None = None


def parsear(texto: str) -> Solicitud:
    cliente = CLIENTE_RE.search(texto.upper())
    sku = SKU_RE.search(texto)  # los SKU se escriben en mayúsculas (EDGE-ORIN)
    cantidad = None
    if sku:
        m = re.search(
            r"(\d{1,6})\s+(?:(?:unidades|uds\.?|piezas)\s+de\s+)?" + re.escape(sku.group()), texto
        )
        cantidad = int(m.group(1)) if m else None
    return Solicitud(
        cliente_id=cliente.group() if cliente else None,
        sku=sku.group() if sku else None,
        cantidad=cantidad,
    )
