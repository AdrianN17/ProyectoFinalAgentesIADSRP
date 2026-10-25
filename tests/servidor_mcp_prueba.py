"""Servidor MCP stdio de PRUEBA: el mismo servidor real (andes_agent.mcp_server) con un repositorio en memoria.

Solo lo usan los tests; permite probar stdio real sin Azure SQL.
"""
from andes_agent import mcp_server


class RepoEnMemoria:
    def consultar_stock(self, sku):
        if sku != "EDGE-ORIN":
            return {"encontrado": False, "sku": sku}
        return {"encontrado": True, "sku": sku, "nombre": "Gateway", "precio_unitario": 1850.0,
                "lead_time_dias": 3, "stock_disponible": 33, "fuente": "memoria:ops.v_stock"}

    def consultar_estado_credito(self, cliente_id):
        if cliente_id != "C-1003":
            return {"encontrado": False, "cliente_id": cliente_id}
        return {"encontrado": True, "cliente_id": cliente_id, "nombre": "Industrias", "estado_credito": "activo",
                "limite_credito": 40000.0, "exposicion_actual": 34092.0, "credito_disponible": 5908.0,
                "plazo_dias": 45, "fuente": "memoria:ops.v_estado_credito"}

    def consultar_historial_ventas(self, cliente_id, limite=5):
        return {"encontrado": True, "cliente_id": cliente_id, "ultimas_ventas": [],
                "resumen_pagos": {"pagos_vencidos": 0, "monto_vencido": 0}, "fuente": "memoria:ventas"}

    def consultar_parametros_credito(self):
        return {"monto_revision": 20000.0, "fuente": "memoria:ops.parametros_caso"}


if __name__ == "__main__":
    mcp_server._repo = RepoEnMemoria()
    mcp_server.main()
