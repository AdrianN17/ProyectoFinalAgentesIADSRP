"""MCP por stdio real (subproceso) sin LLM, y agente consumiendo el mismo servidor con una consulta compuesta."""
import asyncio
import os
import sys
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import RetryPolicy
from mcp import StdioServerParameters

from andes_agent import mcp_client
from andes_agent.errores import ErrorHerramienta, FalloTransitorio
from andes_agent.fuentes import McpFuentes
from andes_agent.graph import Dependencias, construir_grafo
from andes_agent.redactor import Redactor
from andes_agent.router import Router
from test_grafo import PoliticasFalsas, RegistradorFalso, cfg

SERVIDOR = Path(__file__).with_name("servidor_mcp_prueba.py")
SRC = Path(__file__).resolve().parents[1] / "src"


@pytest.fixture(autouse=True)
def servidor_de_prueba(monkeypatch):
    entorno = {**os.environ, "PYTHONPATH": str(SRC)}
    monkeypatch.setattr(
        mcp_client, "_parametros",
        lambda: StdioServerParameters(command=sys.executable, args=[str(SERVIDOR)], env=entorno),
    )


def test_list_tools_sin_llm_y_sin_sql_libre():
    tools = {t["nombre"] for t in asyncio.run(mcp_client.listar_herramientas())}
    assert {"consultar_stock", "consultar_estado_credito"} <= tools  # mínimo 2 tools
    assert not any("sql" in t for t in tools)  # prohibido exponer SQL genérico


def test_call_tool_sin_llm():
    stock, credito = asyncio.run(mcp_client.llamar_herramientas(
        [("consultar_stock", {"sku": "EDGE-ORIN"}), ("consultar_estado_credito", {"cliente_id": "C-1003"})]))
    assert stock["stock_disponible"] == 33
    assert credito["credito_disponible"] == 5908.0


def test_resource_politica_credito():
    texto = asyncio.run(mcp_client.leer_recurso("politica://credito"))
    assert "Cliente en hold" in texto


def test_entrada_invalida_se_rechaza_en_el_servidor():
    with pytest.raises(ErrorHerramienta):
        asyncio.run(mcp_client.llamar_herramientas([("consultar_stock", {"sku": "no es un sku"})]))


def test_agente_consume_el_mismo_servidor_con_consulta_compuesta():
    """Una liberación hace 4 llamadas MCP (stock, crédito, historial, parámetros) y pausa por línea insuficiente."""
    deps = Dependencias(McpFuentes(), PoliticasFalsas(), RegistradorFalso(), Router(None), Redactor(None))
    rapido = RetryPolicy(max_attempts=2, initial_interval=0.01, jitter=False, retry_on=FalloTransitorio)
    r = construir_grafo(deps, MemorySaver(), rapido).invoke(
        {"solicitud": "C-1003 solicita liberar la venta de 12 EDGE-ORIN", "id_hilo": "MCP-1"}, cfg("MCP-1"))
    interrupcion = r["__interrupt__"][0].value
    assert interrupcion["motivos"] == ["linea_insuficiente", "monto_requiere_revision"]
    assert interrupcion["monto"] == 22200.0
