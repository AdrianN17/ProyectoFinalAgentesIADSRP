"""El LLM redacta con salida estructurada, pero el código valida cada campo contra los hechos reales."""
import pytest

from andes_agent.redactor import Redactor, RespuestaLiberacion, estado_esperado, validar_respuesta


def estado(resultado="excepcion", aprobacion=None, monto=22200.0, motivos=("linea_insuficiente",)):
    return {
        "id_hilo": "T1", "destino": "TOOLS", "intencion": "liberacion",
        "cliente_id": "C-1003", "sku": "EDGE-ORIN", "cantidad": 12,
        "decision": {"resultado": resultado, "motivos": list(motivos), "monto": monto,
                     "exposicion": 34092.0, "limite": 40000.0},
        "aprobacion": aprobacion or {}, "liberacion": {"creada": True, "liberacion_id": 18} if aprobacion else {},
        "evidencia": {}, "advertencias": [], "traza": ["parsear", "enrutar"],
    }


APROBADA = {"aprobado": True, "aprobador": "Ana (Finanzas)", "comentario": ""}
RECHAZADA = {"aprobado": False, "aprobador": "Ana (Finanzas)", "comentario": "Mora"}


class LlmFalso:
    def __init__(self, respuesta=None, error=None):
        self.respuesta, self.error, self.llamadas = respuesta, error, 0

    def estructurado(self, sistema, usuario, modelo):
        self.llamadas += 1
        if self.error:
            raise self.error
        return self.respuesta


def buena(**cambios):
    base = dict(estado="liberada_con_aprobacion", aprobador="Ana (Finanzas)", monto=22200.0,
                mensaje="La venta de 12 EDGE-ORIN por 22.200,00 quedó liberada tras la aprobación de Ana (Finanzas).")
    return RespuestaLiberacion(**{**base, **cambios})


def test_respuesta_valida_del_llm_se_usa_y_el_codigo_agrega_el_id():
    llm = LlmFalso(buena())
    texto = Redactor(llm).redactar(estado(aprobacion=APROBADA))
    assert "liberada tras la aprobación de Ana (Finanzas)" in texto
    assert "(liberación #18)" in texto  # lo agrega el código
    assert "descartada" not in texto and llm.llamadas == 1


@pytest.mark.parametrize(
    "respuesta, motivo",
    [
        (buena(estado="rechazada_por_finanzas", mensaje="Venta rechazada por Ana (Finanzas), 22200."), "estado"),
        (buena(aprobador="Pedro"), "aprobador"),
        (buena(aprobador=None), "aprobador"),
        (buena(monto=2220.0), "monto"),
        (buena(mensaje="Decisión: excepción. Monto 22200."), "no expresa el estado"),  # el caso real que falló
        (buena(mensaje="Quedó liberada por 22200."), "no nombra al aprobador"),
        (buena(mensaje="Quedó liberada tras la aprobación de Ana (Finanzas)."), "no incluye el monto"),
    ],
)
def test_si_el_llm_contradice_o_omite_se_usa_la_plantilla(respuesta, motivo):
    e = estado(aprobacion=APROBADA)
    assert motivo in validar_respuesta(respuesta, e)
    texto = Redactor(LlmFalso(respuesta)).redactar(e)
    assert "liberada tras aprobación de Ana (Finanzas) (liberación #18)" in texto  # plantilla del código
    assert "respuesta del LLM descartada" in texto and motivo in texto


def test_si_el_llm_falla_se_usa_la_plantilla_con_advertencia():
    texto = Redactor(LlmFalso(error=TimeoutError())).redactar(estado(aprobacion=APROBADA))
    assert "liberada tras aprobación de Ana (Finanzas)" in texto and "LLM no disponible: TimeoutError" in texto


@pytest.mark.parametrize(
    "e, esperado",
    [
        (estado("ok", monto=3700.0, motivos=()), "liberada_automaticamente"),
        (estado(), "pendiente_de_aprobacion"),
        (estado(aprobacion=APROBADA), "liberada_con_aprobacion"),
        (estado(aprobacion=RECHAZADA), "rechazada_por_finanzas"),
        (estado("no_liberable", monto=925000.0), "no_liberable"),
        (estado("datos_invalidos", monto=0.0), "datos_invalidos"),
    ],
)
def test_estado_esperado_sale_de_los_hechos(e, esperado):
    assert estado_esperado(e) == esperado


def test_rechazo_valido():
    e = estado(aprobacion=RECHAZADA)
    r = buena(estado="rechazada_por_finanzas", mensaje="Venta de 22200 rechazada por Ana (Finanzas): mora vencida.")
    assert validar_respuesta(r, e) is None


def test_automatica_sin_aprobador():
    e = estado("ok", monto=3700.0, motivos=())
    ok = buena(estado="liberada_automaticamente", aprobador=None, monto=3700.0, mensaje="Liberada automáticamente por 3.700,00.")
    assert validar_respuesta(ok, e) is None
    inventa = buena(estado="liberada_automaticamente", aprobador="Ana", monto=3700.0, mensaje="Liberada por 3700 con Ana.")
    assert "aprobador" in validar_respuesta(inventa, e)


def test_datos_invalidos_sin_monto_no_exige_cifra():
    e = estado("datos_invalidos", monto=0.0, motivos=("cliente_inexistente",))
    r = buena(estado="datos_invalidos", aprobador=None, monto=0.0, mensaje="No se puede evaluar: el cliente no existe.")
    assert validar_respuesta(r, e) is None


def test_el_llm_no_se_usa_fuera_de_las_liberaciones():
    llm = LlmFalso(buena())
    e = {"id_hilo": "T2", "destino": "TOOLS", "intencion": "stock", "sku": "EDGE-ORIN", "advertencias": [], "traza": [],
         "evidencia": {"stock": {"encontrado": True, "sku": "EDGE-ORIN", "stock_disponible": 33, "lead_time_dias": 3,
                                 "fuente": "azure_sql:ops.v_stock"}}}
    texto = Redactor(llm).redactar(e)
    assert llm.llamadas == 0 and "33 unidades disponibles" in texto
