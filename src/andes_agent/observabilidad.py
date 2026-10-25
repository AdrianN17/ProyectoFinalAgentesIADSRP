"""Telemetría opcional hacia Azure Monitor / Application Insights (extra 'monitor')."""
from __future__ import annotations

import os


def iniciar() -> bool:
    cadena = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    if not cadena:
        return False
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
    except ImportError:
        print("Instala el extra: pip install '.[monitor]'")
        return False
    configure_azure_monitor(connection_string=cadena)
    return True
