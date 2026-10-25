"""Respuesta final: texto por plantilla (o redactado por Foundry) + fuentes, advertencias y trazabilidad por código."""
from __future__ import annotations

import json
from typing import Any, Protocol

MOTIVOS = {
    "cliente_en_hold": "el cliente está en hold",
    "linea_insuficiente": "la línea de crédito es insuficiente",
    "monto_requiere_revision": "el monto alcanza el umbral de revisión de Finanzas",
    "stock_insuficiente": "no hay stock suficiente",
    "cliente_inexistente": "el cliente no existe",
    "sku_inexistente": "el SKU no existe",
    "cantidad_invalida": "la cantidad no es válida",
}

SISTEMA_REDACTOR = (
    "Redacta en español, en 3 a 5 líneas, una respuesta para un analista de ventas usando SOLO los hechos del JSON. "
    "No inventes cifras, no cambies la decisión y no prometas aprobaciones."
)


class LlmTexto(Protocol):
    def texto(self, sistema: str, usuario: str) -> str: ...


def _motivos(codigos: list[str]) -> str:
    return "; ".join(MOTIVOS.get(c, c) for c in codigos)


def _cuerpo(e: dict[str, Any]) -> str:
    ev, dec, intencion = e.get("evidencia", {}), e.get("decision", {}), e.get("intencion")
    if e.get("destino") == "CLARIFY":
        return "Necesito más información. Indica cliente (C-####), SKU y cantidad, o reformula la consulta."
    if e.get("destino") == "DIRECT":
        return "Puedo consultar stock, estado de crédito, historial de pagos, políticas y gestionar liberaciones de venta."
    if intencion == "stock":
        s = ev.get("stock", {})
        if not s.get("encontrado"):
            return f"El SKU {e.get('sku')} no existe."
        return f"{s['sku']}: {s['stock_disponible']} unidades disponibles, lead time {s['lead_time_dias']} días."
    if intencion == "credito":
        c = ev.get("credito", {})
        if not c.get("encontrado"):
            return f"El cliente {e.get('cliente_id')} no existe."
        return (f"{c['cliente_id']} ({c['nombre']}): estado {c['estado_credito']}, límite {c['limite_credito']:.2f}, "
                f"exposición {c['exposicion_actual']:.2f}, disponible {c['credito_disponible']:.2f}.")
    if intencion == "historial":
        h = ev.get("historial", {})
        if not h.get("encontrado"):
            return f"Sin historial para {e.get('cliente_id')}."
        p = h["resumen_pagos"]
        return (f"{h['cliente_id']}: {len(h['ultimas_ventas'])} ventas recientes; pagos vencidos: "
                f"{p['pagos_vencidos']} por {p['monto_vencido']:.2f}.")
    if intencion == "politica":
        frag = ev.get("politica", [])
        return frag[0]["texto"] if frag else "No encontré una política aplicable."
    if intencion == "liberacion":
        r, ap, lib = dec.get("resultado"), e.get("aprobacion"), e.get("liberacion")
        base = f"Venta de {e.get('cantidad')} x {e.get('sku')} para {e.get('cliente_id')} por {dec.get('monto', 0):.2f}"
        if r == "datos_invalidos":
            return f"No se puede evaluar: {_motivos(dec['motivos'])}."
        if r == "no_liberable":
            return f"{base} NO liberable: {_motivos(dec['motivos'])}."
        if r == "ok":
            return f"{base} liberada automáticamente (liberación #{lib['liberacion_id']})."
        if ap and ap.get("aprobado"):
            return f"{base} liberada tras aprobación de {ap['aprobador']} (liberación #{lib['liberacion_id']})."
        if ap:
            return f"{base} RECHAZADA por {ap['aprobador']}. Motivos de la excepción: {_motivos(dec['motivos'])}."
        return f"{base} pendiente de aprobación de Finanzas/Crédito: {_motivos(dec['motivos'])}."
    return "Sin resultado."


def _pie(e: dict[str, Any]) -> str:
    ev = e.get("evidencia", {})
    fuentes = {v["fuente"] for v in ev.values() if isinstance(v, dict) and "fuente" in v}
    fuentes |= {f"{f['fuente']} · {f['seccion']}" for f in ev.get("politica", [])}
    lineas = []
    if fuentes:
        lineas.append("Fuentes: " + "; ".join(sorted(fuentes)))
    if e.get("advertencias"):
        lineas.append("Advertencias: " + " | ".join(e["advertencias"]))
    lineas.append(f"Trazabilidad: hilo={e.get('id_hilo')} ruta={e.get('destino')}/{e.get('intencion')} "
                  f"pasos={' > '.join(e.get('traza', []))}")
    return "\n".join(lineas)


class Redactor:
    def __init__(self, llm: LlmTexto | None = None):
        self.llm = llm

    def redactar(self, e: dict[str, Any]) -> str:
        cuerpo = _cuerpo(e)
        if self.llm and e.get("destino") not in {"CLARIFY", "DIRECT"}:
            try:
                hechos = {"respuesta_base": cuerpo, "decision": e.get("decision"), "aprobacion": e.get("aprobacion")}
                cuerpo = self.llm.texto(SISTEMA_REDACTOR, json.dumps(hechos, ensure_ascii=False)) or cuerpo
            except Exception as ex:  # noqa: BLE001 - la plantilla siempre es el respaldo
                e = {**e, "advertencias": [*e.get("advertencias", []), f"redactor LLM no disponible: {type(ex).__name__}"]}
        return f"{cuerpo}\n\n{_pie(e)}"
