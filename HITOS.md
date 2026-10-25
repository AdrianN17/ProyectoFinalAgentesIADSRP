# HITOS.md · CRE-001 (Crédito) · semilla 7885

Autor: Adrian Norvic Melgarejo Siguas · Módulo 3 · AI Engineer (DSRP)

Registro de los seis hitos. La evidencia detallada está en [EVIDENCIAS.md](./EVIDENCIAS.md) y las decisiones en [DECISIONES.md](./DECISIONES.md).

---

## Hito 1 · Separar responsabilidades

**Qué construí**
- `config_caso.py` con mi CASO_ID `CRE-001` y mi SEMILLA `7885`. La semilla fija 5 parámetros (límite de crédito, exposición, monto de revisión, stock de EDGE-ORIN y lead time) y se imprimen al iniciar cada demo.
- Los datos en Azure SQL (`sql/01_schema.sql` y `02_seed.sql`): 5 clientes (uno sano, uno con línea ajustada, el del caso, uno en hold y otro sano), 6 productos, inventario, 11 ventas y 11 pagos.
- 3 documentos de política en `data/politicas/` y las reglas objetivas en `reglas.py`, con pruebas.
- La tabla de 10 solicitudes en `docs/consulta_capacidad.md`.

**Qué falló**
- Nada bloqueante en este hito. Los problemas de T-SQL aparecieron después, al crear el checkpointer (Hito 4).

**Qué aprendí**
Entendí que las reglas de crédito (línea insuficiente, hold, monto de revisión) no necesitan un LLM: son comparaciones objetivas que deben ser funciones puras, reproducibles y fáciles de probar. Lo que cambia seguido (stock, exposición) tiene que vivir en la base de datos y no en un prompt. Las políticas son información documental, y los clientes, el inventario y las ventas son información transaccional.

**Qué decisión cambió después de probar**
Decidí aplicar la semilla también a los datos en Azure SQL y no solo a variables en memoria, para que SQL, las tools y las reglas vean el mismo escenario.

**Evidencia:** `docs/consulta_capacidad.md`; `tests/test_reglas.py` y `test_semilla_reproducible`; EVIDENCIAS §1.

---

## Hito 2 · Router + RAG + SQL + Tools

**Qué construí**
- Un router híbrido con 5 destinos (`RAG`, `SQL`, `TOOLS`, `CLARIFY`, `DIRECT`), con umbral de confianza 0.6 y validación de código sobre lo que sugiere el modelo.
- RAG sobre Qdrant con embeddings de Foundry (3 documentos, 12 fragmentos) que cita archivo y sección.
- SQL parametrizado (`db.py`) y 4 tools semánticas: `consultar_stock`, `consultar_estado_credito`, `consultar_historial_ventas` y `consultar_parametros_credito`.
- 14 casos de evaluación del router, 3 pruebas RAG, 4 de SQL y pruebas de tools y datos inválidos.

**Qué falló**
- El router se equivocó dos veces: una regla "segura y equivocada" (una pregunta de política que menciona un cliente iba a `TOOLS/credito` con confianza 0.85) y faltaban verbos como "necesita". Ver EVIDENCIAS §3.
- Qdrant respondía 403 por una API key inválida, y Foundry respondía 404 porque el deployment que se había asumido no existía.

**Qué aprendí**
Un router con reglas puede estar seguro y equivocado a la vez, así que hay que probarlo con frases que no escribí yo. Enviar toda pregunta a todas las herramientas costaría tiempo, dinero y riesgo; cuando la confianza es baja, lo correcto es pedir una aclaración y no adivinar. Una consulta de ventas históricas no se resuelve con RAG porque RAG recupera texto, no agrega filas.

**Qué decisión cambió después de probar**
Reordené las reglas para que una pregunta explícita de política gane aunque mencione un cliente, y agregué un umbral de similitud (0.35) en RAG para no citar fragmentos irrelevantes.

**Evidencia:** `tests/test_router.py`, `test_rag.py` y `test_sql.py`; EVIDENCIAS §3–4.

---

## Hito 3 · Workflow con estado

**Qué construí**
- Un grafo de LangGraph con 7 nodos y 4 *conditional edges*, y un State pequeño explicado campo por campo.
- Rutas que terminan directamente: saludo, aclaración, consultas informativas, datos inválidos, stock insuficiente y liberación automática.
- El diagrama y la explicación del State en `docs/workflow_state.md`.

**Qué falló**
- Al reutilizar un `id_hilo` en `ejecutar` se mezclaba el estado anterior: salían trazas y advertencias duplicadas, porque esos campos del State son acumulativos.

