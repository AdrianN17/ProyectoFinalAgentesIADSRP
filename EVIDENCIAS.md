# EVIDENCIAS.md · CRE-001 (Crédito) · semilla 7885

Todas las salidas son de ejecuciones reales del 2026-10-24 sobre Azure SQL (`dbtestgt.database.windows.net`), Azure AI Foundry (`azfnd01`, `gpt-5-mini`) y Qdrant Cloud. Comandos con `uv run` desde esta carpeta. La redacción del texto final varía entre ejecuciones (modelo generativo); lo estable es la decisión, las fuentes y la trazabilidad.

## 1. Semilla y parámetros (Hito 1)

```
[CRE-001] variante=D · Crédito semilla=7885
  limite_credito = 40000.0
  exposicion_actual = 34092.0
  monto_revision = 20000.0
  stock_edge_orin = 33
  lead_time_dias = 3
```

Se imprimen al inicio de cada `ejecutar` y `andes-init-db` los aplica a Azure SQL. Mismo valor en cada corrida (`test_semilla_reproducible`).

## 2. Pruebas

`uv run pytest -q` → **77 passed**.

| Archivo | Pruebas | Cubre |
|---|---|---|
| `test_reglas.py` | 6 | línea insuficiente, hold, monto de revisión, venta sana, stock, datos inválidos |
| `test_router.py` | 19 | **14 casos de evaluación del router** + semilla + parser + 3 con LLM simulado |
| `test_rag.py` | 3 | cita fuente y sección, plazos de entrega, consulta sin relación bajo umbral |
| `test_sql.py` | 7 | **3 consultas SQL** parametrizadas + despacho cerrado + **reintento de conexión cuando la base serverless despierta** (3 pruebas) |
| `test_grafo.py` | 11 | directa, HITL, aprobar, rechazar, otro `id_hilo`, retry, regla sin retry, cliente inexistente, ambigua, **no usar RAG**, **RAG con cita** |
| `test_mcp.py` | 5 | `list_tools`, `call_tool`, `read_resource` por stdio real sin LLM; entrada inválida; **agente con consulta compuesta** |
| `test_redactor.py` | 19 | **redactor con salida estructurada**: respuesta válida, estado/aprobador/monto incorrectos, mensaje que omite la aprobación (el caso real que falló), fallo del LLM → plantilla |
| `test_checkpointer.py` | 7 | filtros SQL, pausa/reanuda con otra instancia, historial, borrado |

## 3. Router (Hito 2)

### 14 casos de evaluación (`tests/test_router.py`)
Los 8 primeros cubren liberación, stock, crédito, SQL, RAG, DIRECT, CLARIFY y una frase vaga. El caso `Hola, ¿qué puedes hacer?` es el que **no usa ninguna tool**. Los casos 9–14 son variantes y regresiones.

### Errores reales del router y por qué ocurrieron
Al probar frases nuevas encontré dos fallos de las reglas:

| Frase | Esperado | Obtuvo | Causa |
|---|---|---|---|
| "El cliente C-1004 no pagó, ¿qué dice la política de hold?" | `RAG/politica` | `TOOLS/credito` (confianza **0.85**) | La regla "cliente + palabra `hold`" se evaluaba antes que la de política. Estaba segura y equivocada. |
| "C-1003 necesita 12 EDGE-ORIN para esta semana" (la redacción del propio PDF) | `TOOLS/liberacion` | `CLARIFY` (0.30) | La lista de verbos no incluía "necesita", "quiero", "requiere". |

**Corrección** (`router.py`): una pregunta explícita de política (`politica`, `normativa`, `procedimiento`, `reglamento`) gana aunque mencione un cliente, y "necesita/quiere/requiere" cuenta como pedido de venta solo si hay SKU y cantidad (así "quiero saber el stock de EDGE-ORIN" sigue siendo stock). Ambos casos quedaron como pruebas de regresión.

### Baja confianza con LLM
`necesito algo urgente` → reglas dan 0.30 → Foundry responde con confianza 0.90 → `_datos_completos` falla (no hay cliente/SKU) → `CLARIFY`:
```
ruta=CLARIFY/ninguna | pasos=parsear > enrutar:CLARIFY/ninguna(llm,0.90)
```

