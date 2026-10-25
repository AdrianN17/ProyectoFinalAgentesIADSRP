from andes_agent.fuentes import DbFuentes, FuentesConFallos, McpFuentes


def test_cada_fuente_declara_su_canal_de_acceso():
    assert "sin MCP" in DbFuentes(repo=None).via
    assert "MCP" in McpFuentes.via and "stdio" in McpFuentes.via


def test_el_envoltorio_de_fallos_conserva_el_canal_real():
    assert FuentesConFallos(DbFuentes(repo=None), fallos=1).via == DbFuentes.via
    assert FuentesConFallos(McpFuentes(), fallos=1).via == McpFuentes.via
