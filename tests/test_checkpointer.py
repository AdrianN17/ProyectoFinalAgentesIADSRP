import re
import sqlite3

import pytest
from langgraph.types import Command

from andes_agent import checkpointer as cp_mod
from andes_agent.checkpointer import AzureSqlSaver, construir_where
from andes_agent.config_caso import SOLICITUD_CASO
from andes_agent.graph import construir_grafo
from test_grafo import cfg as cfg_hilo, entorno  # noqa: F401  (fixture reutilizada)


class _CursorFalso:
    """Traduce el T-SQL mínimo del saver a SQLite. Valida la lógica, no la sintaxis T-SQL."""

    def __init__(self, cur):
        self._cur = cur

    def execute(self, sql, params=()):
        sql = re.sub(r"\s+WITH \(UPDLOCK, SERIALIZABLE\)", "", sql)
        sql = re.sub(r"SELECT TOP \(1\) (.*) ORDER BY (.*)$", r"SELECT \1 ORDER BY \2 LIMIT 1", sql)
        self._cur.execute(sql, tuple(params))
        return self

    rowcount = property(lambda self: self._cur.rowcount)
    fetchone = lambda self: self._cur.fetchone()  # noqa: E731
    fetchall = lambda self: self._cur.fetchall()  # noqa: E731
    close = lambda self: None  # noqa: E731


class _ConexionFalsa:
    def __init__(self, db):
        self.db = db

    cursor = lambda self: _CursorFalso(self.db.cursor())  # noqa: E731
    commit = lambda self: self.db.commit()  # noqa: E731
    rollback = lambda self: self.db.rollback()  # noqa: E731
    close = lambda self: None  # noqa: E731


@pytest.fixture
def sqlserver_falso(monkeypatch, tmp_path):
    ruta = tmp_path / "falso.db"
    db = sqlite3.connect(ruta, check_same_thread=False)
    db.execute("ATTACH DATABASE ? AS lg", (str(tmp_path / "lg.db"),))
    db.executescript(
        """
        CREATE TABLE lg.checkpoints (thread_id TEXT, checkpoint_ns TEXT, checkpoint_id TEXT, parent_checkpoint_id TEXT,
            type TEXT, [checkpoint] BLOB, metadata TEXT, PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id));
        CREATE TABLE lg.writes (thread_id TEXT, checkpoint_ns TEXT, checkpoint_id TEXT, task_id TEXT, task_path TEXT,
            idx INTEGER, channel TEXT, type TEXT, value BLOB,
            PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx));
        """
    )
    monkeypatch.setattr(cp_mod, "conectar", lambda s=None, autocommit=False: _ConexionFalsa(db))
    return db


def test_pausa_y_reanuda_con_otra_instancia_del_saver(entorno, sqlserver_falso):  # noqa: F811
    deps, _, reg, rapido = entorno
    r = construir_grafo(deps, AzureSqlSaver(), rapido).invoke(
        {"solicitud": SOLICITUD_CASO, "id_hilo": "P1"}, cfg_hilo("P1"))
    assert "__interrupt__" in r and reg.filas == {}

    # Otra instancia = otro proceso (`andes-demo reanudar`): el estado solo está en la base de datos.
    g2 = construir_grafo(deps, AzureSqlSaver(), rapido)
    assert g2.get_state(cfg_hilo("P1")).next == ("aprobacion_humana",)
    assert g2.get_state(cfg_hilo("OTRO")).next == ()
    r = g2.invoke(Command(resume={"aprobado": True, "aprobador": "Ana"}), cfg_hilo("P1"))
    assert "liberada tras aprobación de Ana" in r["respuesta"] and list(reg.filas) == ["P1"]
    assert g2.get_state(cfg_hilo("P1")).next == ()


def test_historial_y_borrado_de_hilo(entorno, sqlserver_falso):  # noqa: F811
    deps, _, _, rapido = entorno
    saver = AzureSqlSaver()
    g = construir_grafo(deps, saver, rapido)
    g.invoke({"solicitud": SOLICITUD_CASO, "id_hilo": "P2"}, cfg_hilo("P2"))
    ids = [t.config["configurable"]["checkpoint_id"] for t in saver.list(cfg_hilo("P2"))]
    assert len(ids) >= 3 and ids == sorted(ids, reverse=True)
    saver.delete_thread("P2")
    assert list(saver.list(cfg_hilo("P2"))) == []
    assert saver.get_tuple(cfg_hilo("P2")) is None


def cfg(**extra):
    return {"configurable": {"thread_id": "H1", "checkpoint_ns": "", **extra}}


def test_where_por_hilo_y_ns():
    donde, params = construir_where(cfg(), None, None)
    assert donde == "WHERE thread_id = ? AND checkpoint_ns = ?"
    assert params == ["H1", ""]


def test_where_con_checkpoint_y_before():
    donde, params = construir_where(cfg(checkpoint_id="c1"), None, {"configurable": {"checkpoint_id": "c0"}})
    assert donde.endswith("checkpoint_id = ? AND checkpoint_id < ?")
    assert params == ["H1", "", "c1", "c0"]


def test_where_filtro_de_metadata_parametrizado():
    donde, params = construir_where(None, {"source": "loop", "step": 2, "flag": True, "x": None}, None)
    assert "JSON_VALUE(metadata, '$.source') = ?" in donde
    assert "JSON_VALUE(metadata, '$.x') IS NULL" in donde
    assert params == ["loop", "2", "true"]


def test_where_rechaza_claves_de_filtro_peligrosas():
    with pytest.raises(ValueError):
        construir_where(None, {"a') OR 1=1 --": 1}, None)


def test_sin_filtros_no_hay_where():
    assert construir_where(None, None, None) == ("", [])
