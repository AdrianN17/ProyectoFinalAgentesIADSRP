"""Cliente MCP puro (sin LLM): list_tools + call_tool + read_resource."""
from __future__ import annotations

import asyncio
import json

from .mcp_client import leer_recurso, listar_herramientas, llamar_herramientas


async def _demo() -> None:
    print("== list_tools ==")
    for t in await listar_herramientas():
        print(f"- {t['nombre']}: {t['descripcion']}")

    print("\n== call_tool ==")
    stock, credito = await llamar_herramientas(
        [("consultar_stock", {"sku": "EDGE-ORIN"}), ("consultar_estado_credito", {"cliente_id": "C-1003"})]
    )
    print(json.dumps(stock, ensure_ascii=False, indent=2))
    print(json.dumps(credito, ensure_ascii=False, indent=2))

    print("\n== resource politica://credito ==")
    print((await leer_recurso("politica://credito"))[:400], "...")


def main() -> None:
    asyncio.run(_demo())


if __name__ == "__main__":
    main()
