# CHECKLIST · AI Operations Agent · CRE-001 (Crédito) · semilla 7885

> Validado el 2026-10-24 contra el proyecto `melgarejo_adrian_modulo3/` y la ejecución real sobre Azure SQL, Azure AI Foundry y Qdrant Cloud.
> Fuente: `Modulo3_Proyecto_Final_DSRP.pdf` (secciones 7–17 y Anexo A).

**Leyenda:** ✅ cumple y verificado · ⚠️ cumple parcialmente · ❌ falta · 🎬 depende de ti (video / tu autoría)

## Resumen

| Bloque | Estado |
|---|---|
| Código y núcleo técnico (router, RAG, SQL, tools, LangGraph, retry, checkpoint, HITL, MCP) | ✅ Funciona y se ejecutó de punta a punta |
| Pruebas | ✅ 74 pasan; cubren todo lo que pide la sección 12 del PDF |
| Entregables documentales (`HITOS`, `EVIDENCIAS`, `DECISIONES`, `USO_IA`, `docs/`) | ✅ Completos (los dos de proceso están en primera persona; repásalos antes de entregar) |
| Git (≥ 4 commits, `git_log.txt`) | ✅ 6 commits (uno por hito) y `git_log.txt` |
| Video | 🎬 Pendiente (lo grabas tú) |

**Topes de nota:** ya no hay ninguno activo salvo el video. `USO_IA.md` existe (evita −10) y está redactado en primera persona; antes de entregar, léelo y quita o ajusta cualquier frase que no refleje lo que realmente hiciste.

> Los commits se agruparon **por hito después de construir** el proyecto: reflejan el orden y la estructura del trabajo, pero el contenido de cada archivo es el final. Si quieres commits que muestren evolución real, haz commits pequeños desde ahora (por ejemplo, el cambio del minuto 8:00 del video).

---

## 1. Checklist final del PDF (sección 17)

| # | Ítem | Estado | Evidencia / qué falta |
|---|---|---|---|
| 1 | CASO_ID y SEMILLA reproducibles | ✅ | `config_caso.py`: `CRE-001` / `7885`, generador aislado `random.Random(7885)`. Test `test_semilla_reproducible`. Se imprimen al iniciar cada `ejecutar`. |
| 2 | `uv sync` funciona | ✅ | Verificado: `uv sync --extra dev` (107 paquetes) y `uv run pytest` pasan. Se corrigió `mcp>=1.10,<2` (con mcp 2.x el servidor no arrancaba) y se regeneró `uv.lock`. |
| 3 | README con comandos exactos | ✅ | [README.md](./README.md). Verificados: `uv run andes-demo`, `andes-mcp-cliente`, `andes-init-db`, `pytest`. |
| 4 | `HITOS.md` con los 6 hitos | ✅ | Los 6 hitos con qué se construyó, qué falló, qué aprendiste, qué decisión cambió y evidencia (en primera persona). |
| 5 | Router con 12 casos | ✅ | 14 casos de evaluación en `tests/test_router.py`, incluido uno donde la mejor acción es no usar ninguna tool. |
| 6 | RAG muestra fuentes | ✅ | Respuestas citan `politica_credito.md · Cliente en hold`. Verificado en vivo con Qdrant Cloud (12 fragmentos, 3 documentos). |
| 7 | SQL parametrizado | ✅ | `db.py`: todas las consultas usan `?`; despacho cerrado en `Repositorio.ejecutar`. 4 pruebas en `tests/test_sql.py` (incluye un intento de inyección que viaja como parámetro). |
| 8 | Workflow pausa y reanuda | ✅ | Verificado en Azure SQL: pausa con `H1`, reanudación desde otra instancia, `reanudar` sobre hilo no pausado se rechaza. |
| 9 | Retry técnico demostrado | ✅ | `SIMULAR_FALLOS_FUENTES=2` imprime 2 fallos y la recuperación. Con 3 fallos se agota (`max_attempts=3`). Test `test_retry_en_fallo_transitorio`. |
| 10 | Regla de negocio sin retry demostrada | ✅ | Cliente en hold (C-1004) pausa a la primera, sin reintentos. Test `test_regla_de_negocio_no_se_reintenta`. |
| 11 | MCP cliente puro funciona | ✅ | `uv run andes-mcp-cliente`: `list_tools` (4 tools), `call_tool` y `read_resource` contra Azure SQL. |
| 12 | Agente consume MCP | ✅ | `andes-demo` usa `McpFuentes` por defecto (4 llamadas MCP por liberación). |
| 13 | Tests ejecutables | ✅ | `uv run pytest` → 74 passed. |
| 14 | `DECISIONES.md` completo | ✅ | 8 decisiones con problema, alternativas, decisión, trade-off, riesgo y cambio en producción. |
| 15 | `USO_IA.md` completo | ✅ | Herramientas, 3 prompts, qué generó la IA, qué decidiste tú, sugerencia rechazada, errores de IA y validación. |
| 16 | `git_log.txt` incluido | ✅ | Repositorio con 6 commits y `git_log.txt`. |
| 17 | Video entre 9:00 y 10:30 | 🎬 | Usa [GUIA_EXPOSICION.md](./GUIA_EXPOSICION.md). |
| 18 | Video incluye cambio real de código | 🎬 | Cambio preparado en la guía (minuto 8:00). |
| 19 | Video explica causas, no solo resultados | 🎬 | Puntos de explicación incluidos en la guía. |

