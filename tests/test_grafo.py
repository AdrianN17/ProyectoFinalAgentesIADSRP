import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, RetryPolicy

from andes_agent.config_caso import SOLICITUD_CASO
from andes_agent.errores import FalloTransitorio
from andes_agent.fuentes import FuentesConFallos
from andes_agent.graph import Dependencias, construir_grafo
from andes_agent.redactor import Redactor
from andes_agent.router import Router

CLIENTES = {
    "C-1003": {"encontrado": True, "cliente_id": "C-1003", "nombre": "Industrias Pacífico", "estado_credito": "activo",
               "limite_credito": 40000.0, "exposicion_actual": 30000.0, "credito_disponible": 10000.0,
               "fuente": "azure_sql:ops.v_estado_credito"},
    "C-1001": {"encontrado": True, "cliente_id": "C-1001", "nombre": "Minera", "estado_credito": "activo",
               "limite_credito": 250000.0, "exposicion_actual": 40000.0, "credito_disponible": 210000.0,
               "fuente": "azure_sql:ops.v_estado_credito"},
}
STOCK = {"encontrado": True, "sku": "EDGE-ORIN", "nombre": "Gateway", "precio_unitario": 1850.0,
         "lead_time_dias": 5, "stock_disponible": 35, "fuente": "azure_sql:ops.v_stock"}


class FuentesFalsas:
    def __init__(self):
        self.llamadas = 0

    def llamar(self, llamadas):
        self.llamadas += 1
        out = []
        for nombre, args in llamadas:
            if nombre == "consultar_stock":
                out.append(STOCK if args["sku"] == "EDGE-ORIN" else {"encontrado": False, "sku": args["sku"]})
            elif nombre == "consultar_estado_credito":
                out.append(CLIENTES.get(args["cliente_id"], {"encontrado": False, "cliente_id": args["cliente_id"]}))
            elif nombre == "consultar_historial_ventas":
                out.append({"encontrado": True, "cliente_id": args["cliente_id"], "ultimas_ventas": [],
                            "resumen_pagos": {"pagos_vencidos": 0, "monto_vencido": 0}, "fuente": "azure_sql:ventas"})
            else:
                out.append({"monto_revision": 25000.0, "fuente": "azure_sql:ops.parametros_caso"})
        return out


class PoliticasFalsas:
    def __init__(self):
        self.consultas = 0

    def buscar(self, consulta, k=3, umbral=0.0):
        self.consultas += 1
        return [{"fuente": "politica_credito.md", "seccion": "Línea insuficiente", "texto": "Escala a Finanzas.", "score": 0.9}]


class RegistradorFalso:
    def __init__(self):
        self.filas = {}

    def registrar_liberacion(self, id_hilo, cliente_id, sku, cantidad, monto, aprobado_por, motivos):
        creada = id_hilo not in self.filas
        self.filas.setdefault(id_hilo, {"id": len(self.filas) + 1, "aprobado_por": aprobado_por})
        return {"creada": creada, "liberacion_id": self.filas[id_hilo]["id"]}


@pytest.fixture
def entorno():
    fuentes, registrador = FuentesFalsas(), RegistradorFalso()
    deps = Dependencias(fuentes, PoliticasFalsas(), registrador, Router(None), Redactor(None))
    rapido = RetryPolicy(max_attempts=3, initial_interval=0.01, jitter=False, retry_on=FalloTransitorio)
    return deps, fuentes, registrador, rapido


def cfg(hilo):
    return {"configurable": {"thread_id": hilo}}


def test_ruta_directa_sin_excepcion(entorno):
    deps, _, reg, rapido = entorno
    g = construir_grafo(deps, MemorySaver(), rapido)
    r = g.invoke({"solicitud": "C-1001 pide 2 EDGE-ORIN a crédito", "id_hilo": "D1"}, cfg("D1"))
    assert "__interrupt__" not in r
    assert "liberada automáticamente" in r["respuesta"]
    assert reg.filas["D1"]["aprobado_por"] == "REGLAS_AUTOMATICAS"


def test_excepcion_pausa_y_no_registra(entorno):
    deps, _, reg, rapido = entorno
    g = construir_grafo(deps, MemorySaver(), rapido)
    r = g.invoke({"solicitud": SOLICITUD_CASO, "id_hilo": "H1"}, cfg("H1"))
    assert r["__interrupt__"][0].value["motivos"] == ["linea_insuficiente"]
    assert reg.filas == {}