## 4. RAG, SQL y Tools (Hito 2)

| Consulta | Ruta | Fuentes |
|---|---|---|
| ¿Qué dice la política cuando un cliente está en hold? | `RAG/politica` | `politica_credito.md · Cliente en hold; politica_excepciones.md · Qué se considera excepción` |
| ¿Cuánto stock hay de EDGE-ORIN? (**sin RAG**) | `TOOLS/stock` | `azure_sql:ops.v_stock` → 33 unidades, lead time 3 días |
| Muéstrame el historial de pagos de C-1004 | `SQL/historial` | `azure_sql:ops.v_ventas_cliente,ops.v_pagos_cliente` → 2 pagos vencidos por 39.500 |
| ¿Cómo está la línea de crédito de C-1003? | `TOOLS/credito` | `azure_sql:ops.v_estado_credito` |

Datos inválidos y stock:

| Solicitud | Resultado |
|---|---|
| C-9999 pide 2 EDGE-ORIN | `evaluar_reglas:datos_invalidos` (`cliente_inexistente`), sin pausa |
| C-1001 pide 2 XXX-NADA | `datos_invalidos` (`sku_inexistente`), sin pausa |
| C-1001 pide 500 EDGE-ORIN | `no_liberable` (`stock_insuficiente`), sin pausa |
| Libera la venta de C-1003 | `CLARIFY` (faltan SKU y cantidad), no consulta fuentes |

## 5. Workflow, pausa y reanudación (Hitos 3–4)

Ruta directa (cliente sano, sin excepción):
```
C-1001 pide 2 EDGE-ORIN a crédito
pasos=parsear > enrutar:TOOLS/liberacion(reglas,0.90) > consultar_fuentes > evaluar_reglas:ok > registrar_liberacion
liberada automáticamente (aprobador REGLAS_AUTOMATICAS)
```

Caso base, flujo pausado:
```
== FLUJO PAUSADO · id_hilo=T-H1 · esperando a Finanzas/Crédito ==
{ "cliente_id": "C-1003", "sku": "EDGE-ORIN", "cantidad": 12, "monto": 22200.0,
  "motivos": ["linea_insuficiente", "monto_requiere_revision"], "aprobador_requerido": "Finanzas/Crédito" }
```
Estado en Azure SQL: `T-H1  6 checkpoints`.

| Acción | Resultado |
|---|---|
| `reanudar --hilo T-OTRO` (otro `id_hilo`) | `El hilo 'T-OTRO' no está pausado (no existe o ya terminó).` |
| `ejecutar --hilo T-H1` (hilo repetido) | `El hilo 'T-H1' ya existe...` |
| `reanudar --hilo T-H1 --decision aprobar --aprobador "Ana (Finanzas)"` | `liberada tras aprobación de Ana (Finanzas) (liberación #9)`; pasos `... aprobacion_humana:aprobada > registrar_liberacion` |
| `reanudar --hilo T-H1` por segunda vez | `no está pausado`; `ops.liberaciones` tiene una sola fila para el hilo (idempotencia) |

Rechazo (cliente en hold, C-1004):
```
motivos: ["cliente_en_hold"] -> reanudar --decision rechazar --aprobador "Ana (Finanzas)" --comentario "Mora vencida"
pasos=... evaluar_reglas:excepcion > aprobacion_humana:rechazada     (no se registra liberación)
```

## 6. Retry técnico y regla de negocio sin retry (Hito 4)

Fallo transitorio provocado (`SIMULAR_FALLOS_FUENTES=2`):
```
  [fallo transitorio simulado] la dependencia no respondió; fallos restantes: 1
  [fallo transitorio simulado] la dependencia no respondió; fallos restantes: 0
  [dependencia recuperada] consulta de fuentes OK tras reintento
== FLUJO PAUSADO · id_hilo=T-R1 ...
```
Con `SIMULAR_FALLOS_FUENTES=3` se agotan los 3 intentos y termina con `FalloTransitorio: FALLO_TRANSITORIO: fallo simulado de la dependencia de stock` (error visible, no se oculta).

