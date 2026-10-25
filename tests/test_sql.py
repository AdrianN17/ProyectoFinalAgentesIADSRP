"""Pruebas de SQL parametrizado (db.py) con una conexión simulada: no necesitan Azure SQL.

Lo que se verifica: cada consulta lleva los valores en `params` y nunca interpolados en el texto SQL.
"""
import pytest
import pyodbc
from andes_agent import db as db_mod
from andes_agent.db import Repositorio


class _Cursor:
    def __init__(self, conexion):
        self.c = conexion
        self.description = None
        self._filas = []

    def execute(self, sql, params=()):
        self.c.llamadas.append((" ".join(sql.split()), tuple(params)))
        columnas, filas = self.c.respuestas.pop(0)
        self.description = [(n,) for n in columnas]
        self._filas = filas
        return self

    def fetchall(self):
        return self._filas

    def fetchone(self):
        return self._filas[0] if self._filas else None


class _Conexion:
    def __init__(self, respuestas):
        self.respuestas, self.llamadas = list(respuestas), []

    def cursor(self):
        return _Cursor(self)

    def close(self):
        pass


@pytest.fixture
def conexion_falsa(monkeypatch):
    def preparar(respuestas):
        conn = _Conexion(respuestas)
        monkeypatch.setattr(db_mod, "conectar", lambda s=None, autocommit=False: conn)
        return conn

    return preparar


def test_sql_1_stock_usa_parametro_y_vista(conexion_falsa):
    conn = conexion_falsa([(["sku", "nombre", "precio_unitario", "lead_time_dias", "stock_disponible"],
                            [("EDGE-ORIN", "Gateway", 1850, 3, 33)])])
    r = Repositorio().consultar_stock("EDGE-ORIN")
    sql, params = conn.llamadas[0]
    assert "FROM ops.v_stock WHERE sku = ?" in sql and params == ("EDGE-ORIN",)
    assert r["encontrado"] and r["stock_disponible"] == 33 and r["fuente"] == "azure_sql:ops.v_stock"


def test_sql_2_credito_inexistente_y_texto_malicioso_va_como_parametro(conexion_falsa):
    malicioso = "C-1'; DROP TABLE ops.clientes;--"
    conn = conexion_falsa([(["cliente_id"], [])])
    r = Repositorio().consultar_estado_credito(malicioso)
    sql, params = conn.llamadas[0]
    assert malicioso not in sql and params == (malicioso,)
    assert r == {"encontrado": False, "cliente_id": malicioso}


def test_sql_3_historial_acota_el_limite_y_resume_pagos(conexion_falsa):
    conn = conexion_falsa([
        (["venta_id", "fecha", "total", "estado", "condicion_pago"], [(5008, "2026-04-02", 24000, "facturada", "credito_30")]),
        (["pagos_totales", "pagos_vencidos", "monto_vencido"], [(2, 2, 39500)]),
    ])
    r = Repositorio().consultar_historial_ventas("C-1004", limite=9999)
    (sql_ventas, p_ventas), (sql_pagos, p_pagos) = conn.llamadas
    assert "TOP (?)" in sql_ventas and p_ventas == (20, "C-1004")  # límite acotado a 20
    assert p_pagos == ("C-1004",)
    assert r["resumen_pagos"]["pagos_vencidos"] == 2 and r["encontrado"]


def test_ejecutar_solo_permite_operaciones_conocidas(conexion_falsa):
    conexion_falsa([])
    with pytest.raises(KeyError):
        Repositorio().ejecutar("ejecutar_sql", {"sql": "SELECT * FROM ops.clientes"})


# --- Azure SQL serverless: la primera conexión tras la pausa automática falla mientras reanuda ---

class _Ajustes:
    sql_server, sql_database, sql_auth = "srv.database.windows.net", "bd", "sql"
    sql_user, sql_password, sql_driver = "u", "p", "ODBC Driver 18 for SQL Server"


def _error_reanudando():
    return pyodbc.OperationalError(
        "08001", "[08001] Database 'bd' on server 'srv' is not currently available. (40613) (SQLDriverConnect)")


def test_conexion_reintenta_mientras_la_base_reanuda(monkeypatch):
    intentos, esperas = [], []

    def conectar_falso(*args, **kwargs):
        intentos.append(1)
        if len(intentos) <= 2:
            raise _error_reanudando()
        return "CONEXION"

    monkeypatch.setattr(db_mod.pyodbc, "connect", conectar_falso)
    monkeypatch.setattr(db_mod.time, "sleep", esperas.append)
    assert db_mod.conectar(_Ajustes()) == "CONEXION"
    assert len(intentos) == 3 and esperas == [db_mod.ESPERA_CONEXION_S] * 2


def test_conexion_no_reintenta_errores_que_no_son_transitorios(monkeypatch):
    intentos = []

    def conectar_falso(*args, **kwargs):
        intentos.append(1)
        raise pyodbc.OperationalError("28000", "[28000] Login failed for user 'u'. (18456)")

    monkeypatch.setattr(db_mod.pyodbc, "connect", conectar_falso)
    monkeypatch.setattr(db_mod.time, "sleep", lambda s: pytest.fail("no debe esperar"))
    with pytest.raises(pyodbc.OperationalError):
        db_mod.conectar(_Ajustes())
    assert len(intentos) == 1  # credenciales malas: fallar rápido, no esperar 50 s


def test_conexion_se_rinde_tras_agotar_los_intentos(monkeypatch):
    intentos = []

    def siempre_reanudando(*args, **kwargs):
        intentos.append(1)
        raise _error_reanudando()

    monkeypatch.setattr(db_mod.pyodbc, "connect", siempre_reanudando)
    monkeypatch.setattr(db_mod.time, "sleep", lambda s: None)
    with pytest.raises(pyodbc.OperationalError):
        db_mod.conectar(_Ajustes())
    assert len(intentos) == db_mod.INTENTOS_CONEXION
