# USO_IA.md · CRE-001 (Crédito) · semilla 7885

Autor: Adrian Norvic Melgarejo Siguas · Módulo 3 · AI Engineer (DSRP)

Usé IA como copiloto de desarrollo. Aquí declaro qué usé, qué me generó, qué decidí yo, dónde se equivocó y cómo lo validé antes de confiar en ella.

## 1. Herramientas usadas

| Herramienta | Para qué la usé |
|---|---|
| Asistente de IA agéntico en VS Code (GitHub Copilot) | Revisar mi diagrama de arquitectura, generar y corregir el código, los scripts SQL, las pruebas y la documentación, y ejecutar comandos de validación. |
| Azure AI Foundry · `gpt-5-mini` y `text-embedding-3-small` | **No** son mi copiloto: son modelos que usa el sistema en tiempo de ejecución (redactor, router con baja confianza y embeddings del RAG). |
| Azure SQL, Qdrant Cloud, `uv`, `conda`, `pytest`, `az` CLI | Infraestructura y herramientas para construir y verificar el proyecto. |

## 2. Tres prompts representativos (textuales)

1. *"revisa mi diagrama de arquitectura, luego creame el codigo en python, enfocate a azure y foundry porfavor, crea los esquemas de bd y la data de prueba para azuresql, tambien usare qdrant"*
2. *"No uses sqlite, usa azure sql"*
3. *"Revisa este pdf, creame un checklist.md y con ese checklist valida si cumplo todo, adicional, crea otro md para realizar yo las ejecuciones por consola porfavor, esto para hacerlo en mi expocision"*

Después pedí *"Puedes agregar lo que falta del checklist"* y *"ejecuta todos los casos, quiero validar que qdrant, azure sql y la api de openai funcionen"*.

## 3. Qué generó o sugirió la IA

- El código de `src/andes_agent/`: reglas, parser, router híbrido, RAG sobre Qdrant, acceso a Azure SQL, cliente de Foundry, grafo de LangGraph, servidor y cliente MCP, y el CLI.
- Los scripts `sql/01_schema.sql`, `02_seed.sql`, `03_permisos.sql` y `04_checkpoints.sql`, y el checkpointer `AzureSqlSaver`.
- Las pruebas de `tests/`, el `README.md`, `CHECKLIST.md`, `GUIA_EXPOSICION.md`, la carpeta `docs/` y la redacción inicial de `HITOS.md`, `DECISIONES.md`, `EVIDENCIAS.md` y este archivo, que luego completé en primera persona.
- Una revisión de mi diagrama con 5 observaciones: la ruta sin excepción no registraba la liberación, el camino de escritura quedaba fuera de MCP, el monto de revisión no tenía fuente, el stock insuficiente no debía ir a Finanzas, y el checkpoint no debía vivir en un archivo local.

## 4. Qué decidí y modifiqué yo

- **Definí el stack:** Azure SQL, Azure AI Foundry y Qdrant, y aporté los recursos reales (servidor y base de Azure SQL, el recurso `azfnd01` con sus deployments, el cluster de Qdrant) y sus credenciales en mi `.env`.
- **Cambié una decisión de diseño:** el asistente planteó el checkpoint en SQLite; yo pedí pasarlo a Azure SQL para que todo quede en Azure.
- **Corregí mi configuración** cuando falló: el endpoint de Foundry (usé el del recurso y no el del proyecto) y la API key de Qdrant, que daba 403.
- **Pedí validar contra servicios reales**, no solo con pruebas: ejecutar todos los casos para comprobar Azure SQL, Qdrant y Foundry.
- **Los cambios de código los hizo el asistente** a partir de mis pedidos y de los fallos que encontramos al ejecutar. Yo los revisé en las ejecuciones, en las pruebas y en `DECISIONES.md`, para poder explicarlos en el video.

## 5. Una sugerencia rechazada y por qué

- **Checkpointer SQLite (`SqliteSaver`).** El asistente lo usó por simplicidad: un archivo local, sin infraestructura. Lo rechacé con *"No uses sqlite, usa azure sql"*. La razón técnica es que un archivo local no sirve si el agente corre en varias instancias o en contenedores efímeros: el estado de un hilo pausado se perdería y no podría reanudar. El resultado fue `AzureSqlSaver` (decisión D5 en `DECISIONES.md`).

## 6. Errores de la IA que detecté

| # | Error de la IA | Cómo se detectó | Corrección |
|---|---|---|---|
| 1 | Usó `checkpoint` como nombre de columna en `04_checkpoints.sql`, que es palabra reservada de T-SQL | Al ejecutar el script en mi Azure SQL: `Incorrect syntax near 'checkpoint'` | `[checkpoint]` en el SQL y en las consultas dinámicas |
| 2 | Dejó `mcp>=1.10` sin tope: un `uv sync` limpio instala mcp 2.x y el servidor no arranca | `uv run andes-mcp-cliente` falló con `No module named 'mcp.server.fastmcp'` | `mcp>=1.10,<2` y `uv.lock` regenerado |
| 3 | Asumió el deployment `gpt-4o-mini` y `temperature=0` | Error 404 `DeploymentNotFound`; luego el modelo de razonamiento rechazó `temperature` | Deployment `gpt-5-mini` (comprobado con `az`) y sin `temperature` |
| 4 | El router tenía reglas "seguras y equivocadas" y le faltaban verbos | Al probar frases nuevas (`EVIDENCIAS.md` §3) | Reordenar reglas, ampliar verbos y pruebas de regresión |
| 5 | `ejecutar` permitía reutilizar un `id_hilo` y mezclaba estados | Trazas y advertencias duplicadas en una corrida real | `ejecutar` rechaza hilos existentes |
| 6 | El redactor con LLM en texto libre omitió la aprobación en la respuesta ("Decisión: excepción") | Al ejecutar `reanudar` en una corrida real | Salida estructurada validada por código (D8); 30/30 respuestas aceptadas con el modelo real |

Varios de estos errores (1, 3 y el 403 de Qdrant) solo aparecieron al ejecutar contra los servicios reales; las pruebas con simulaciones no los habrían detectado.

## 7. Cómo validé antes de confiar

- **Pruebas automáticas:** `uv run pytest` (77 pruebas), con una prueba de regresión por cada error corregido.
- **Ejecución real:** corrí cada pieza contra Azure SQL, Foundry y Qdrant (`EVIDENCIAS.md` §4–7), incluida la pausa y reanudación con el mismo `id_hilo`.
- **Verificación independiente:** `az cognitiveservices account deployment list` para los deployments, consultas SQL directas para comprobar liberaciones y checkpoints, y un escaneo para confirmar que ningún secreto de mi `.env` aparece en el código ni en el repositorio.
- **Lectura de las reglas de negocio:** la decisión de crédito está en `reglas.py` (determinista). El LLM no controla ramas críticas: solo enruta con validación posterior y redacta.
- **Comprensión:** repasé el `CHECKLIST.md` contra el PDF y preparé `GUIA_EXPOSICION.md` con respuestas a las preguntas de control para poder explicar el sistema en el video.
