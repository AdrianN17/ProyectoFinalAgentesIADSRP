"""Respuesta final: plantilla por código; para liberaciones, Foundry redacta con salida estructurada validada por código."""
from __future__ import annotations

import json
import re
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

MOTIVOS = {
    "cliente_en_hold": "el cliente está en hold",
    "linea_insuficiente": "la línea de crédito es insuficiente",
    "monto_requiere_revision": "el monto alcanza el umbral de revisión de Finanzas",
    "stock_insuficiente": "no hay stock suficiente",
    "cliente_inexistente": "el cliente no existe",
    "sku_inexistente": "el SKU no existe",
    "cantidad_invalida": "la cantidad no es válida",
}

EstadoLiberacion = Literal[
    "liberada_automaticamente",
    "liberada_con_aprobacion",
    "rechazada_por_finanzas",
    "pendiente_de_aprobacion",
    "no_liberable",
    "datos_invalidos",
]

SISTEMA_REDACTOR = (
    "Redactas la respuesta de una solicitud de liberación de venta para un analista de ventas. "
    "Usa SOLO los hechos del JSON; no inventes cifras ni nombres. Devuelve:\n"
    "- estado: elige según los hechos.\n"
    "  resultado=ok -> liberada_automaticamente.\n"
    "  resultado=excepcion y aprobacion=null -> pendiente_de_aprobacion.\n"
    "  resultado=excepcion y aprobacion.aprobado=true -> liberada_con_aprobacion.\n"
    "  resultado=excepcion y aprobacion.aprobado=false -> rechazada_por_finanzas.\n"
    "  resultado=no_liberable -> no_liberable. resultado=datos_invalidos -> datos_invalidos.\n"
    "- aprobador: el nombre en aprobacion.aprobador; null si no hay aprobacion.\n"
    "- monto: el monto del JSON.\n"
    "- mensaje: 2 a 3 líneas en español que digan claramente el estado (liberada, rechazada, pendiente, "
    "'no liberable' o 'no se puede evaluar'), el monto, el aprobador si existe y los motivos. "
    "Escribe en lenguaje natural: nunca uses 'null' ni '[]' (si no hay aprobador humano o motivos, no los menciones "
    "o di 'sin aprobación humana')."
)

# Palabras que el mensaje debe contener para ser coherente con el estado declarado.
PALABRAS_POR_ESTADO = {
    "liberada_automaticamente": ["liberad"],
    "liberada_con_aprobacion": ["liberad"],
    "rechazada_por_finanzas": ["rechaz"],
    "pendiente_de_aprobacion": ["pendiente"],
    "no_liberable": ["no liberable", "no es liberable", "no se puede liberar", "no se libera", "no puede liberarse"],
    "datos_invalidos": ["no se puede evaluar", "no existe", "inválid", "invalid"],
}


class RespuestaLiberacion(BaseModel):
    estado: EstadoLiberacion
    aprobador: str | None
    monto: float
    mensaje: str = Field(min_length=1)


class LlmEstructurado(Protocol):
    def estructurado(self, sistema: str, usuario: str, modelo: type[RespuestaLiberacion]) -> RespuestaLiberacion: ...


def estado_esperado(e: dict[str, Any]) -> str:
    resultado = e["decision"]["resultado"]
    ap = e.get("aprobacion") or {}
    if resultado == "ok":
        return "liberada_automaticamente"
    if resultado == "excepcion":
        if not ap:
            return "pendiente_de_aprobacion"
        return "liberada_con_aprobacion" if ap.get("aprobado") else "rechazada_por_finanzas"
    return resultado  # no_liberable | datos_invalidos


def validar_respuesta(r: RespuestaLiberacion, e: dict[str, Any]) -> str | None:
    """Compara lo que devolvió el LLM con los hechos reales. Devuelve el motivo del rechazo, o None si es válida."""
    dec, ap = e["decision"], e.get("aprobacion") or {}
    esperado = estado_esperado(e)
    if r.estado != esperado:
        return f"estado '{r.estado}' != '{esperado}'"

    aprobador_real = (ap.get("aprobador") or "").strip() or None
    if (r.aprobador or "").strip().casefold() != (aprobador_real or "").casefold():
        return f"aprobador '{r.aprobador}' != '{aprobador_real}'"

    if abs(r.monto - float(dec["monto"])) > 0.01:
        return f"monto {r.monto} != {dec['monto']}"

    texto = r.mensaje.casefold()
    if not any(p in texto for p in PALABRAS_POR_ESTADO[esperado]):
        return f"el mensaje no expresa el estado '{esperado}'"
    if aprobador_real and aprobador_real.casefold() not in texto:
        return "el mensaje no nombra al aprobador"
    if dec["monto"] > 0 and str(round(dec["monto"])) not in re.sub(r"[.,\s']", "", r.mensaje):
        return "el mensaje no incluye el monto"
    return None


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
    def __init__(self, llm: LlmEstructurado | None = None):
        self.llm = llm

    def redactar(self, e: dict[str, Any]) -> str:
        cuerpo = _cuerpo(e)
        # El LLM solo redacta liberaciones (donde la decisión importa) y su salida se valida contra los hechos.
        if self.llm and e.get("destino") == "TOOLS" and e.get("intencion") == "liberacion":
            cuerpo, e = self._redactar_con_llm(e, cuerpo)
        return f"{cuerpo}\n\n{_pie(e)}"

    def _redactar_con_llm(self, e: dict[str, Any], plantilla: str) -> tuple[str, dict[str, Any]]:
        dec, lib = e["decision"], e.get("liberacion") or {}
        hechos = {
            "resultado": dec["resultado"], "motivos": [MOTIVOS.get(m, m) for m in dec["motivos"]], "monto": dec["monto"],
            "cliente_id": e.get("cliente_id"), "sku": e.get("sku"), "cantidad": e.get("cantidad"),
            "aprobacion": e.get("aprobacion") or None, "liberacion_id": lib.get("liberacion_id"),
        }
        try:
            r = self.llm.estructurado(SISTEMA_REDACTOR, json.dumps(hechos, ensure_ascii=False), RespuestaLiberacion)
            motivo = validar_respuesta(r, e)
        except Exception as ex:  # noqa: BLE001 - la plantilla siempre es el respaldo
            motivo = f"LLM no disponible: {type(ex).__name__}"
        if motivo:
            aviso = f"respuesta del LLM descartada ({motivo}); se usó la plantilla"
            return plantilla, {**e, "advertencias": [*e.get("advertencias", []), aviso]}
        mensaje = r.mensaje.strip()
        if lib.get("liberacion_id") and f"#{lib['liberacion_id']}" not in mensaje:
            mensaje += f" (liberación #{lib['liberacion_id']})"  # el id lo añade el código, no el modelo
        return mensaje, e