def test_reanudar_aprobado_registra_una_sola_vez(entorno):
    deps, _, reg, rapido = entorno
    g = construir_grafo(deps, MemorySaver(), rapido)
    g.invoke({"solicitud": SOLICITUD_CASO, "id_hilo": "H1"}, cfg("H1"))
    r = g.invoke(Command(resume={"aprobado": True, "aprobador": "Ana (Finanzas)"}), cfg("H1"))
    assert "liberada tras aprobación de Ana (Finanzas)" in r["respuesta"]
    assert list(reg.filas) == ["H1"]


def test_reanudar_rechazado_no_registra(entorno):
    deps, _, reg, rapido = entorno
    g = construir_grafo(deps, MemorySaver(), rapido)
    g.invoke({"solicitud": SOLICITUD_CASO, "id_hilo": "H2"}, cfg("H2"))
    r = g.invoke(Command(resume={"aprobado": False, "aprobador": "Ana"}), cfg("H2"))
    assert "RECHAZADA" in r["respuesta"] and reg.filas == {}


def test_otro_id_hilo_no_ve_el_estado_pausado(entorno):
    deps, _, _, rapido = entorno
    g = construir_grafo(deps, MemorySaver(), rapido)
    g.invoke({"solicitud": SOLICITUD_CASO, "id_hilo": "H1"}, cfg("H1"))
    assert g.get_state(cfg("H1")).next == ("aprobacion_humana",)
    assert g.get_state(cfg("OTRO")).next == ()


def test_retry_en_fallo_transitorio(entorno):
    deps, fuentes, _, rapido = entorno
    deps.fuentes = FuentesConFallos(fuentes, fallos=2)
    g = construir_grafo(deps, MemorySaver(), rapido)
    r = g.invoke({"solicitud": SOLICITUD_CASO, "id_hilo": "R1"}, cfg("R1"))
    assert "__interrupt__" in r and fuentes.llamadas == 1


def test_regla_de_negocio_no_se_reintenta(entorno):
    deps, fuentes, _, rapido = entorno
    g = construir_grafo(deps, MemorySaver(), rapido)
    g.invoke({"solicitud": SOLICITUD_CASO, "id_hilo": "N1"}, cfg("N1"))
    assert fuentes.llamadas == 1


def test_cliente_inexistente_responde_sin_hitl(entorno):
    deps, _, reg, rapido = entorno
    g = construir_grafo(deps, MemorySaver(), rapido)
    r = g.invoke({"solicitud": "C-9999 pide 2 EDGE-ORIN", "id_hilo": "X1"}, cfg("X1"))
    assert "__interrupt__" not in r and "el cliente no existe" in r["respuesta"] and reg.filas == {}


def test_consulta_de_stock_decide_no_usar_rag(entorno):
    deps, fuentes, _, rapido = entorno
    g = construir_grafo(deps, MemorySaver(), rapido)
    r = g.invoke({"solicitud": "¿Cuánto stock hay de EDGE-ORIN?", "id_hilo": "S1"}, cfg("S1"))
    assert deps.politicas.consultas == 0  # el dato es transaccional: no se consulta el RAG
    assert "politica" not in r["evidencia"] and "35 unidades" in r["respuesta"]


def test_pregunta_de_politica_si_usa_rag_y_cita_la_fuente(entorno):
    deps, fuentes, _, rapido = entorno
    g = construir_grafo(deps, MemorySaver(), rapido)
    r = g.invoke({"solicitud": "¿Qué dice la política cuando un cliente está en hold?", "id_hilo": "S2"}, cfg("S2"))
    assert deps.politicas.consultas == 1 and fuentes.llamadas == 0
    assert "politica_credito.md · Línea insuficiente" in r["respuesta"]


def test_solicitud_ambigua_pide_aclaracion(entorno):
    deps, fuentes, _, rapido = entorno
    g = construir_grafo(deps, MemorySaver(), rapido)
    r = g.invoke({"solicitud": "Libera la venta de C-1003", "id_hilo": "A1"}, cfg("A1"))
    assert "Necesito más información" in r["respuesta"] and fuentes.llamadas == 0
