"""Checkpointer de LangGraph sobre Azure SQL (tablas lg.checkpoints y lg.writes, ver sql/04_checkpoints.sql).

Una conexión por instancia, serializada con un lock (como SqliteSaver). Si la conexión se cae
(p. ej. Azure SQL serverless reanudando) se reabre y la operación se reintenta una vez.
"""
from __future__ import annotations

import json
import re
import threading
from collections.abc import Iterator, Sequence
from typing import Any, cast

import pyodbc
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
    get_checkpoint_metadata,
    writes_sort_key,
)
from langgraph.checkpoint.serde.base import SerializerProtocol

from .db import conectar
from .settings import Settings

_CLAVE_FILTRO = re.compile(r"^[a-zA-Z0-9_.-]+$")
_COLUMNAS_CP = "thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, type, [checkpoint], metadata"
_SQL_WRITES = (
    "SELECT task_id, channel, type, value, task_path, idx FROM lg.writes "
    "WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?"
)


def construir_where(
    config: RunnableConfig | None, filtro: dict[str, Any] | None, antes: RunnableConfig | None
) -> tuple[str, list[Any]]:
    """WHERE parametrizado. Las claves del filtro se validan (van dentro de la ruta JSON, no se parametrizan)."""
    condiciones: list[str] = []
    params: list[Any] = []
    if config is not None:
        condiciones.append("thread_id = ?")
        params.append(str(config["configurable"]["thread_id"]))
        ns = config["configurable"].get("checkpoint_ns")
        if ns is not None:
            condiciones.append("checkpoint_ns = ?")
            params.append(ns)
        if cid := get_checkpoint_id(config):
            condiciones.append("checkpoint_id = ?")
            params.append(cid)
    for clave, valor in (filtro or {}).items():
        if not _CLAVE_FILTRO.match(clave):
            raise ValueError(f"Clave de filtro inválida: {clave!r}")
        if valor is None:
            condiciones.append(f"JSON_VALUE(metadata, '$.{clave}') IS NULL")
        elif isinstance(valor, (dict, list)):
            condiciones.append(f"JSON_QUERY(metadata, '$.{clave}') = ?")
            params.append(json.dumps(valor, ensure_ascii=False))
        else:
            condiciones.append(f"JSON_VALUE(metadata, '$.{clave}') = ?")
            params.append(json.dumps(valor) if isinstance(valor, bool) else str(valor))
    if antes is not None:
        condiciones.append("checkpoint_id < ?")
        params.append(get_checkpoint_id(antes))
    return ("WHERE " + " AND ".join(condiciones) if condiciones else ""), params