**Qué aprendí**
Un if/else no sobrevive a una pausa de horas ni a otro proceso: el flujo necesita un estado explícito y persistente. También entendí que el State debe ser pequeño y que los campos acumulativos se comportan distinto cuando se reutiliza un hilo.

**Qué decisión cambió después de probar**
`ejecutar` ahora rechaza un `id_hilo` que ya existe.

**Evidencia:** `docs/workflow_state.md`; `test_grafo.py` (ruta directa); EVIDENCIAS §5.

---

## Hito 4 · Retry, checkpoint y HITL

**Qué construí**
- `RetryPolicy` solo en `consultar_fuentes` y solo para `FalloTransitorio`.
- `AzureSqlSaver`: el checkpoint persistente en Azure SQL (`lg.checkpoints` y `lg.writes`).
- `interrupt()` ante hold, línea insuficiente o monto de revisión, con reanudación mediante `Command(resume=...)` y el mismo `id_hilo`, y una escritura de la liberación idempotente después del `interrupt()`.

**Qué falló**
- `checkpoint` es palabra reservada en T-SQL, y la creación de las tablas falló hasta usar `[checkpoint]`.
- El retry funcionaba, pero no dejaba evidencia visible.
- La primera versión guardaba el checkpoint en SQLite local.

**Qué aprendí**
Un timeout o una conexión caída merecen retry porque pueden resolverse solos; un cliente en hold no mejora reintentando. Los side effects deben ir después del `interrupt()` y ser idempotentes, porque al reanudar el nodo se ejecuta otra vez desde el inicio. Y sin checkpoint, un flujo pausado se perdería al terminar el proceso.

**Qué decisión cambió después de probar**
Pasé el checkpointer de SQLite a Azure SQL, y agregué un mensaje por cada fallo simulado para poder mostrar el retry.

**Evidencia:** logs de pausa, aprobación, rechazo, retry y regla sin retry en EVIDENCIAS §5–6; `test_grafo.py` y `test_checkpointer.py`.

---

## Hito 5 · MCP: desacoplar capacidades

**Qué construí**
- Un servidor MCP por stdio con 4 tools y 1 Resource (`politica://credito`), de solo lectura, sobre vistas, y sin `ejecutar_sql`.
- Un cliente MCP puro sin LLM (`list_tools`, `call_tool` y `read_resource`).
- El agente consume el mismo servidor: una liberación hace 4 llamadas MCP.
- Pruebas por stdio real con un servidor de prueba en memoria (`tests/test_mcp.py`).

**Qué falló**
- `mcp>=1.10` sin tope instaló mcp 2.x y el servidor dejó de arrancar con un `uv sync` limpio.

**Qué aprendí**
MCP separa la capacidad de negocio de la aplicación que la consume: un contrato único y de solo lectura evita que cada app repita el acceso a la base. Entendí por qué no se expone `ejecutar_sql` (sería SQL libre) y por qué un Resource informa pero no autoriza.

**Qué decisión cambió después de probar**
Fijé `mcp>=1.10,<2` y regeneré `uv.lock`.

**Evidencia:** la salida del cliente puro y del agente (EVIDENCIAS §7); el diagrama antes/después en `docs/arquitectura.md`; `tests/test_mcp.py`.

---

## Hito 6 · Integración y reflexión

**Qué construí**
- El caso end-to-end (router, fuentes, workflow y MCP), reproducible con `uv run andes-demo`.
- `README.md`, `CHECKLIST.md`, `GUIA_EXPOSICION.md`, `DECISIONES.md`, `EVIDENCIAS.md` y `USO_IA.md`.

**Qué falló**
- Las respuestas del redactor con LLM añaden algo de ruido (por ejemplo "Aprobación: (vacía)") y no son idénticas entre ejecuciones.

**Qué aprendí**
- **Probabilístico vs determinista:** son probabilísticos el router con baja confianza, la redacción de la respuesta y los embeddings. Son deterministas las reglas de crédito, las validaciones y la idempotencia.
- **Con SAP/ERP/CRM reales:** las tools leerían del ERP por API, habría autenticación por usuario y límites de tasa, y la liberación se escribiría en el ERP con transacciones e idempotencia.
- **Mayor riesgo del diseño actual:** el checkpointer propio, que tiene menos madurez que los oficiales, y el RAG como dependencia externa.
- **Qué simplificaría en un año:** usaría plantilla pura para las decisiones y LLM solo para consultas, y un PostgreSQL gestionado con el checkpointer oficial.

**Qué decisión cambió después de probar**
La respuesta base se arma por código y el LLM solo la reformula, con una plantilla de respaldo si Foundry falla.

**Evidencia:** `uv run pytest` (55 pruebas), las ejecuciones del 2026-10-24, `git_log.txt` y el video (`VIDEO_LINK.txt`).
