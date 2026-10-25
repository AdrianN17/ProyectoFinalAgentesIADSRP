"""Errores del dominio. Solo FalloTransitorio es reintentable."""

MARCA_TRANSITORIO = "FALLO_TRANSITORIO"


class FalloTransitorio(Exception):
    """Fallo técnico recuperable (red, Azure SQL en pausa, timeout). Único error con RetryPolicy."""

    def __init__(self, detalle: str = ""):
        super().__init__(f"{MARCA_TRANSITORIO}: {detalle}")


class ErrorHerramienta(Exception):
    """Error devuelto por una tool MCP (entrada inválida, etc.). No se reintenta."""


class ErrorConfiguracion(Exception):
    """Falta configuración necesaria (variable de entorno)."""
