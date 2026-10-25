"""CLI del agente. Dos comandos para mostrar pausa y reanudación con el MISMO id_hilo:

  andes-demo ejecutar --hilo H1 "C-1003 solicita liberar la venta de 12 EDGE-ORIN ..."
  andes-demo reanudar --hilo H1 --decision aprobar --aprobador "Finanzas"
"""
from __future__ import annotations

import argparse
import json

from langgraph.types import Command

from . import observabilidad
from .checkpointer import AzureSqlSaver
from .config_caso import SOLICITUD_CASO, imprimir_parametros
from .db import Repositorio
from .foundry import ClienteFoundry
from .fuentes import DbFuentes, FuentesConFallos, McpFuentes
from .graph import Dependencias, construir_grafo
from .rag import RepositorioPoliticas, crear_embedder, crear_qdrant
from .redactor import Redactor
from .router import Router
from .settings import get_settings


def _construir(directo: bool, checkpointer):
    s = get_settings()
    repo = Repositorio(s)
    fuentes = DbFuentes(repo) if directo else McpFuentes()
    if s.simular_fallos:
        fuentes = FuentesConFallos(fuentes, s.simular_fallos)
    llm = ClienteFoundry(s) if s.use_llm else None
    deps = Dependencias(
        fuentes=fuentes,
        politicas=RepositorioPoliticas(crear_qdrant(s), crear_embedder(s), s.qdrant_collection),
        registrador=repo,
        router=Router(llm),
        redactor=Redactor(llm),
    )
    return construir_grafo(deps, checkpointer)


def _correr(grafo, entrada, config, progreso: bool = True) -> dict:
    """Ejecuta el grafo con stream: LangGraph emite un evento cada vez que termina un nodo."""
    paso = 0
    for evento in grafo.stream(entrada, config, stream_mode="updates"):
        for nodo, cambios in evento.items():
            if nodo == "__interrupt__":
                if progreso:
                    print("  [PAUSA] aprobacion_humana -> interrupt(): el flujo se detiene y el estado queda guardado")
                continue
            paso += 1
            if progreso:
                detalle = (cambios or {}).get("traza", [""])[0] if isinstance(cambios, dict) else ""
                print(f"  [paso {paso}] nodo '{nodo}' terminado · {detalle}")
    estado = grafo.get_state(config)
    if estado.next:  # sigue pendiente un nodo: el grafo quedó pausado en un interrupt()
        return {"__interrupt__": estado.tasks[0].interrupts}
    return dict(estado.values)


def _mostrar(resultado: dict, hilo: str) -> None:
    if "__interrupt__" in resultado:
        print(f"\n== FLUJO PAUSADO · id_hilo={hilo} · esperando a Finanzas/Crédito ==")
        print(json.dumps(resultado["__interrupt__"][0].value, ensure_ascii=False, indent=2))
        print(f'\nReanudar: andes-demo reanudar --hilo {hilo} --decision aprobar|rechazar --aprobador "<nombre>"')
    else:
        print(f"\n== RESPUESTA · id_hilo={hilo} ==\n{resultado['respuesta']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ej = sub.add_parser("ejecutar")
    ej.add_argument("solicitud", nargs="?", default=SOLICITUD_CASO)
    ej.add_argument("--hilo", required=True)
    re_ = sub.add_parser("reanudar")
    re_.add_argument("--hilo", required=True)
    re_.add_argument("--decision", choices=["aprobar", "rechazar"], required=True)
    re_.add_argument("--aprobador", default="Finanzas/Crédito")
    re_.add_argument("--comentario", default="")
    for p in (ej, re_):
        p.add_argument("--directo", action="store_true", help="Consulta Azure SQL sin pasar por MCP.")
        p.add_argument("--sin-progreso", action="store_true", help="No imprime el recorrido nodo por nodo.")
    args = ap.parse_args()

    observabilidad.iniciar()
    checkpointer = AzureSqlSaver(get_settings())
    try:
        grafo = _construir(args.directo, checkpointer)
        config = {"configurable": {"thread_id": args.hilo}}

        if args.cmd == "ejecutar":
            if grafo.get_state(config).values:
                raise SystemExit(
                    f"El hilo '{args.hilo}' ya existe. Usa otro --hilo para una solicitud nueva "
                    "o 'reanudar' si está pausado."
                )
            imprimir_parametros()
            print(f"\nRecorrido del grafo (hilo {args.hilo}):")
            resultado = _correr(grafo, {"solicitud": args.solicitud, "id_hilo": args.hilo}, config, not args.sin_progreso)
        else:
            if not grafo.get_state(config).next:
                raise SystemExit(f"El hilo '{args.hilo}' no está pausado (no existe o ya terminó).")
            print(f"\nReanudando el hilo {args.hilo} desde su checkpoint:")
            resultado = _correr(
                grafo,
                Command(resume={"aprobado": args.decision == "aprobar", "aprobador": args.aprobador,
                                "comentario": args.comentario}),
                config,
                not args.sin_progreso,
            )
        _mostrar(resultado, args.hilo)
    finally:
        checkpointer.close()


if __name__ == "__main__":
    main()
