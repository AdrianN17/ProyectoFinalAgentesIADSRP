# HITOS.md · CRE-001 (Crédito) · semilla 7885

> **Borrador para que lo revises y lo reescribas con tus palabras.** Los hechos (qué se construyó, qué falló, qué evidencia hay) salen del proyecto real. Las secciones *"Qué aprendí"* son una propuesta: ajústalas a lo que realmente entendiste antes de entregar.

Evidencia detallada de cada hito en [EVIDENCIAS.md](./EVIDENCIAS.md); decisiones en [DECISIONES.md](./DECISIONES.md).

---

## Hito 1 · Separar responsabilidades

**Qué se construyó**
- `config_caso.py`: CASO_ID `CRE-001`, SEMILLA `7885`; la semilla fija 5 parámetros (límite, exposición, monto de revisión, stock de EDGE-ORIN, lead time) y se imprimen al iniciar.
- Datos en Azure SQL (`sql/01_schema.sql`, `02_seed.sql`): 5 clientes (sano, línea ajustada, el del caso, en hold, sano), 6 productos, inventario, 11 ventas y 11 pagos.
- 3 documentos de política en `data/politicas/` y reglas objetivas en `reglas.py`, con pruebas.
- 10 solicitudes clasificadas en `docs/consulta_capacidad.md`.

**Qué falló**
- Nada bloqueante en este hito. Los problemas de T-SQL aparecieron después, al crear el checkpointer (Hito 4).

**Qué aprendí** *(borrador)*
Las reglas objetivas (línea, hold, monto) no necesitan LLM y deben ser funciones puras. Lo que cambia seguido (stock, exposición) vive en la base de datos; las políticas son documentos.

**Qué decisión cambió después de probar**
La semilla también se aplica a los datos en Azure SQL (no solo a variables en memoria), para que SQL, las tools y las reglas vean el mismo escenario.

**Evidencia:** `docs/consulta_capacidad.md`; `tests/test_reglas.py` y `test_semilla_reproducible`; EVIDENCIAS §1.

---

## Hito 2 · Router + RAG + SQL + Tools

**Qué se construyó**
- Router híbrido con 5 destinos (`RAG`, `SQL`, `TOOLS`, `CLARIFY`, `DIRECT`), umbral de confianza 0.6 y validación determinista de lo que sugiere el modelo.
- RAG sobre Qdrant con embeddings de Foundry (3 documentos, 12 fragmentos) que cita archivo y sección.
- SQL parametrizado (`db.py`) y 4 tools semánticas: `consultar_stock`, `consultar_estado_credito`, `consultar_historial_ventas`, `consultar_parametros_credito`.
- 14 casos de evaluación del router, 3 pruebas RAG, 4 SQL y pruebas de tools/datos inválidos.

**Qué falló**
- Dos errores reales del router: una regla segura y equivocada (política con cliente → `TOOLS/credito` con 0.85) y verbos faltantes ("necesita"). Ver EVIDENCIAS §3.
- Qdrant devolvía 403 por una API key inválida y Foundry 404 por un deployment inexistente.

**Qué aprendí** *(borrador)*
Un router con reglas puede estar seguro y equivocado: hay que probarlo con frases nuevas, no solo con las que uno escribió. Enviar todo a todas las herramientas costaría tiempo y dinero; la baja confianza debe terminar en aclaración, no en adivinar.

**Qué decisión cambió después de probar**
Se reordenaron las reglas (la pregunta explícita de política gana) y se añadió un umbral de similitud (0.35) en RAG para no citar fragmentos irrelevantes.

**Evidencia:** `tests/test_router.py`, `test_rag.py`, `test_sql.py`; EVIDENCIAS §3–4.

---

## Hito 3 · Workflow con estado

**Qué se construyó**
- LangGraph con 7 nodos y 4 *conditional edges*; State pequeño documentado campo por campo.
- Rutas que terminan directamente: saludo, aclaración, consultas informativas, datos inválidos, stock insuficiente y liberación automática.
- Diagrama y explicación del State en `docs/workflow_state.md`.

**Qué falló**
- Reutilizar un `id_hilo` en `ejecutar` mezclaba el estado previo (trazas y advertencias duplicadas, porque los campos acumulativos suman).

