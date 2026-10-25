"""Parámetros del caso derivados de la semilla. Misma semilla => mismo escenario."""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass

CASO_ID = "CRE-001"
VARIANTE = "D · Crédito"
SEMILLA = 7885

CLIENTE_CASO = "C-1003"
SKU_CASO = "EDGE-ORIN"
CANTIDAD_CASO = 12
SOLICITUD_CASO = (
    "C-1003 solicita liberar la venta de 12 EDGE-ORIN para un proyecto industrial, "
    "con pago a crédito y entrega esta semana."
)


@dataclass(frozen=True)
class ParametrosCaso:
    limite_credito: float
    exposicion_actual: float
    monto_revision: float
    stock_edge_orin: int
    lead_time_dias: int


def generar_parametros(semilla: int = SEMILLA) -> ParametrosCaso:
    # Generador aislado: no toca el estado global de random.
    rng = random.Random(semilla)
    limite = float(rng.choice([40_000, 45_000, 50_000]))
    holgura = rng.randint(5_000, 15_000)  # < 22.200 (12 x 1.850): la línea de C-1003 siempre queda corta
    return ParametrosCaso(
        limite_credito=limite,
        exposicion_actual=limite - holgura,
        monto_revision=float(rng.choice([15_000, 20_000, 25_000])),
        stock_edge_orin=rng.randint(20, 60),
        lead_time_dias=rng.choice([3, 5, 7, 10]),
    )


def imprimir_parametros(p: ParametrosCaso | None = None) -> None:
    p = p or generar_parametros()
    print(f"[{CASO_ID}] variante={VARIANTE} semilla={SEMILLA}")
    for clave, valor in asdict(p).items():
        print(f"  {clave} = {valor}")
