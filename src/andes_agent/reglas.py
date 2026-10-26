"""Reglas de crédito deterministas. El LLM nunca decide aquí."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

Resultado = Literal["ok", "excepcion", "no_liberable", "datos_invalidos"]


@dataclass(frozen=True)
class Decision:
    resultado: Resultado
    motivos: list[str] = field(default_factory=list)
    monto: float = 0.0
    exposicion: float = 0.0
    limite: float = 0.0


def _d(valor: Any) -> Decimal:
    return Decimal(str(valor))


def evaluar_liberacion(
    *,
    cliente: dict[str, Any] | None,
    producto: dict[str, Any] | None,
    cantidad: int | None,
    monto_revision: float,
) -> Decision:
    """cliente: fila de v_estado_credito; producto: fila de v_stock (o None si no existen)."""
    invalidos = []
    if cliente is None:
        invalidos.append("cliente_inexistente")
    if producto is None:
        invalidos.append("sku_inexistente")
    if cantidad is None or cantidad <= 0:
        invalidos.append("cantidad_invalida")
    if invalidos:
        return Decision("datos_invalidos", invalidos)

    monto = _d(producto["precio_unitario"]) * cantidad
    exposicion = _d(cliente["exposicion_actual"])
    limite = _d(cliente["limite_credito"])
    base = {"monto": float(monto), "exposicion": float(exposicion), "limite": float(limite)}

    motivos: list[str] = []
    if cliente["estado_credito"] == "hold":
        motivos.append("cliente_en_hold")
    if exposicion + monto > limite:
        motivos.append("linea_insuficiente")
    #Modificacion de Regla de negocio
    if monto >= _d(monto_revision):
        motivos.append("monto_requiere_revision")

    if producto["stock_disponible"] < cantidad:
        # Finanzas no resuelve falta de stock: no se escala, se informa.
        return Decision("no_liberable", ["stock_insuficiente", *motivos], **base)
    return Decision("excepcion" if motivos else "ok", motivos, **base)
