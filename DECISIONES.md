# DECISIONES.md · CRE-001 (Crédito) · semilla 7885

Ocho decisiones de diseño. Cada una indica el problema, las alternativas, la decisión, el trade-off, el riesgo y qué cambiaría en producción.

---

## D1 · Router híbrido (reglas primero, LLM solo con baja confianza)

- **Problema:** elegir entre RAG, SQL, TOOLS, DIRECT y CLARIFY sin gastar un LLM en cada solicitud y sin que el LLM controle ramas críticas.
- **Alternativas:** (a) solo reglas/regex; (b) solo LLM; (c) híbrido.
- **Decisión:** híbrido. Las reglas resuelven lo evidente con confianza 0.8–0.9; si la confianza es < 0.6, Foundry clasifica con salida estructurada (Pydantic) y el resultado se **valida de nuevo con código** (`_datos_completos`): si falta cliente, SKU o cantidad, se pide aclaración aunque el modelo tenga confianza alta. Sin LLM (`USE_LLM=false`) la baja confianza termina en `CLARIFY`.
- **Trade-off:** las reglas requieren mantenimiento (cada giro nuevo del lenguaje es una regla) a cambio de coste cero, latencia mínima y reproducibilidad en los casos comunes.
- **Riesgo:** una regla puede estar *segura y equivocada* (confianza 0.85 y destino erróneo). Ocurrió dos veces durante las pruebas (ver `EVIDENCIAS.md`, sección 3).
- **En producción:** medir el router con un conjunto de evaluación creciente (hoy 14 casos), registrar los desvíos reales y calibrar umbrales con datos de uso.

## D2 · Las reglas de crédito son Python determinista, nunca el LLM

- **Problema:** decidir si una venta se libera sola, se escala o se bloquea.
- **Alternativas:** (a) LLM decide con la política como contexto; (b) LLM propone y una regla valida; (c) reglas en Python.
- **Decisión:** (c). `reglas.py` evalúa `exposición + monto > límite`, `hold`, `monto ≥ monto de revisión`, existencia de cliente/SKU y stock, con `Decimal`. Es una función pura, sin red.
- **Trade-off:** cambiar una política exige un cambio de código/parámetro, a cambio de reproducibilidad, auditoría y pruebas unitarias.
- **Riesgo:** divergencia entre el documento de política (RAG) y el código. La política se cita, pero la decisión la toma el código.
- **En producción:** mover umbrales a una tabla de parámetros versionada (ya existe `ops.parametros_caso` para el monto de revisión) y generar pruebas a partir de la política.

## D3 · Azure SQL como fuente de verdad, con vistas de solo lectura y consultas parametrizadas

- **Problema:** acceder a clientes, stock, ventas y pagos sin SQL libre del LLM y con mínimo privilegio.
- **Alternativas:** SQLite local; Azure SQL con tablas directas; Azure SQL con vistas y roles.
- **Decisión:** Azure SQL con esquema `ops`, **vistas `ops.v_*`** para lectura y roles (`rol_mcp_lectura`, `rol_agente_liberaciones`). Todas las consultas son fijas y usan `?` (nunca interpolación). El despacho de operaciones es un diccionario cerrado.
- **Trade-off:** más infraestructura que SQLite (firewall, driver ODBC 18, credenciales) a cambio de un entorno cercano a producción.
- **Riesgo:** autenticación SQL con usuario y contraseña en el entorno de pruebas.
- **En producción:** Microsoft Entra ID / identidad administrada (`AZURE_SQL_AUTH=entra`, ya soportado), sin contraseñas, y los roles de `03_permisos.sql` asignados a esas identidades.

## D4 · Qdrant + embeddings de Azure AI Foundry para el RAG

- **Problema:** recuperar política con cita de fuente, tolerando sinónimos y redacciones distintas.
- **Alternativas:** RAG léxico local (núcleo del PDF); Azure AI Search; Qdrant.
- **Decisión:** Qdrant (colección `credito`, 12 fragmentos de 3 documentos, uno por sección `##`) con `text-embedding-3-small`. Se aplica un umbral mínimo (0.35) para no citar fragmentos irrelevantes, y si Qdrant falla, el flujo **degrada con una advertencia**: la política cita, no decide.
- **Trade-off:** dependencia externa y costo de embeddings, a cambio de mejor recuperación semántica. El PDF lista la vector DB externa como extensión, no como núcleo.
- **Riesgo:** la disponibilidad de Qdrant y de Foundry afecta la calidad de las citas (no las decisiones). Ya ocurrió: una API key inválida (HTTP 403) dejó el RAG sin citas hasta renovarla.
- **En producción:** red privada, rotación de claves en Key Vault, reindexado automático al cambiar los documentos y evaluación de recuperación (recall).

