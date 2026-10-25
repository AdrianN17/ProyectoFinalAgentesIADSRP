"""Crea el esquema en Azure SQL, carga los datos de prueba y aplica los parámetros de la semilla 7885."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from .config_caso import CLIENTE_CASO, SKU_CASO, SEMILLA, CASO_ID, generar_parametros, imprimir_parametros
from .db import conexion

DIR_SQL = Path(__file__).resolve().parents[2] / "sql"


def lotes(sql: str) -> list[str]:
    """Separa por líneas 'GO' (no es T-SQL, es separador de herramientas cliente)."""
    return [b.strip() for b in re.split(r"^\s*GO\s*$", sql, flags=re.M | re.I) if b.strip()]


def ejecutar_archivo(cur, nombre: str) -> None:
    for lote in lotes((DIR_SQL / nombre).read_text(encoding="utf-8")):
        cur.execute(lote)


def aplicar_semilla(cur) -> None:
    p = generar_parametros()
    cur.execute(
        "UPDATE ops.clientes SET limite_credito = ?, exposicion_actual = ?, estado_credito = 'activo' "
        "WHERE cliente_id = ?", (p.limite_credito, p.exposicion_actual, CLIENTE_CASO))
    cur.execute("UPDATE ops.inventario SET stock_disponible = ? WHERE sku = ?", (p.stock_edge_orin, SKU_CASO))
    cur.execute("UPDATE ops.productos SET lead_time_dias = ? WHERE sku = ?", (p.lead_time_dias, SKU_CASO))
    for clave, valor in {
        "caso_id": CASO_ID, "semilla": str(SEMILLA), "monto_revision": f"{p.monto_revision:.2f}",
    }.items():
        cur.execute("DELETE FROM ops.parametros_caso WHERE clave = ?", (clave,))
        cur.execute("INSERT INTO ops.parametros_caso (clave, valor) VALUES (?, ?)", (clave, valor))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--solo-esquema", action="store_true", help="No carga datos de prueba.")
    ap.add_argument("--solo-checkpoints", action="store_true",
                    help="Solo crea las tablas lg.* del checkpointer (no toca el esquema ops ni sus datos).")
    ap.add_argument("--limpiar-demo", action="store_true",
                    help="Borra liberaciones e hilos/checkpoints de demos anteriores (no toca clientes, stock ni ventas).")
    args = ap.parse_args()

    with conexion(autocommit=True) as conn:
        cur = conn.cursor()
        if args.limpiar_demo:
            cur.execute("DELETE FROM ops.liberaciones")
            cur.execute("DELETE FROM lg.writes")
            cur.execute("DELETE FROM lg.checkpoints")
            print("Demo limpia: liberaciones y checkpoints borrados.")
            return
            ejecutar_archivo(cur, "04_checkpoints.sql")
            print("Tablas del checkpointer (lg.checkpoints, lg.writes) listas.")
            return
        ejecutar_archivo(cur, "01_schema.sql")
        ejecutar_archivo(cur, "04_checkpoints.sql")
        print("Esquema ops creado y tablas del checkpointer (lg) verificadas.")
        if not args.solo_esquema:
            ejecutar_archivo(cur, "02_seed.sql")
            aplicar_semilla(cur)
            print("Datos de prueba cargados y parámetros de la semilla aplicados:")
            imprimir_parametros()


if __name__ == "__main__":
    main()
