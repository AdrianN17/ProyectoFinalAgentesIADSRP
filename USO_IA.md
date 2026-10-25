# USO_IA.md · CRE-001 (Crédito) · semilla 7885

> **Borrador para que lo valides y lo completes.** Los hechos de abajo (prompts, qué generó la IA, errores detectados, cómo se validó) salen de la conversación y las ejecuciones reales. Los puntos marcados con ✍️ dependen de lo que **tú** hiciste o decidiste: complétalos con tus palabras. El PDF exige que esto coincida con la evidencia; no lo entregues sin revisarlo.

## 1. Herramientas usadas

| Herramienta | Para qué |
|---|---|
| Asistente de IA agéntico en VS Code (GitHub Copilot) | Revisar la arquitectura, generar y corregir el código, los scripts SQL, las pruebas y la documentación; ejecutar comandos de validación. |
| Azure AI Foundry · `gpt-5-mini` y `text-embedding-3-small` | **No** es copiloto de desarrollo: son modelos que usa el sistema en tiempo de ejecución (redactor, router con baja confianza y embeddings del RAG). |
| Azure SQL, Qdrant Cloud, `uv`, `conda`, `pytest`, `az` CLI | Infraestructura y herramientas de desarrollo y verificación. |

## 2. Tres prompts representativos (textuales)

1. *"revisa mi diagrama de arquitectura, luego creame el codigo en python, enfocate a azure y foundry porfavor, crea los esquemas de bd y la data de prueba para azuresql, tambien usare qdrant"*
2. *"No uses sqlite, usa azure sql"*
3. *"Revisa este pdf, creame un checklist.md y con ese checklist valida si cumplo todo, adicional, crea otro md para realizar yo las ejecuciones por consola porfavor, esto para hacerlo en mi expocision"*

(Seguimiento: *"Puedes agregar lo que falta del checklist"* → tests faltantes, documentos y repositorio git.)

## 3. Qué generó o sugirió la IA

- Código en `src/andes_agent/`: reglas, parser, router híbrido, RAG sobre Qdrant, acceso a Azure SQL, cliente Foundry, grafo LangGraph, servidor y cliente MCP, CLI.
- `sql/01_schema.sql`, `02_seed.sql`, `03_permisos.sql`, `04_checkpoints.sql` y el checkpointer `AzureSqlSaver`.
- Pruebas (`tests/`), `README.md`, `CHECKLIST.md`, `GUIA_EXPOSICION.md`, `docs/`, y borradores de `HITOS.md`, `DECISIONES.md`, `EVIDENCIAS.md` y este archivo.
- Una revisión del diagrama inicial con 5 observaciones (ruta sin excepción sin registrar liberación, camino de escritura fuera de MCP, falta de fuente del monto de revisión, stock insuficiente sin HITL, persistencia del checkpoint).

## 4. Qué modificó el estudiante

Hechos conocidos:
- Definiste el stack (Azure SQL, Azure AI Foundry, Qdrant) y aportaste los recursos reales: servidor y base de Azure SQL, recurso `azfnd01` con los deployments, cluster de Qdrant, y las credenciales en tu `.env`.
- Renovaste la API key de Qdrant cuando el RAG fallaba con 403.
- Decidiste cambiar el checkpointer de SQLite a Azure SQL.

✍️ **Completa tú:** cambios que hiciste directamente en el código, en los datos o en las reglas (por ejemplo, ajustes a políticas, parámetros, nombres de deployments o textos), y qué entendiste antes de aceptarlos.

## 5. Una sugerencia rechazada y por qué

- **Checkpointer SQLite (`SqliteSaver`).** La IA lo propuso por simplicidad (archivo local, sin infraestructura) y porque el diseño original lo mencionaba. Lo rechazaste con *"No uses sqlite, usa azure sql"*. Razón técnica: un archivo local no sirve si el agente corre en varias instancias o en contenedores efímeros, y el estado pausado se perdería. Resultado: `AzureSqlSaver` (D5 en `DECISIONES.md`).
- ✍️ Añade otra si la hubo (por ejemplo, el comando de diagnóstico del entorno que no autorizaste al inicio) y por qué la rechazaste.

## 6. Errores de la IA detectados

| # | Error de la IA | Cómo se detectó | Corrección |
|---|---|---|---|
| 1 | Columna `checkpoint` en `04_checkpoints.sql`: palabra reservada de T-SQL | Al ejecutar el script en Azure SQL (`Incorrect syntax near 'checkpoint'`) | `[checkpoint]` en SQL y en consultas dinámicas |
| 2 | `mcp>=1.10` sin tope: un `uv sync` limpio instala mcp 2.x y rompe el servidor | `uv run andes-mcp-cliente` falló con `No module named 'mcp.server.fastmcp'` | `mcp>=1.10,<2` y `uv.lock` |
| 3 | Asumió el deployment `gpt-4o-mini` y `temperature=0` | Error 404 `DeploymentNotFound` y luego el rechazo de `temperature` por un modelo de razonamiento | Deployment `gpt-5-mini` (verificado con `az`) y sin `temperature` |
| 4 | Router con reglas "seguras y equivocadas" y verbos incompletos | Al probar frases nuevas (EVIDENCIAS §3) | Reordenar reglas, ampliar verbos y pruebas de regresión |
| 5 | `ejecutar` permitía reutilizar un `id_hilo` y mezclaba estados | Trazas y advertencias duplicadas en una corrida real | Rechazar hilos existentes |

## 7. Cómo se validó antes de confiar

- **Pruebas automáticas:** `uv run pytest` (55 pruebas) y regresiones para cada error corregido.
- **Ejecución real:** cada pieza se ejecutó contra Azure SQL, Foundry y Qdrant, no solo con simulaciones (EVIDENCIAS §4–7).
- **Verificación independiente:** `az cognitiveservices account deployment list` para los deployments; consultas SQL directas para comprobar liberaciones y checkpoints; escaneo para confirmar que ningún secreto del `.env` aparece en el código.
- **Lectura del código y de las reglas:** las decisiones de negocio están en `reglas.py` (determinista); el LLM no controla ramas críticas.
- ✍️ **Completa tú:** qué revisaste personalmente y qué pudiste explicar sin ayuda (para el video).