---

## 2. Entregables (sección 9)

| Archivo | Estado | Nota |
|---|---|---|
| `README.md` | ✅ | |
| `pyproject.toml` | ✅ | |
| `.env.example` | ✅ | Sin valores en campos sensibles (verificado). |
| `src/` | ✅ | `src/andes_agent/` (20 módulos). |
| `data/` | ✅ | `data/politicas/` (3 documentos). Datos de negocio en `sql/`. |
| `docs/` | ✅ | `consulta_capacidad.md` (tabla del Hito 1), `arquitectura.md` (incluye antes/después de MCP) y `workflow_state.md` (diagrama y State campo por campo). |
| `tests/` | ✅ | Ver sección 3. |
| `HITOS.md` | ✅ | Los 6 hitos. |
| `EVIDENCIAS.md` | ✅ | Salidas reales de las ejecuciones, errores del router, errores propios y cambios de decisión. |
| `DECISIONES.md` | ✅ | 8 decisiones. |
| `USO_IA.md` | ✅ | Completo (primera persona). |
| `git_log.txt` | ✅ | Generado desde el repositorio. Regenéralo si haces más commits: `git log --stat > git_log.txt`. |
| `VIDEO_LINK.txt` | 🎬 | Contiene un marcador: pega el enlace del video. |

> La carpeta se llama `melgarejo_adrian_modulo3` (formato `apellido_nombre_modulo3`) ✅.

---

## 3. Pruebas mínimas (sección 12)

74 pruebas pasan (`uv run pytest`). Cobertura frente a lo exigido:

| Componente | Requerido | Estado | Detalle |
|---|---|---|---|
| Router | 12 casos | ✅ | 14 casos de evaluación (`test_router.py`), con 2 regresiones de errores reales. |
| RAG | 3 consultas, 1 sin RAG | ✅ | 3 pruebas (`test_rag.py`) con Qdrant en memoria, más 2 de workflow: una consulta de stock **no llama al RAG** y una de política **sí lo usa y cita la fuente**. |
| SQL | 3 consultas | ✅ | `test_sql.py`: stock, crédito (con texto malicioso como parámetro) e historial (límite acotado), con conexión simulada. |
| Workflow | directa, HITL, aprobar, rechazar | ✅ | `test_grafo.py` |
| Retry | error transitorio simulado | ✅ | `test_retry_en_fallo_transitorio` |
| Regla de negocio | bloqueada sin retry | ✅ | `test_regla_de_negocio_no_se_reintenta` |
| MCP | `list_tools` + `call_tool` sin LLM | ✅ | `test_mcp.py`: stdio real contra un servidor de prueba en memoria (también `read_resource`, rechazo de entrada inválida y ausencia de SQL libre). |
| Agente MCP | 1 consulta compuesta | ✅ | `test_agente_consume_el_mismo_servidor_con_consulta_compuesta`: 4 llamadas MCP y pausa por HITL. |
| Datos inválidos | SKU o cliente inexistente | ✅ | `test_cliente_inexistente_responde_sin_hitl`, `test_datos_invalidos` |
| Solicitud ambigua | aclarar o detener | ✅ | `test_solicitud_ambigua_pide_aclaracion` |

Además hay pruebas propias: reglas (6), checkpointer (7) y semilla/parser.

---

## 4. Requisitos técnicos del núcleo (sección 8)