class AzureSqlSaver(BaseCheckpointSaver[str]):
    def __init__(self, settings: Settings | None = None, *, serde: SerializerProtocol | None = None):
        super().__init__(serde=serde)
        self._settings = settings
        self._conn: pyodbc.Connection | None = None
        self._lock = threading.RLock()

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def _ejecutar(self, operacion):
        """Ejecuta operacion(cursor) en una transacción; reabre la conexión si falló la conectividad."""
        with self._lock:
            for intento in (1, 2):
                try:
                    if self._conn is None:
                        self._conn = conectar(self._settings, autocommit=False)
                    cur = self._conn.cursor()
                    try:
                        resultado = operacion(cur)
                        self._conn.commit()
                        return resultado
                    finally:
                        cur.close()
                except (pyodbc.OperationalError, pyodbc.InterfaceError):
                    self.close()
                    if intento == 2:
                        raise
                except Exception:
                    if self._conn is not None:
                        self._conn.rollback()
                    raise

    @staticmethod
    def _upsert(cur: pyodbc.Cursor, tabla: str, claves: dict[str, Any], valores: dict[str, Any]) -> None:
        asignaciones = ", ".join(f"[{c}] = ?" for c in valores)
        donde = " AND ".join(f"[{c}] = ?" for c in claves)
        cur.execute(
            f"UPDATE {tabla} WITH (UPDLOCK, SERIALIZABLE) SET {asignaciones} WHERE {donde}",
            (*valores.values(), *claves.values()),
        )
        if cur.rowcount == 0:
            columnas = {**claves, **valores}
            cur.execute(
                f"INSERT INTO {tabla} ({', '.join(f'[{c}]' for c in columnas)}) "
                f"VALUES ({', '.join('?' * len(columnas))})",
                tuple(columnas.values()),
            )

    def _writes(self, cur: pyodbc.Cursor, thread_id: str, ns: str, checkpoint_id: str) -> list[tuple[str, str, Any]]:
        filas = cur.execute(_SQL_WRITES, (thread_id, ns, checkpoint_id)).fetchall()
        return [
            (task_id, canal, self.serde.loads_typed((tipo, bytes(valor) if valor is not None else b"")))
            for task_id, canal, tipo, valor, _ruta, _idx in sorted(
                filas, key=lambda r: writes_sort_key(r[4], r[0], r[5])
            )
        ]

    def _tupla(self, fila: Any, writes: list[tuple[str, str, Any]]) -> CheckpointTuple:
        thread_id, ns, checkpoint_id, padre, tipo, checkpoint, metadata = fila
        return CheckpointTuple(
            {"configurable": {"thread_id": thread_id, "checkpoint_ns": ns, "checkpoint_id": checkpoint_id}},
            self.serde.loads_typed((tipo, bytes(checkpoint))),
            cast(CheckpointMetadata, json.loads(metadata) if metadata else {}),
            {"configurable": {"thread_id": thread_id, "checkpoint_ns": ns, "checkpoint_id": padre}} if padre else None,
            writes,
        )

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        thread_id = str(config["configurable"]["thread_id"])
        ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = get_checkpoint_id(config)

        def op(cur: pyodbc.Cursor) -> CheckpointTuple | None:
            if checkpoint_id:
                fila = cur.execute(
                    f"SELECT {_COLUMNAS_CP} FROM lg.checkpoints "
                    "WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?",
                    (thread_id, ns, checkpoint_id),
                ).fetchone()
            else:
                fila = cur.execute(
                    f"SELECT TOP (1) {_COLUMNAS_CP} FROM lg.checkpoints "
                    "WHERE thread_id = ? AND checkpoint_ns = ? ORDER BY checkpoint_id DESC",
                    (thread_id, ns),
                ).fetchone()
            return self._tupla(fila, self._writes(cur, fila[0], fila[1], fila[2])) if fila else None

        return self._ejecutar(op)

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        donde, params = construir_where(config, filter, before)
        top = "TOP (?) " if limit is not None else ""
        if limit is not None:
            params = [int(limit), *params]

        def op(cur: pyodbc.Cursor) -> list[CheckpointTuple]:
            filas = cur.execute(
                f"SELECT {top}{_COLUMNAS_CP} FROM lg.checkpoints {donde} ORDER BY checkpoint_id DESC", params
            ).fetchall()  # se materializa antes de consultar writes: sin MARS no hay cursores simultáneos
            return [self._tupla(f, self._writes(cur, f[0], f[1], f[2])) for f in filas]

        yield from self._ejecutar(op)

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        thread_id = str(config["configurable"]["thread_id"])
        ns = config["configurable"]["checkpoint_ns"]
        tipo, serializado = self.serde.dumps_typed(checkpoint)
        meta = json.dumps(get_checkpoint_metadata(config, metadata), ensure_ascii=False)

        def op(cur: pyodbc.Cursor) -> None:
            self._upsert(
                cur,
                "lg.checkpoints",
                {"thread_id": thread_id, "checkpoint_ns": ns, "checkpoint_id": checkpoint["id"]},
                {
                    "parent_checkpoint_id": config["configurable"].get("checkpoint_id"),
                    "type": tipo,
                    "checkpoint": serializado,
                    "metadata": meta,
                },
            )

        self._ejecutar(op)
        return {"configurable": {"thread_id": thread_id, "checkpoint_ns": ns, "checkpoint_id": checkpoint["id"]}}

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        thread_id = str(config["configurable"]["thread_id"])
        ns = str(config["configurable"]["checkpoint_ns"])
        checkpoint_id = str(config["configurable"]["checkpoint_id"])
        reemplazar = all(canal in WRITES_IDX_MAP for canal, _ in writes)

        def op(cur: pyodbc.Cursor) -> None:
            for idx, (canal, valor) in enumerate(writes):
                tipo, serializado = self.serde.dumps_typed(valor)
                claves = {
                    "thread_id": thread_id, "checkpoint_ns": ns, "checkpoint_id": checkpoint_id,
                    "task_id": task_id, "idx": WRITES_IDX_MAP.get(canal, idx),
                }
                valores = {"task_path": task_path, "channel": canal, "type": tipo, "value": serializado}
                if reemplazar:
                    self._upsert(cur, "lg.writes", claves, valores)
                    continue
                existe = cur.execute(
                    "SELECT 1 FROM lg.writes WITH (UPDLOCK, SERIALIZABLE) WHERE "
                    + " AND ".join(f"[{c}] = ?" for c in claves),
                    tuple(claves.values()),
                ).fetchone()
                if not existe:
                    columnas = {**claves, **valores}
                    cur.execute(
                        f"INSERT INTO lg.writes ({', '.join(f'[{c}]' for c in columnas)}) "
                        f"VALUES ({', '.join('?' * len(columnas))})",
                        tuple(columnas.values()),
                    )

        self._ejecutar(op)

    def delete_thread(self, thread_id: str) -> None:
        def op(cur: pyodbc.Cursor) -> None:
            cur.execute("DELETE FROM lg.writes WHERE thread_id = ?", (str(thread_id),))
            cur.execute("DELETE FROM lg.checkpoints WHERE thread_id = ?", (str(thread_id),))

        self._ejecutar(op)

    def get_next_version(self, current: str | None, channel: None) -> str:
        import random

        actual = 0 if current is None else int(str(current).split(".")[0])
        return f"{actual + 1:032}.{random.random():016}"
