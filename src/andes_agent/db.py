"""Acceso a Azure SQL: consultas fijas y parametrizadas (nunca SQL libre del LLM)."""
from __future__ import annotations

import struct
import sys
import time
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterator

import pyodbc
from azure.identity import DefaultAzureCredential

from .errores import ErrorConfiguracion, FalloTransitorio
from .settings import Settings, get_settings

ALCANCE_SQL = "https://database.windows.net/.default"
SQL_COPT_SS_ACCESS_TOKEN = 1256
_credencial: DefaultAzureCredential | None = None

# Azure SQL serverless se pausa por inactividad (aquí a los 60 min): la primera conexión falla mientras reanuda.
CODIGOS_BASE_REANUDANDO = ("40613", "40197", "40501", "49918", "10928", "10929")
INTENTOS_CONEXION = 6
ESPERA_CONEXION_S = 10.0


def _base_reanudando(e: Exception) -> bool:
    texto = str(e).lower()
    return (any(c in texto for c in CODIGOS_BASE_REANUDANDO)
            or "not currently available" in texto or "timeout expired" in texto)


def _abrir(*args: Any, **kwargs: Any) -> pyodbc.Connection:
    """pyodbc.connect con espera y reintento solo cuando la base está despertando (error transitorio)."""
    for intento in range(1, INTENTOS_CONEXION + 1):
        try:
            return pyodbc.connect(*args, **kwargs)
        except (pyodbc.OperationalError, pyodbc.InterfaceError) as e:
            if intento == INTENTOS_CONEXION or not _base_reanudando(e):
                raise
            # stderr: el servidor MCP usa stdout para el protocolo
            print(f"  [Azure SQL] la base está reanudando (intento {intento}/{INTENTOS_CONEXION}), "
                  f"reintento en {ESPERA_CONEXION_S:.0f} s...", file=sys.stderr, flush=True)
            time.sleep(ESPERA_CONEXION_S)
    raise AssertionError("inalcanzable")


def conectar(s: Settings | None = None, autocommit: bool = False) -> pyodbc.Connection:
    s = s or get_settings()
    if not s.sql_server or not s.sql_database:
        raise ErrorConfiguracion("Faltan AZURE_SQL_SERVER y/o AZURE_SQL_DATABASE.")
    base = (
        f"Driver={{{s.sql_driver}}};Server=tcp:{s.sql_server},1433;Database={s.sql_database};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )
    if s.sql_auth == "sql":
        return _abrir(base + f"Uid={s.sql_user};Pwd={s.sql_password};", autocommit=autocommit)

    global _credencial
    _credencial = _credencial or DefaultAzureCredential()
    token = _credencial.get_token(ALCANCE_SQL).token.encode("utf-16-le")
    empaquetado = struct.pack(f"<I{len(token)}s", len(token), token)
    return _abrir(base, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: empaquetado}, autocommit=autocommit)


def _valor(v: Any) -> Any:
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


def _filas(cursor: pyodbc.Cursor) -> list[dict[str, Any]]:
    columnas = [c[0] for c in cursor.description]
    return [{c: _valor(v) for c, v in zip(columnas, fila)} for fila in cursor.fetchall()]


@contextmanager
def conexion(s: Settings | None = None, autocommit: bool = True) -> Iterator[pyodbc.Connection]:
    conn = conectar(s, autocommit=autocommit)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def _traducir_errores() -> Iterator[None]:
    """Errores de conexión/timeout (p. ej. Azure SQL serverless reanudando) => reintentables."""
    try:
        yield
    except (pyodbc.OperationalError, pyodbc.InterfaceError) as e:
        raise FalloTransitorio(str(e)) from e


