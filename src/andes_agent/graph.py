"""Workflow LangGraph: parsear > enrutar > consultar_fuentes > evaluar_reglas > aprobacion_humana > registrar > responder."""
from __future__ import annotations

import operator
from dataclasses import asdict, dataclass
from typing import Annotated, Any, Protocol, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy, interrupt
from pydantic import BaseModel

from .errores import FalloTransitorio
from .fuentes import Fuentes
from .parser import Solicitud, parsear
from .redactor import Redactor
from .reglas import evaluar_liberacion
from .router import Router

CONSULTA_POLITICA_LIBERACION = "venta a crédito cliente en hold línea insuficiente excepción aprobación Finanzas"
UMBRAL_RAG = 0.35  # por debajo, el fragmento no se cita como fuente


class Estado(TypedDict, total=False):
    """Estado pequeño: solo identificadores, rutas y evidencia mínima. Sin historiales largos ni documentos completos."""

    id_hilo: str
    solicitud: str
    cliente_id: str | None
    sku: str | None
    cantidad: int | None
    destino: str
    intencion: str
    confianza: float
    evidencia: dict[str, Any]
    decision: dict[str, Any]
    aprobacion: dict[str, Any]
    liberacion: dict[str, Any]
    respuesta: str
    advertencias: Annotated[list[str], operator.add]
    traza: Annotated[list[str], operator.add]


class Aprobacion(BaseModel):
    aprobado: bool
    aprobador: str
    comentario: str = ""


class Politicas(Protocol):
    def buscar(self, consulta: str, k: int = 3, umbral: float = 0.0) -> list[dict[str, Any]]: ...


class Registrador(Protocol):
    def registrar_liberacion(
        self, id_hilo: str, cliente_id: str, sku: str, cantidad: int, monto: float,
        aprobado_por: str, motivos: list[str],
    ) -> dict[str, Any]: ...


@dataclass
class Dependencias:
    fuentes: Fuentes
    politicas: Politicas
    registrador: Registrador
    router: Router
    redactor: Redactor


def _plan(intencion: str, cliente: str | None, sku: str | None) -> dict[str, tuple[str, dict[str, Any]]]:
    plan: dict[str, tuple[str, dict[str, Any]]] = {}
    if intencion in {"liberacion", "stock"}:
        plan["stock"] = ("consultar_stock", {"sku": sku})
    if intencion in {"liberacion", "credito"}:
        plan["credito"] = ("consultar_estado_credito", {"cliente_id": cliente})
    if intencion in {"liberacion", "historial"}:
        plan["historial"] = ("consultar_historial_ventas", {"cliente_id": cliente, "limite": 5})
    if intencion == "liberacion":
        plan["parametros"] = ("consultar_parametros_credito", {})
    return plan


