"""Cliente MCP stdio reutilizable (lo usan el cliente puro y el agente)."""
from __future__ import annotations

import json
import os
import sys
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .errores import MARCA_TRANSITORIO, ErrorHerramienta, FalloTransitorio


def _parametros() -> StdioServerParameters:
    # env completo: por defecto el cliente stdio solo pasa unas pocas variables
    # y el servidor necesita las de Azure SQL / Entra ID.
    return StdioServerParameters(
        command=sys.executable, args=["-m", "andes_agent.mcp_server"], env=dict(os.environ)
    )


def _extraer(resultado: Any) -> dict[str, Any]:
    texto = "".join(getattr(c, "text", "") for c in resultado.content)
    if resultado.isError:
        if MARCA_TRANSITORIO in texto:
            raise FalloTransitorio(texto)
        raise ErrorHerramienta(texto)
    estructurado = resultado.structuredContent
    if estructurado is not None:
        return estructurado["result"] if set(estructurado) == {"result"} else estructurado
    return json.loads(texto)


async def listar_herramientas() -> list[dict[str, str]]:
    async with stdio_client(_parametros()) as (lee, escribe):
        async with ClientSession(lee, escribe) as sesion:
            await sesion.initialize()
            r = await sesion.list_tools()
            return [{"nombre": t.name, "descripcion": t.description or ""} for t in r.tools]


async def llamar_herramientas(llamadas: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    """Abre una sola sesión stdio y ejecuta todas las llamadas."""
    crudos = []
    async with stdio_client(_parametros()) as (lee, escribe):
        async with ClientSession(lee, escribe) as sesion:
            await sesion.initialize()
            for nombre, args in llamadas:
                crudos.append(await sesion.call_tool(nombre, args))
    # Se interpretan fuera de los task groups de anyio para que los errores no lleguen envueltos.
    return [_extraer(r) for r in crudos]


async def leer_recurso(uri: str) -> str:
    async with stdio_client(_parametros()) as (lee, escribe):
        async with ClientSession(lee, escribe) as sesion:
            await sesion.initialize()
            r = await sesion.read_resource(uri)
            return "".join(getattr(c, "text", "") for c in r.contents)