class Repositorio:
    def __init__(self, settings: Settings | None = None):
        self.s = settings or get_settings()

    def _consultar(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with _traducir_errores(), conexion(self.s) as conn:
            return _filas(conn.cursor().execute(sql, params))

    def consultar_stock(self, sku: str) -> dict[str, Any]:
        filas = self._consultar(
            "SELECT sku, nombre, precio_unitario, lead_time_dias, stock_disponible FROM ops.v_stock WHERE sku = ?",
            (sku,),
        )
        return {"encontrado": True, **filas[0], "fuente": "azure_sql:ops.v_stock"} if filas else {
            "encontrado": False, "sku": sku}

    def consultar_estado_credito(self, cliente_id: str) -> dict[str, Any]:
        filas = self._consultar(
            "SELECT cliente_id, nombre, estado_credito, limite_credito, exposicion_actual, credito_disponible, "
            "plazo_dias FROM ops.v_estado_credito WHERE cliente_id = ?",
            (cliente_id,),
        )
        return {"encontrado": True, **filas[0], "fuente": "azure_sql:ops.v_estado_credito"} if filas else {
            "encontrado": False, "cliente_id": cliente_id}

    def consultar_historial_ventas(self, cliente_id: str, limite: int = 5) -> dict[str, Any]:
        limite = max(1, min(int(limite), 20))
        ventas = self._consultar(
            "SELECT TOP (?) venta_id, fecha, total, estado, condicion_pago FROM ops.v_ventas_cliente "
            "WHERE cliente_id = ? ORDER BY fecha DESC",
            (limite, cliente_id),
        )
        pagos = self._consultar(
            "SELECT COUNT(*) AS pagos_totales, "
            "SUM(CASE WHEN estado = 'vencido' THEN 1 ELSE 0 END) AS pagos_vencidos, "
            "COALESCE(SUM(CASE WHEN estado = 'vencido' THEN monto ELSE 0 END), 0) AS monto_vencido "
            "FROM ops.v_pagos_cliente WHERE cliente_id = ?",
            (cliente_id,),
        )[0]
        return {
            "encontrado": bool(ventas),
            "cliente_id": cliente_id,
            "ultimas_ventas": ventas,
            "resumen_pagos": {k: (v or 0) for k, v in pagos.items()},
            "fuente": "azure_sql:ops.v_ventas_cliente,ops.v_pagos_cliente",
        }

    def consultar_parametros_credito(self) -> dict[str, Any]:
        filas = self._consultar("SELECT valor FROM ops.parametros_caso WHERE clave = 'monto_revision'")
        if not filas:
            raise ErrorConfiguracion("Falta el parámetro monto_revision en ops.parametros_caso.")
        return {"monto_revision": float(filas[0]["valor"]), "fuente": "azure_sql:ops.parametros_caso"}

    def ejecutar(self, herramienta: str, args: dict[str, Any]) -> dict[str, Any]:
        """Despacho cerrado: solo estas operaciones existen."""
        permitidas = {
            "consultar_stock": self.consultar_stock,
            "consultar_estado_credito": self.consultar_estado_credito,
            "consultar_historial_ventas": self.consultar_historial_ventas,
            "consultar_parametros_credito": self.consultar_parametros_credito,
        }
        return permitidas[herramienta](**args)

    def registrar_liberacion(
        self, id_hilo: str, cliente_id: str, sku: str, cantidad: int, monto: float,
        aprobado_por: str, motivos: list[str],
    ) -> dict[str, Any]:
        """Idempotente: UNIQUE(id_hilo) evita duplicar si el nodo se re-ejecuta o se reanuda dos veces."""
        with _traducir_errores(), conexion(self.s) as conn:
            cur = conn.cursor()
            existente = cur.execute(
                "SELECT liberacion_id FROM ops.liberaciones WHERE id_hilo = ?", (id_hilo,)
            ).fetchone()
            if existente:
                return {"creada": False, "liberacion_id": existente[0]}
            creada = True
            try:
                cur.execute(
                    "INSERT INTO ops.liberaciones (id_hilo, cliente_id, sku, cantidad, monto, aprobado_por, motivos) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (id_hilo, cliente_id, sku, cantidad, monto, aprobado_por, ",".join(motivos)),
                )
            except pyodbc.IntegrityError:  # carrera con otra ejecución del mismo hilo
                creada = False
            fila = cur.execute(
                "SELECT liberacion_id FROM ops.liberaciones WHERE id_hilo = ?", (id_hilo,)
            ).fetchone()
            return {"creada": creada, "liberacion_id": fila[0]}