**Qué aprendí** *(borrador)*
Un if/else no sobrevive a una pausa de horas ni a otro proceso; el estado debe ser pequeño y explícito. Los campos acumulativos del State se comportan distinto al reutilizar un hilo.

**Qué decisión cambió después de probar**
`ejecutar` ahora rechaza un `id_hilo` que ya existe.

**Evidencia:** `docs/workflow_state.md`; `test_grafo.py` (ruta directa); EVIDENCIAS §5.

---

## Hito 4 · Retry, checkpoint y HITL

**Qué se construyó**
- `RetryPolicy` solo en `consultar_fuentes` y solo para `FalloTransitorio`.
- `AzureSqlSaver`: checkpoint persistente en Azure SQL (`lg.checkpoints`, `lg.writes`).
- `interrupt()` ante hold, línea insuficiente o monto de revisión; reanudación con `Command(resume=...)` y el mismo `id_hilo`; `registrar_liberacion` idempotente tras el `interrupt()`.

**Qué falló**
- `checkpoint` es palabra reservada en T-SQL: la creación de tablas falló hasta usar `[checkpoint]`.
- El retry funcionaba pero no dejaba evidencia visible.
- La primera versión usaba SQLite local.

**Qué aprendí** *(borrador)*
Un timeout merece retry; un cliente en hold no. Los side effects van después del `interrupt()` y deben ser idempotentes porque el nodo se vuelve a ejecutar al reanudar.

**Qué decisión cambió después de probar**
Pasar el checkpointer de SQLite a Azure SQL, y mostrar un mensaje por cada fallo simulado.

**Evidencia:** logs de pausa, aprobación, rechazo, retry y regla sin retry en EVIDENCIAS §5–6; `test_grafo.py`, `test_checkpointer.py`.

---

## Hito 5 · MCP: desacoplar capacidades

**Qué se construyó**
- Servidor MCP stdio con 4 tools y 1 Resource (`politica://credito`), solo lectura, sobre vistas; sin `ejecutar_sql`.
- Cliente MCP puro sin LLM (`list_tools`, `call_tool`, `read_resource`).
- El agente consume el mismo servidor (una liberación hace 4 llamadas MCP).
- Pruebas por stdio real con un servidor de prueba en memoria (`tests/test_mcp.py`).

**Qué falló**
- `mcp>=1.10` sin tope instaló mcp 2.x y el servidor dejó de arrancar con `uv sync` limpio.

**Qué aprendí** *(borrador)*
MCP separa la capacidad de negocio de quien la consume; el contrato único y de solo lectura evita exponer de más. Un Resource informa, no autoriza.

**Qué decisión cambió después de probar**
Se fijó `mcp>=1.10,<2` y se regeneró `uv.lock`.

**Evidencia:** salida del cliente puro y del agente (EVIDENCIAS §7); diagrama antes/después en `docs/arquitectura.md`; `tests/test_mcp.py`.

---

## Hito 6 · Integración y reflexión

**Qué se construyó**
- Caso end-to-end (router + fuentes + workflow + MCP) reproducible con `uv run andes-demo`.
- `README.md`, `CHECKLIST.md`, `GUIA_EXPOSICION.md`, `DECISIONES.md`, `EVIDENCIAS.md`, `USO_IA.md`.

**Qué falló**
- Las respuestas del redactor LLM añaden ruido ("Aprobación: (vacía)") y no son idénticas entre ejecuciones.

**Qué aprendí** *(borrador)*
- *Probabilístico:* router con baja confianza, redacción de la respuesta, embeddings. *Determinista:* reglas de crédito, validaciones, idempotencia.
- *Con SAP/ERP reales:* las tools leerían del ERP vía API, habría autenticación por usuario y límites de tasa, y la liberación escribiría en el ERP con transacciones e idempotencia.
- *Mayor riesgo:* el checkpointer propio (poca madurez) y el RAG como dependencia externa.
- *Qué simplificaría:* usar plantilla pura para decisiones y LLM solo para consultas; PostgreSQL con checkpointer oficial.

**Qué decisión cambió después de probar**
Respuesta base por código y LLM solo como reformulador, con plantilla de respaldo.

**Evidencia:** `uv run pytest` (55 passed), ejecuciones del 2026-10-24, `git_log.txt`, video (`VIDEO_LINK.txt`).