Regla de negocio sin retry: el caso hold de la sección 5 se detiene a la primera, sin líneas de reintento; la traza muestra una sola vez `consultar_fuentes`.

## 7. MCP (Hito 5)

`uv run andes-mcp-cliente` (sin LLM):
```
== list_tools ==
- consultar_stock / consultar_estado_credito / consultar_historial_ventas / consultar_parametros_credito
== call_tool ==  stock_disponible: 33 · estado_credito: activo · limite_credito: 40000.0 · exposicion_actual: 34092.0
== resource politica://credito ==  # Política de crédito y líneas · AndesSupply
```
El agente usa el mismo servidor: una liberación genera **4** `CallToolRequest` (stock, crédito, historial, parámetros). Con `--directo` genera 0. Diagrama antes/después en `docs/arquitectura.md`.

## 8. Errores propios del desarrollo y cómo se corrigieron

| # | Error | Causa | Corrección |
|---|---|---|---|
| 1 | `04_checkpoints.sql` fallaba (`Incorrect syntax near 'checkpoint'`) | `checkpoint` es palabra reservada de T-SQL | Columna `[checkpoint]` y corchetes en todas las consultas dinámicas |
| 2 | `uv sync` limpio rompía el servidor MCP | `mcp>=1.10` sin tope instaló mcp 2.x (`FastMCP` renombrado) | `mcp>=1.10,<2` y `uv.lock` regenerado |
| 3 | Foundry respondía 404 `DeploymentNotFound` | Se asumió el deployment `gpt-4o-mini`; el recurso solo tenía `gpt-5-mini` | `FOUNDRY_CHAT_DEPLOYMENT=gpt-5-mini` (verificado con `az cognitiveservices account deployment list`) |
| 4 | Chat con `gpt-5-mini` fallaba por `temperature` | Los modelos de razonamiento no aceptan `temperature=0` | Se quitó `temperature`; API `2025-04-01-preview` |
| 5 | Endpoint equivocado | Se copió el endpoint de *proyecto* de Foundry (`.../api/projects/...`) en `.env`; se detectó al revisar qué endpoint exige `AzureOpenAI` | `https://<recurso>.openai.azure.com/` |
| 6 | Qdrant respondía 403 | API key inválida/de otro cluster | Se renovó la key y se reindexó |
| 7 | Trazas y advertencias duplicadas | `ejecutar` sobre un `id_hilo` existente mezclaba el estado anterior | `ejecutar` rechaza hilos existentes |
| 8 | El retry funcionaba pero no se veía | Sin salida por intento | Mensajes por cada fallo simulado y recuperación |
| 9 | Dos errores del router (sección 3) | Orden de reglas y lista de verbos incompleta | Ajuste + pruebas de regresión |
| 10 | El redactor LLM omitió la aprobación en la respuesta ("Decisión: excepción") aunque la decisión y el registro eran correctos | Ejecución real de `reanudar` | Salida estructurada (`estado`, `aprobador`, `monto`, `mensaje`) validada por código; si no coincide, se usa la plantilla. Validado con el modelo real: 30/30 respuestas aceptadas (6 escenarios × 5 repeticiones) |
| 11 | El primer comando tras un rato de inactividad falló (5 de 23 comprobaciones en la revalidación del 2026-10-25) | La base de Azure SQL es serverless con pausa automática a los 60 min (`az sql db show`: `autoPauseDelay: 60`): la primera conexión falla mientras la base despierta | `conectar` reintenta hasta 6 veces con 10 s de espera, solo ante los errores de "base reanudando" (40613, 40197, 40501, 49918, 10928, 10929) y avisa por stderr. Un error de credenciales no se reintenta. 3 pruebas nuevas. Revalidación: 23/23 |

## 9. Cambio de decisión después de probar
- **SQLite → Azure SQL para checkpoints.** El diseño inicial usaba `SqliteSaver`; se cambió a `AzureSqlSaver` para que el estado pausado no dependa de un archivo local (D5 en `DECISIONES.md`).
- **Umbral de RAG (0.35).** Una consulta sin relación (`receta de ceviche`) aún devolvía fragmentos con puntaje ~0.2; sin umbral se habrían citado como fuente.
