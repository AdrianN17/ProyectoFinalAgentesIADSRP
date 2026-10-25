from andes_agent.reglas import evaluar_liberacion

CLIENTE = {"estado_credito": "activo", "limite_credito": 40000.0, "exposicion_actual": 30000.0}
PRODUCTO = {"precio_unitario": 1850.0, "stock_disponible": 35}


def evaluar(cliente=CLIENTE, producto=PRODUCTO, cantidad=12, revision=25000.0):
    return evaluar_liberacion(cliente=cliente, producto=producto, cantidad=cantidad, monto_revision=revision)


def test_linea_insuficiente_es_excepcion():
    d = evaluar()
    assert d.resultado == "excepcion"
    assert d.motivos == ["linea_insuficiente"]
    assert d.monto == 22200.0


def test_cliente_en_hold_es_excepcion():
    d = evaluar(cliente={**CLIENTE, "estado_credito": "hold", "limite_credito": 500000.0}, cantidad=1)
    assert d.resultado == "excepcion" and d.motivos == ["cliente_en_hold"]


def test_monto_de_revision():
    d = evaluar(cliente={**CLIENTE, "limite_credito": 500000.0}, revision=20000.0)
    assert d.motivos == ["monto_requiere_revision"]


def test_venta_sana_se_libera():
    d = evaluar(cliente={**CLIENTE, "limite_credito": 500000.0}, cantidad=2)
    assert d.resultado == "ok" and d.motivos == []


def test_stock_insuficiente_no_escala():
    d = evaluar(producto={**PRODUCTO, "stock_disponible": 5})
    assert d.resultado == "no_liberable" and "stock_insuficiente" in d.motivos


def test_datos_invalidos():
    assert evaluar(cliente=None).motivos == ["cliente_inexistente"]
    assert evaluar(producto=None).motivos == ["sku_inexistente"]
    assert evaluar(cantidad=0).motivos == ["cantidad_invalida"]