| Req. | Estado | Evidencia |
|---|---|---|
| **Router**: ≥ 4 destinos | ✅ | `RAG`, `SQL`, `TOOLS`, `CLARIFY`, `DIRECT` (`router.py`). |
| Router: justificar enfoque | ✅ | **Híbrido** (reglas primero, Foundry solo con baja confianza, validación determinista de lo que sugiere el modelo). Justificación escrita en `DECISIONES.md` (D1). |
| Router: ≥ 1 caso sin ninguna tool | ✅ | `Hola, ¿qué puedes hacer?` → `DIRECT` (verificado). |
| **RAG**: ≥ 2 documentos | ✅ | `politica_credito`, `politica_entrega`, `politica_excepciones`. |
| RAG: indica la fuente | ✅ | Archivo y sección en cada respuesta. |
| RAG: caso que decide no usar RAG | ✅ | Consulta de stock o historial → sin RAG (verificado en vivo y con `test_consulta_de_stock_decide_no_usar_rag`). |
| **SQL** parametrizado | ✅ | `db.py` |
| ≥ 3 Tools semánticas | ✅ | `consultar_stock`, `consultar_estado_credito`, `consultar_historial_ventas`, `consultar_parametros_credito`. La regla de crédito es `evaluar_liberacion` (Python). |
| Cliente/SKU inexistente y stock insuficiente | ✅ | Verificados en vivo: `cliente_inexistente`, `sku_inexistente`, `stock_insuficiente` (500 unidades → `no_liberable`, sin pausa). |
| **LangGraph**: State pequeño y explícito | ⚠️ | `Estado` en `graph.py`, explicado campo por campo en `docs/workflow_state.md`. Punto discutible: `evidencia` guarda las últimas 5 ventas del historial; para producción se reduciría al resumen (está anotado en el documento). |
| ≥ 5 nodos | ✅ | 7: `parsear_solicitud`, `enrutar`, `consultar_fuentes`, `evaluar_reglas`, `aprobacion_humana`, `registrar_liberacion`, `responder`. |
| ≥ 1 conditional edge | ✅ | 4 (`tras_enrutar`, `tras_fuentes`, `tras_reglas`, `tras_aprobacion`). |
| Retry + checkpoint + `interrupt()` + mismo `id_hilo` | ✅ | `RetryPolicy` solo sobre `consultar_fuentes` con `FalloTransitorio`; checkpoint en Azure SQL (`lg.*`); verificado. |
| **MCP**: ≥ 2 Tools + 1 Resource | ✅ | 4 Tools + Resource `politica://credito`. |
| Cliente puro sin LLM | ✅ | `cliente_mcp_puro.py` |
| Agente consumidor | ✅ | `fuentes.py` → `mcp_client.py` |
| stdio | ✅ | `mcp.run(transport="stdio")` |
| Sin SQL libre expuesto | ✅ | No existe `ejecutar_sql`; solo consultas fijas sobre vistas. |

---

## 5. Restricciones de ingeniería (sección 13)

| Restricción | Estado | Nota |
|---|---|---|
| No prompt gigante | ✅ | Prompts cortos y separados (router, redactor). |
| No secretos hardcodeados | ✅ | Escaneo: ningún valor de `.env` aparece en el código ni en los demás archivos. `.env` está en `.gitignore`. **Al entregar, no incluyas `.env`.** |
| No SQL libre del LLM | ✅ | El LLM nunca produce SQL. |
| No side effects antes de `interrupt()` | ✅ | `aprobacion_humana` no escribe; `registrar_liberacion` va después y es idempotente (`UNIQUE(id_hilo)`). |
| No retries para reglas de negocio | ✅ | `retry_on=FalloTransitorio` solo. |
| No guardar contexto innecesario en State | ⚠️ | Ver nota de `evidencia` en la sección 4 y en `docs/workflow_state.md`. |
| No exponer más por MCP de lo necesario | ✅ | Solo lectura, sobre vistas; sin aprobar ni modificar. |
| No usar outputs no validados en ramas críticas | ✅ | Las ramas críticas salen de `reglas.py`. La salida del router (LLM) se valida con Pydantic y con `_datos_completos`; la del redactor se valida contra los hechos (`validar_respuesta`) y, si no coincide, se descarta. |

---

## 6. Evidencia de proceso y aprendizaje (sección 11)

| Requisito | Estado | Qué tienes / qué falta |
|---|---|---|
| ≥ 4 commits con evolución real | ⚠️ | 6 commits, uno por hito. Se agruparon después de construir (reflejan el orden del trabajo, no la evolución archivo por archivo). Haz commits pequeños reales desde ahora. |
| Error propio introducido y corregido | ✅ | 9 errores documentados con causa y corrección (`EVIDENCIAS.md` §8). Elige uno para contar en el video. |
| Ejecución con fallo técnico y retry | ✅ | Reproducible con `SIMULAR_FALLOS_FUENTES=2`. |
| Regla de negocio rechazada sin retry | ✅ | Cliente en hold, rechazo por Finanzas. |
| Pausa y reanudación con mismo `id_hilo` | ✅ | |
| Caso donde el router se equivoque o tenga baja confianza | ✅ | Dos errores reales del router (confianza 0.85 con destino equivocado, y verbos faltantes) y el caso de baja confianza que resuelve el LLM (`EVIDENCIAS.md` §3). |
| Una decisión que cambiarías en producción | ✅ | En cada decisión de `DECISIONES.md` ("En producción"). |
| IA sugirió algo incorrecto y lo corregiste | ⚠️ | Documentado en `USO_IA.md` §6; revisa que coincida con lo que viviste. |

