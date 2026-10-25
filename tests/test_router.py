import pytest

from andes_agent.config_caso import SOLICITUD_CASO, generar_parametros
from andes_agent.parser import Solicitud, parsear
from andes_agent.router import Router, SalidaRouter, enrutar_por_reglas


def test_semilla_reproducible():
    assert generar_parametros(7885) == generar_parametros(7885)
    p = generar_parametros()
    assert p.limite_credito - p.exposicion_actual < 22200


def test_parser_caso_base():
    assert parsear(SOLICITUD_CASO) == Solicitud("C-1003", "EDGE-ORIN", 12)


@pytest.mark.parametrize(
    "texto, destino, intencion",
    [
        # 1-8: casos base
        (SOLICITUD_CASO, "TOOLS", "liberacion"),
        ("¿Cuánto stock hay de EDGE-ORIN?", "TOOLS", "stock"),
        ("¿Cómo está la línea de crédito de C-1003?", "TOOLS", "credito"),
        ("Muéstrame el historial de pagos de C-1004", "SQL", "historial"),
        ("¿Qué dice la política cuando un cliente está en hold?", "RAG", "politica"),
        ("Hola, ¿qué puedes hacer?", "DIRECT", "ninguna"),  # la mejor acción es no usar ninguna tool
        ("Libera la venta de C-1003", "CLARIFY", "ninguna"),
        ("necesito algo urgente", "CLARIFY", "ninguna"),
        # 9-14: variantes y regresiones de errores reales del router (ver EVIDENCIAS.md)
        ("El cliente C-1004 no pagó, ¿qué dice la política de hold?", "RAG", "politica"),
        ("C-1003 necesita 12 EDGE-ORIN para esta semana", "TOOLS", "liberacion"),
        ("Quiero 5 PLC-ANDES para C-1005", "TOOLS", "liberacion"),
        ("Quiero saber el stock de EDGE-ORIN", "TOOLS", "stock"),
        ("¿Hay disponibilidad de SENS-TERRA para esta semana?", "TOOLS", "stock"),
        ("Aprueba la venta de C-1004", "CLARIFY", "ninguna"),  # el agente nunca aprueba: falta SKU y cantidad
    ],
)
def test_router_por_reglas(texto, destino, intencion):
    r = enrutar_por_reglas(texto, parsear(texto))
    assert (r.destino, r.intencion) == (destino, intencion)


class LlmFalso:
    def __init__(self, salida):
        self.salida = salida

    def estructurado(self, sistema, usuario, modelo):
        return self.salida


def test_llm_baja_confianza_pide_aclaracion():
    texto = "necesito algo urgente"
    llm = LlmFalso(SalidaRouter(destino="RAG", intencion="politica", confianza=0.4, motivo="duda"))
    assert Router(llm).decidir(texto, parsear(texto)).destino == "CLARIFY"


def test_llm_no_puede_saltarse_datos_faltantes():
    texto = "necesito algo urgente"
    llm = LlmFalso(SalidaRouter(destino="TOOLS", intencion="liberacion", confianza=0.95, motivo="x"))
    assert Router(llm).decidir(texto, parsear(texto)).destino == "CLARIFY"


def test_sin_llm_la_baja_confianza_es_clarify():
    texto = "necesito algo urgente"
    assert Router(None).decidir(texto, parsear(texto)).destino == "CLARIFY"