## D5 · Checkpointer propio sobre Azure SQL en lugar de SQLite

- **Problema:** persistir el estado de los hilos pausados para reanudar con el mismo `id_hilo`.
- **Alternativas:** `SqliteSaver` (archivo local); checkpointer de PostgreSQL; checkpointer propio en Azure SQL.
- **Decisión:** `AzureSqlSaver` (`checkpointer.py`, tablas `lg.checkpoints` y `lg.writes`) a pedido de mantener todo en Azure. Se creó porque no existe un checkpointer oficial para Azure SQL. Hereda de `BaseCheckpointSaver`, usa consultas parametrizadas, colación binaria para ordenar los checkpoint IDs y una conexión por instancia con reconexión.
- **Trade-off:** el estado sobrevive a procesos, máquinas y contenedores efímeros, pero se mantiene código propio sin la madurez de los checkpointers oficiales.
- **Riesgo:** concurrencia (varios procesos escribiendo el mismo hilo) y cambios de la interfaz de LangGraph entre versiones. Se probó en Azure SQL real con dos instancias del saver; no hay pruebas de carga.
- **En producción:** PostgreSQL gestionado con el checkpointer oficial, o pruebas de contrato y concurrencia para el propio, además de una política de retención de hilos.

## D6 · MCP stdio de solo lectura; la escritura queda fuera de MCP

- **Problema:** exponer capacidades reutilizables sin dar poder de más.
- **Alternativas:** MCP con `ejecutar_sql`; MCP con una tool que apruebe y libere ventas; MCP solo de lectura.
- **Decisión:** 4 tools de consulta + 1 Resource (`politica://credito`), sobre vistas, con validación de formato de entradas (`C-####`, SKU). La liberación se escribe desde el agente, después de `interrupt()`, de forma idempotente (`UNIQUE(id_hilo)`).
- **Trade-off:** otro consumidor no puede liberar ventas por MCP (es deliberado), y hay dos rutas de acceso a la base (MCP para lectura, agente para la escritura).
- **Riesgo:** un Resource no es una autorización; la política expuesta no otorga permisos.
- **En producción:** MCP por Streamable HTTP con autenticación, autorización por tool (*scopes*) y auditoría de llamadas.

## D7 · `RetryPolicy` solo para fallos técnicos transitorios

- **Problema:** diferenciar un fallo técnico (red, Azure SQL serverless despertando, subproceso MCP caído) de una regla de negocio incumplida.
- **Alternativas:** retry en todo el grafo; retry en nodos críticos; retry solo en `consultar_fuentes` para `FalloTransitorio`.
- **Decisión:** la última. `db.py` traduce `OperationalError`/`InterfaceError` a `FalloTransitorio`, y el nodo reintenta 3 veces con espera creciente. Una regla de negocio (hold, línea) nunca se reintenta: pausa a la primera.
- **Trade-off:** un error técnico no clasificado como transitorio falla de inmediato, a cambio de nunca repetir efectos ni esconder una regla de negocio.
- **Riesgo:** clasificar mal un error (por ejemplo, un timeout de lógica de negocio).
- **En producción:** backoff exponencial con *jitter*, *circuit breaker* y métricas de reintentos en Application Insights.

## D8 · Redactor LLM opcional, con plantilla como respaldo

- **Problema:** respuestas legibles sin que el LLM invente cifras ni altere decisiones.
- **Alternativas:** solo plantilla; solo LLM; plantilla + LLM que reformula.
- **Decisión:** la respuesta base se construye por código (con cifras, fuentes, advertencias y trazabilidad) y, si `USE_LLM=true`, `gpt-5-mini` la reformula con instrucciones de usar solo esos hechos. Si Foundry falla, se entrega la plantilla con una advertencia. El redactor **no controla ramas**.
- **Trade-off:** respuestas más naturales a cambio de ruido (se observó "Aprobación: (vacía)" y frases repetidas) y de no ser idénticas entre ejecuciones.
- **Riesgo:** que el texto reformulado contradiga la decisión. Mitigación: la trazabilidad y las fuentes se añaden por código y la decisión es la del JSON.
- **En producción:** validar que el texto final contenga la decisión y las cifras de entrada (o usar plantilla pura para el canal de decisión y LLM solo para comentarios).