**Errores reales ocurridos durante el desarrollo** (ya documentados en `EVIDENCIAS.md`, `HITOS.md` y `USO_IA.md`):

1. `checkpoint` es palabra reservada de T-SQL: `04_checkpoints.sql` falló hasta usar `[checkpoint]`.
2. `mcp>=1.10` sin tope: un `uv sync` limpio instalaba mcp 2.x y el servidor MCP no arrancaba (`FastMCP` fue renombrado).
3. `temperature=0` rechazado por `gpt-5-mini` (modelo de razonamiento) y deployment `gpt-4o-mini` inexistente en el recurso.
4. Endpoint equivocado: el de proyecto de Foundry (`.../api/projects/...`) no sirve con `AzureOpenAI`; hace falta el del recurso (`https://<recurso>.openai.azure.com/`).
5. Reutilizar un `id_hilo` en `ejecutar` mezclaba el estado anterior (trazas y advertencias duplicadas). Corregido: ahora se rechaza.
6. El reintento funcionaba pero no dejaba evidencia visible; se agregó salida por intento.
7. Sin ODBC Driver 18 el proyecto no conectaba a Azure SQL (documentado en README).

---

## 7. Topes de nota (sección 15)

| Situación | Estado |
|---|---|
| Sin video → no aprobado | 🎬 Pendiente |
| Video solo con slides o código sin ejecutar → máx. 59 | 🎬 Ejecuta todo en vivo con la guía |
| Proyecto que no instala/ejecuta con README → máx. 59 | ✅ Verificado con `uv sync` y `uv run` |
| No demuestra pausa y resume real → máx. 69 | ✅ Listo para demostrar |
| MCP solo como código → máx. 69 | ✅ Se ejecuta (cliente puro y agente) |
| No entrega `USO_IA.md` → −10 | ✅ Entregado (borrador: complétalo) |
| Secreto/API key expuesto → −15 mínimo | ✅ No hay secretos en el código. Cuida `.env` y no lo muestres en pantalla durante el video. |
| Video y código no corresponden | 🎬 Graba desde esta misma carpeta |
| Entrega idéntica a otra sin justificar semilla | ✅ Valores propios de la semilla 7885 |

---

## 8. Observaciones de diseño a tener presentes (para responder en el video)

- **Se usó Azure SQL, Qdrant Cloud y checkpointer en Azure SQL.** El PDF los lista como *extensiones* (base remota, vector DB externa, persistencia externa). Está bien, pero el núcleo debe poder defenderse: ¿por qué Qdrant en vez de RAG local? ¿qué pasa si Qdrant cae? (el flujo degrada con una advertencia: la política cita, no decide).
- **El redactor LLM ya no puede omitir ni contradecir la decisión.** Devuelve una estructura (`estado`, `aprobador`, `monto`, `mensaje`) que el código valida contra los hechos reales; si no coincide, se usa la plantilla y aparece una advertencia (D8). Aun así, es probabilístico: la redacción varía entre ejecuciones; con `USE_LLM=false` la respuesta es 100 % por plantilla y reproducible.
- **El checkpointer `AzureSqlSaver` es propio** (no existe uno oficial para Azure SQL). Probado en Azure SQL real; el riesgo es que no recibe las pruebas de la comunidad que sí tienen los oficiales.
- **Autenticación SQL con usuario y contraseña** (`AZURE_SQL_AUTH=sql`): en producción usarías Microsoft Entra ID / identidad administrada (`AZURE_SQL_AUTH=entra`). Además la contraseña actual es débil y se compartió en una conversación: cámbiala.

---

## 9. Pendientes (lo que solo tú puedes hacer)

1. **Leer `USO_IA.md` y `HITOS.md` completos** y asegurarte de que cada frase sea cierta y la puedas explicar: si algo no lo hiciste o no lo entiendes, ajústalo antes de entregar.
2. 🎬 **Grabar el video** (9:00–10:30) con [GUIA_EXPOSICION.md](./GUIA_EXPOSICION.md) y pegar el enlace en `VIDEO_LINK.txt`.
3. **Commits reales:** haz commits pequeños con tus cambios (p. ej. el del minuto 8:00) y regenera `git log --stat > git_log.txt`.
4. **Cambiar la contraseña de Azure SQL** (se compartió en una conversación).
5. Antes de entregar: sin `.env` en la carpeta, `uv run pytest` en verde y `uv run andes-init-db --limpiar-demo`.
6. Archivo `src/andes_agent/llm.py`: está vacío y sin commit (apareció junto con la desaparición de `foundry.py` y no es parte del proyecto). Bórralo si no lo necesitas.
