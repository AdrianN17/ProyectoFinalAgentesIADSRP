"""Fuentes de evidencia: vía MCP (por defecto) o acceso directo a Azure SQL."""
from __future__ import annotations

import asyncio
from typing import Any, Protocol

from .db import Repositorio
from .errores import ErrorHerramienta, FalloTransitorio
from .mcp_client import llamar_herramientas

Llamada = tuple[str, dict[str, Any]]


class Fuentes(Protocol):
    def llamar(self, llamadas: list[Llamada]) -> list[dict[str, Any]]: ...


class DbFuentes:
    via = "ACCESO DIRECTO a Azure SQL (sin MCP, sin subproceso)"

    def __init__(self, repo: Repositorio):
        self.repo = repo

    def llamar(self, llamadas: list[Llamada]) -> list[dict[str, Any]]:
        return [self.repo.ejecutar(n, a) for n, a in llamadas]


class McpFuentes:
    via = "servidor MCP (subproceso por stdio, solo lectura)"

    def llamar(self, llamadas: list[Llamada]) -> list[dict[str, Any]]:
        try:
            return asyncio.run(llamar_herramientas(llamadas))
        except (FalloTransitorio, ErrorHerramienta):
            raise
        except Exception as e:  # noqa: BLE001 - fallos de transporte/proceso MCP: se tratan como transitorios
            raise FalloTransitorio(f"{type(e).__name__}: {e}") from e


class FuentesConFallos:
    """Inyecta N fallos transitorios iniciales para demostrar RetryPolicy."""

    def __init__(self, interno: Fuentes, fallos: int):
        self.interno, self.pendientes = interno, fallos

    @property
    def via(self) -> str:
        return getattr(self.interno, "via", "desconocido")

    def llamar(self, llamadas: list[Llamada]) -> list[dict[str, Any]]:
        if self.pendientes > 0:
            self.pendientes -= 1
            print(f"  [fallo transitorio simulado] la dependencia no respondió; fallos restantes: {self.pendientes}")
            raise FalloTransitorio("fallo simulado de la dependencia de stock")
        print("  [dependencia recuperada] consulta de fuentes OK tras reintento")
        return self.interno.llamar(llamadas)
