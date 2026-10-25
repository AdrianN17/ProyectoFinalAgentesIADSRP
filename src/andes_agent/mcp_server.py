"""Servidor MCP (stdio) de solo lectura. No expone SQL libre ni operaciones de escritura.

IMPORTANTE: en stdio no se debe escribir nada a stdout (rompe el protocolo); los logs van a stderr.
"""
from __future__ import annotations

import logging
import re
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from .db import Repositorio
from .errores import ErrorConfiguracion
from .parser import CLIENTE_RE, SKU_RE
from .settings import DIR_POLITICAS

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
mcp = FastMCP("andes-supply-credito")
_repo: Repositorio | None = None


def _r() -> Repositorio:
    global _repo
    _repo = _repo or Repositorio()
    return _repo


def _validar(patron: re.Pattern[str], valor: str, nombre: str) -> str:
    valor = valor.strip().upper()
    if not patron.fullmatch(valor):
        raise ValueError(f"{nombre} con formato inválido: {valor!r}")
    return valor


@mcp.tool()
def consultar_stock(sku: str) -> dict[str, Any]:
    """Stock disponible, precio y lead time de un SKU (p. ej. EDGE-ORIN)."""
    return _r().consultar_stock(_validar(SKU_RE, sku, "sku"))


@mcp.tool()
def consultar_estado_credito(cliente_id: str) -> dict[str, Any]:
    """Estado de crédito (activo/hold), límite, exposición y crédito disponible de un cliente (p. ej. C-1003)."""
    return _r().consultar_estado_credito(_validar(CLIENTE_RE, cliente_id, "cliente_id"))


@mcp.tool()
def consultar_historial_ventas(cliente_id: str, limite: int = 5) -> dict[str, Any]:
    """Últimas ventas del cliente y resumen de pagos (vencidos y monto vencido)."""
    return _r().consultar_historial_ventas(_validar(CLIENTE_RE, cliente_id, "cliente_id"), limite)


@mcp.tool()
def consultar_parametros_credito() -> dict[str, Any]:
    """Parámetros de crédito vigentes (monto de revisión de Finanzas)."""
    return _r().consultar_parametros_credito()


@mcp.resource("politica://credito", mime_type="text/markdown")
def politica_credito() -> str:
    """Política de crédito y líneas. Informa; no autoriza ventas."""
    ruta = DIR_POLITICAS / "politica_credito.md"
    if not ruta.exists():
        raise ErrorConfiguracion(f"No existe {ruta}")
    return ruta.read_text(encoding="utf-8")


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