def construir_grafo(
    deps: Dependencias,
    checkpointer: BaseCheckpointSaver | None = None,
    reintento: RetryPolicy | None = None,
):
    # Reintento solo para fallos técnicos transitorios, nunca para reglas de negocio.
    reintento = reintento or RetryPolicy(max_attempts=3, initial_interval=0.5, retry_on=FalloTransitorio)

    def parsear_solicitud(e: Estado) -> dict[str, Any]:
        s = parsear(e["solicitud"])
        return {
            "cliente_id": s.cliente_id, "sku": s.sku, "cantidad": s.cantidad,
            "evidencia": {}, "decision": {}, "aprobacion": {}, "liberacion": {},
            "traza": ["parsear"],
        }

    def enrutar(e: Estado) -> dict[str, Any]:
        ruta = deps.router.decidir(e["solicitud"], Solicitud(e["cliente_id"], e["sku"], e["cantidad"]))
        return {
            "destino": ruta.destino, "intencion": ruta.intencion, "confianza": ruta.confianza,
            "traza": [f"enrutar:{ruta.destino}/{ruta.intencion}({ruta.origen},{ruta.confianza:.2f})"],
        }

    def consultar_fuentes(e: Estado) -> dict[str, Any]:
        intencion = e["intencion"]
        plan = _plan(intencion, e.get("cliente_id"), e.get("sku"))
        evidencia: dict[str, Any] = {}
        if plan:
            resultados = deps.fuentes.llamar(list(plan.values()))
            evidencia = dict(zip(plan.keys(), resultados))
        advertencias: list[str] = []
        if intencion in {"liberacion", "politica"}:
            consulta = e["solicitud"] if intencion == "politica" else CONSULTA_POLITICA_LIBERACION
            try:
                evidencia["politica"] = deps.politicas.buscar(consulta, k=2, umbral=UMBRAL_RAG)
            except Exception as ex:  # noqa: BLE001 - la política cita, no decide: se degrada con advertencia
                evidencia["politica"] = []
                advertencias.append(f"RAG (Qdrant) no disponible: {type(ex).__name__}")
        return {"evidencia": evidencia, "advertencias": advertencias, "traza": ["consultar_fuentes"]}

    def evaluar_reglas(e: Estado) -> dict[str, Any]:
        ev = e["evidencia"]
        stock, credito = ev["stock"], ev["credito"]
        d = evaluar_liberacion(
            cliente=credito if credito.get("encontrado") else None,
            producto=stock if stock.get("encontrado") else None,
            cantidad=e.get("cantidad"),
            monto_revision=ev["parametros"]["monto_revision"],
        )
        return {"decision": asdict(d), "traza": [f"evaluar_reglas:{d.resultado}"]}

    def aprobacion_humana(e: Estado) -> dict[str, Any]:
        # Sin side effects antes de interrupt(): al reanudar este nodo se ejecuta de nuevo desde el inicio.
        respuesta = interrupt({
            "tipo": "aprobacion_credito",
            "id_hilo": e["id_hilo"],
            "cliente_id": e["cliente_id"], "sku": e["sku"], "cantidad": e["cantidad"],
            "monto": e["decision"]["monto"],
            "motivos": e["decision"]["motivos"],
            "aprobador_requerido": "Finanzas/Crédito",
        })
        ap = Aprobacion.model_validate(respuesta)
        return {"aprobacion": ap.model_dump(), "traza": [f"aprobacion_humana:{'aprobada' if ap.aprobado else 'rechazada'}"]}

    def registrar_liberacion(e: Estado) -> dict[str, Any]:
        d = e["decision"]
        aprobador = e.get("aprobacion", {}).get("aprobador") or "REGLAS_AUTOMATICAS"
        lib = deps.registrador.registrar_liberacion(
            e["id_hilo"], e["cliente_id"], e["sku"], e["cantidad"], d["monto"], aprobador, d["motivos"],
        )
        return {"liberacion": lib, "traza": ["registrar_liberacion"]}

    def responder(e: Estado) -> dict[str, Any]:
        return {"respuesta": deps.redactor.redactar(dict(e)), "traza": ["responder"]}

    def tras_enrutar(e: Estado) -> str:
        return "consultar_fuentes" if e["destino"] in {"RAG", "SQL", "TOOLS"} else "responder"

    def tras_fuentes(e: Estado) -> str:
        return "evaluar_reglas" if e["intencion"] == "liberacion" else "responder"

    def tras_reglas(e: Estado) -> str:
        return {"excepcion": "aprobacion_humana", "ok": "registrar_liberacion"}.get(
            e["decision"]["resultado"], "responder")

    def tras_aprobacion(e: Estado) -> str:
        return "registrar_liberacion" if e["aprobacion"]["aprobado"] else "responder"

    g = StateGraph(Estado)
    g.add_node("parsear_solicitud", parsear_solicitud)
    g.add_node("enrutar", enrutar)
    g.add_node("consultar_fuentes", consultar_fuentes, retry_policy=reintento)
    g.add_node("evaluar_reglas", evaluar_reglas)
    g.add_node("aprobacion_humana", aprobacion_humana)
    g.add_node("registrar_liberacion", registrar_liberacion)
    g.add_node("responder", responder)

    g.add_edge(START, "parsear_solicitud")
    g.add_edge("parsear_solicitud", "enrutar")
    g.add_conditional_edges("enrutar", tras_enrutar, ["consultar_fuentes", "responder"])
    g.add_conditional_edges("consultar_fuentes", tras_fuentes, ["evaluar_reglas", "responder"])
    g.add_conditional_edges(
        "evaluar_reglas", tras_reglas, ["aprobacion_humana", "registrar_liberacion", "responder"])
    g.add_conditional_edges("aprobacion_humana", tras_aprobacion, ["registrar_liberacion", "responder"])
    g.add_edge("registrar_liberacion", "responder")
    g.add_edge("responder", END)
    return g.compile(checkpointer=checkpointer)
