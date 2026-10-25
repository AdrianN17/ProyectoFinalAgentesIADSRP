# Guía de exposición · comandos de consola · CRE-001 · semilla 7885

Guion para el video de 10:00 min (tolerancia 9:00–10:30). Todos los comandos se ejecutan **en vivo** desde esta misma carpeta, narrando lo que haces. Los tiempos y bloques siguen la sección 10 del PDF.

> Los textos de respuesta los redacta `gpt-5-mini`, así que la **redacción exacta puede variar** entre ejecuciones. Lo que no cambia: la decisión, los motivos, las fuentes y la trazabilidad. Si quieres respuestas idénticas siempre: `$env:USE_LLM = "false"` antes de ejecutar.

---

## 0. Antes de grabar (preparación, no se graba)

```powershell
conda activate multiagentes
cd C:\Users\adria\OneDrive\Escritorio\ProyectoFinalAgentesIA\melgarejo_adrian_modulo3
chcp 65001 | Out-Null
$env:PYTHONIOENCODING = "utf-8"
$env:UV_PYTHON = (Get-Command python).Source

uv sync --extra dev                      # dependencias (debe decir "Checked ... packages")
uv run pytest -q                         # esperado: 38 passed
uv run andes-init-db --limpiar-demo      # borra hilos y liberaciones de pruebas anteriores
```

Comprobaciones rápidas (todas deben funcionar):

| Qué | Comando | Esperado |
|---|---|---|
| Azure SQL + MCP | `uv run andes-mcp-cliente` | 4 tools y datos de EDGE-ORIN y C-1003 |
| Qdrant | `uv run andes-demo ejecutar --hilo PRE-1 "¿Qué dice la política cuando un cliente está en hold?"` | Respuesta con `Fuentes: politica_credito.md · Cliente en hold` |
| Foundry | (mismo comando anterior) | Sin línea `Advertencias:` |

Después de las pruebas, vuelve a limpiar: `uv run andes-init-db --limpiar-demo`.

**Reglas durante el video**
- Cada `ejecutar` necesita un `--hilo` **nuevo** (si repites uno, el programa lo rechaza).
- Mantén `.env` cerrado: tiene la contraseña de SQL y las API keys.
- Letra grande en la terminal; deja visibles `CRE-001` y `7885` (salen impresos al inicio de cada `ejecutar`).
- Si algo falla, muéstralo y explícalo: el PDF prohíbe ocultar fallos.

Si un comando demora, es normal: cada `ejecutar` consulta Azure SQL por MCP, Qdrant y Foundry (8–15 s).

---

## 1. 0:00–1:00 · Problema, CASO_ID y SEMILLA

**Di:** *"Mi caso es CRE-001, variante Crédito, y mi semilla es 7885. Estos valores determinan mi escenario. El proceso real es la liberación de una venta a crédito en AndesSupply, y el riesgo es liberar una venta a un cliente en hold o sin línea suficiente."*

```powershell
uv run python -c "from andes_agent.config_caso import imprimir_parametros; imprimir_parametros()"
```

Salida esperada (misma semilla ⇒ mismos valores):

```
[CRE-001] variante=D · Crédito semilla=7885
  limite_credito = 40000.0
  exposicion_actual = 34092.0
  monto_revision = 20000.0
  stock_edge_orin = 33
  lead_time_dias = 3
```

**Explica:** la semilla afecta 5 parámetros (límite, exposición, monto de revisión, stock y lead time). Con la semilla, C-1003 siempre tiene poca línea disponible (5.908), y 12 EDGE-ORIN valen 22.200.

---

## 2. 1:00–2:00 · Arquitectura

Abre `..\DIAGRAMA_ARQUITECTURA.md` (vista previa Mermaid) y, si quieres, muestra los módulos:

```powershell
Get-ChildItem src\andes_agent -Name
```

**Di (cuatro tipos de decisión):**
- **Determinista:** `reglas.py` en Python (línea insuficiente, hold, monto de revisión). Nunca el LLM.
- **Semántica:** el router (reglas primero, Foundry solo con baja confianza).
- **Proceso/estado:** LangGraph, con checkpoint en Azure SQL (esquema `lg`).
- **Integración:** el servidor MCP de solo lectura sobre vistas de Azure SQL.

---

## 3. 2:00–4:00 · Caso end-to-end y por qué el router elige cada capacidad

Ejecuta 4–5 de estas (elige según el tiempo). Para cada una, mira la línea `Trazabilidad:`: muestra la ruta elegida y los pasos.

```powershell
# a) RAG: pregunta de política -> cita fuente y sección
uv run andes-demo ejecutar --hilo V1 "¿Qué dice la política cuando un cliente está en hold?"

# b) TOOLS sin RAG: stock de un SKU (aquí el sistema decide NO usar RAG)
uv run andes-demo ejecutar --hilo V2 "¿Cuánto stock hay de EDGE-ORIN?"

# c) SQL: historial de pagos del cliente
uv run andes-demo ejecutar --hilo V3 "Muéstrame el historial de pagos de C-1004"

# d) Liberación automática: cliente sano, sin excepción
uv run andes-demo ejecutar --hilo V4 "C-1001 pide 2 EDGE-ORIN a crédito"

# e) CLARIFY: faltan SKU y cantidad -> no ejecuta ninguna tool
uv run andes-demo ejecutar --hilo V5 "Libera la venta de C-1003"
```

Resultados esperados (resumidos):

| Comando | `ruta=` en la trazabilidad | Qué muestra |
|---|---|---|
| a) | `RAG/politica` | `Fuentes: politica_credito.md · Cliente en hold; politica_excepciones.md · Qué se considera excepción` |
| b) | `TOOLS/stock` | `33 unidades disponibles, lead time 3 días`, `Fuentes: azure_sql:ops.v_stock` (sin fuente de RAG) |
| c) | `SQL/historial` | `Pagos vencidos: 2 por 39500.00`, `Fuentes: azure_sql:ops.v_ventas_cliente,ops.v_pagos_cliente` |
| d) | `TOOLS/liberacion` | `liberada automáticamente (liberación #N)`, pasos: `... evaluar_reglas:ok > registrar_liberacion` |
| e) | `CLARIFY/ninguna` | `Necesito más información...` (sin consultar fuentes) |

Opcionales si te sobra tiempo:

```powershell
uv run andes-demo ejecutar --hilo V6 "Hola, ¿qué puedes hacer?"                 # DIRECT, sin tool
uv run andes-demo ejecutar --hilo V7 "C-9999 pide 2 EDGE-ORIN a crédito"         # cliente inexistente
uv run andes-demo ejecutar --hilo V8 "C-1001 pide 500 EDGE-ORIN a crédito"       # stock insuficiente (no_liberable, sin HITL)
```

**Explica:** *"Una venta histórica no se resuelve con RAG porque es dato transaccional que cambia; la política es documental. Si el router duda, pide aclaración en lugar de adivinar. Enviar todo a todas las herramientas costaría tiempo, dinero y riesgo."*

---

## 4. 4:00–5:30 · LangGraph HITL: pausa, `id_hilo` y reanudación

```powershell
# 1) Caso base: línea insuficiente (22.200 > 5.908 disponibles) y monto >= monto de revisión
uv run andes-demo ejecutar --hilo H1
```

Esperado:

```
== FLUJO PAUSADO · id_hilo=H1 · esperando a Finanzas/Crédito ==
{ "tipo": "aprobacion_credito", "id_hilo": "H1", "cliente_id": "C-1003", "sku": "EDGE-ORIN",
  "cantidad": 12, "monto": 22200.0, "motivos": ["linea_insuficiente", "monto_requiere_revision"], ... }
```

```powershell
# 2) Mostrar que el estado vive en Azure SQL (checkpoints por hilo)
@'
from andes_agent.db import conexion
with conexion() as c:
    for fila in c.cursor().execute("SELECT thread_id, COUNT(*) AS checkpoints FROM lg.checkpoints GROUP BY thread_id"):
        print(fila.thread_id, fila.checkpoints)
'@ | uv run python -

# 3) Pregunta de control: ¿qué pasa si se reanuda con OTRO id_hilo?
uv run andes-demo reanudar --hilo OTRO --decision aprobar
#    -> "El hilo 'OTRO' no está pausado (no existe o ya terminó)."

# 4) Reanudar con el MISMO id_hilo
uv run andes-demo reanudar --hilo H1 --decision aprobar --aprobador "Ana (Finanzas)"
```

Esperado del paso 4: `liberada tras aprobación de Ana (Finanzas) (liberación #N)` y en la traza `aprobacion_humana:aprobada > registrar_liberacion`.

```powershell
# 5) Comprobar que la liberación se escribió UNA vez (idempotencia: UNIQUE por id_hilo)
@'
from andes_agent.db import conexion
with conexion() as c:
    for f in c.cursor().execute("SELECT liberacion_id, id_hilo, cliente_id, sku, cantidad, monto, aprobado_por FROM ops.liberaciones"):
        print(tuple(f))
'@ | uv run python -

# 6) Reanudar de nuevo el mismo hilo: ya no está pausado, no duplica nada
uv run andes-demo reanudar --hilo H1 --decision aprobar
```

**Explica:** *"`interrupt()` detiene el grafo y el checkpoint guarda el estado en Azure SQL. No hay side effects antes del `interrupt()`: la escritura va después y es idempotente, porque al reanudar el nodo de aprobación se ejecuta otra vez desde el inicio."*

---

## 5. 5:30–7:00 · MCP: cliente puro (sin LLM) y luego el agente

```powershell
# Cliente MCP puro: list_tools + call_tool + read_resource, sin LLM
uv run andes-mcp-cliente
```

Esperado: lista de 4 tools (`consultar_stock`, `consultar_estado_credito`, `consultar_historial_ventas`, `consultar_parametros_credito`), JSON de EDGE-ORIN (stock 33) y de C-1003 (límite 40000, exposición 34092) y el inicio del Resource `politica://credito`.

```powershell
# El agente consume el MISMO servidor MCP (consulta compuesta: stock + crédito + historial + parámetros)
uv run andes-demo ejecutar --hilo M1 "C-1001 pide 3 EDGE-ORIN a crédito"
```

En la salida busca las líneas `INFO:mcp.server.lowlevel.server:Processing request of type CallToolRequest` (una por tool) y `Fuentes: azure_sql:...`. Opcional, para contrastar con el acceso directo sin MCP:

```powershell
uv run andes-demo ejecutar --hilo M2 --directo "C-1001 pide 2 EDGE-ORIN a crédito"
```

**Explica:** *"Antes de MCP, cada aplicación tenía su propio acceso a la base y quedaba atada al esquema. Ahora hay un contrato único, de solo lectura, sobre vistas. No expongo `ejecutar_sql`: sería SQL libre. Tampoco expongo aprobar ventas ni modificar límites. Un Resource informa, no autoriza."*

---

## 6. 7:00–8:00 · Fallo controlado: retry técnico vs. regla de negocio sin retry

```powershell
# Fallo TÉCNICO transitorio: 2 fallos simulados, el 3.er intento funciona
$env:SIMULAR_FALLOS_FUENTES = "2"
uv run andes-demo ejecutar --hilo R1
Remove-Item Env:SIMULAR_FALLOS_FUENTES
```

Esperado:

```
  [fallo transitorio simulado] la dependencia no respondió; fallos restantes: 1
  [fallo transitorio simulado] la dependencia no respondió; fallos restantes: 0
  [dependencia recuperada] consulta de fuentes OK tras reintento
== FLUJO PAUSADO · id_hilo=R1 ...
```

Opcional (retry agotado, `max_attempts=3`): con `SIMULAR_FALLOS_FUENTES = "3"` termina en `FalloTransitorio` (error visible, no se oculta).

```powershell
# Regla de NEGOCIO: cliente en hold -> se bloquea a la primera, sin ningún reintento
uv run andes-demo ejecutar --hilo N1 "C-1004 pide 1 EDGE-ORIN a crédito"
uv run andes-demo reanudar --hilo N1 --decision rechazar --aprobador "Ana (Finanzas)" --comentario "Mora vencida"
```

Esperado: motivo `cliente_en_hold`, `RECHAZADA por Ana (Finanzas)`, y **no** se registra liberación. En la traza no hay repeticiones de `consultar_fuentes`.

**Explica:** *"Un timeout o una conexión caída merecen retry porque puede resolverse solo. Un cliente en hold no mejora reintentando: reintentar una regla de negocio solo retrasa y repite efectos."*

---

## 7. 8:00–9:15 · Cambio real de código y efecto predicho

**Predicción (dila antes de ejecutar):** *"Si subo el monto de revisión a 30.000 y dejo mucha holgura en la línea de C-1003, la misma solicitud de 12 EDGE-ORIN (22.200) ya no tendrá excepción y se liberará sola."*

Por qué: con holgura 30.000–38.000, la exposición queda entre 2.000 y 10.000. Sumada a 22.200 no supera el límite (≥ 40.000), y 22.200 < 30.000 ya no activa la revisión.

```powershell
# 0) Respaldo para poder volver atrás
Copy-Item src\andes_agent\config_caso.py $env:TEMP\config_caso.bak
```

Edita [config_caso.py](src/andes_agent/config_caso.py) (dos líneas dentro de `generar_parametros`):

```python
holgura = rng.randint(30_000, 38_000)                    # antes: rng.randint(5_000, 15_000)
...
monto_revision=float(rng.choice([30_000])),              # antes: rng.choice([15_000, 20_000, 25_000])
```

```powershell
# 1) Ver los nuevos parámetros y reaplicarlos a Azure SQL
uv run python -c "from andes_agent.config_caso import imprimir_parametros; imprimir_parametros()"
uv run andes-init-db

# 2) Mismo caso base, hilo nuevo
uv run andes-demo ejecutar --hilo C1
```

Esperado: **ya no se pausa**: `liberada automáticamente`, traza `evaluar_reglas:ok > registrar_liberacion`.

```powershell
# 3) Volver al estado original
Copy-Item $env:TEMP\config_caso.bak src\andes_agent\config_caso.py -Force
uv run andes-init-db
uv run andes-init-db --limpiar-demo
```

**Alternativa rápida (sin reaplicar datos):** en [reglas.py](src/andes_agent/reglas.py) comenta las dos líneas de `monto_requiere_revision` (`if monto >= _d(monto_revision): motivos.append(...)`). Predicción: el caso base sigue pausando (la línea sigue siendo insuficiente) pero el interrupt ya solo muestra `["linea_insuficiente"]`. Revierte con `Ctrl+Z`/respaldo.

---

## 8. 9:15–10:00 · Reflexión

Dilo en este orden (30–45 s):

- **2 trade-offs:**
  1. Checkpointer propio sobre Azure SQL (todo en Azure, sin archivos locales) a cambio de mantener código que no tiene la madurez de los oficiales.
  2. Router híbrido: reglas primero (barato y reproducible) y LLM solo con baja confianza; menos flexible que un LLM puro, pero predecible.
- **1 error propio** (elige uno real): `checkpoint` es palabra reservada de T-SQL y la tabla no se creaba hasta usar `[checkpoint]`; o `mcp>=1.10` sin tope instalaba mcp 2.x y rompía el servidor (corregido con `<2` y `uv.lock`).
- **1 mejora para producción:** autenticar Azure SQL con Microsoft Entra ID / identidad administrada (sin contraseña), y un checkpointer sobre una base con soporte oficial o pruebas de concurrencia.

---

## 9. Pregunta de control: respuestas listas

| Pregunta posible | Respuesta corta |
|---|---|
| ¿Qué se rompe si reanudas con otro `id_hilo`? | No hay estado para ese hilo: el programa responde que no está pausado. El estado y la liberación pertenecen al hilo original. |
| ¿Qué operación NO debería tener retry y por qué? | Las reglas de negocio (hold, línea insuficiente) y la escritura de la liberación sin idempotencia: reintentar no cambia el resultado o duplica efectos. |
| ¿Por qué una Resource MCP no es una autorización? | Solo expone información (la política). Quién puede aprobar lo deciden las reglas y Finanzas/Crédito. |
| ¿Qué campo eliminarías del State? | `evidencia.historial` y los fragmentos completos de política: solo hacen falta la decisión, los motivos y las fuentes. |
| ¿Qué riesgo introduces si una regla objetiva la decide el LLM? | No determinismo: el mismo caso podría liberarse hoy y bloquearse mañana, sin auditoría ni reproducibilidad. |
| ¿Por qué no exponer `ejecutar_sql(sql)`? | Es SQL libre: permite leer o modificar cualquier dato, inyección y saltarse el mínimo privilegio. |

---

## 10. Si algo falla en vivo

| Síntoma | Causa y solución |
|---|---|
| `El hilo 'X' ya existe` | Usaste un `--hilo` repetido. Cambia el nombre o `uv run andes-init-db --limpiar-demo`. |
| `Advertencias: RAG (Qdrant) no disponible` | Qdrant sin acceso (key inválida) o colección sin indexar: `uv run andes-index`. El flujo continúa; solo faltan las citas. |
| `Advertencias: redactor LLM no disponible` | Foundry no responde: revisa `FOUNDRY_CHAT_DEPLOYMENT=gpt-5-mini` y el endpoint `https://azfnd01.openai.azure.com/`. La respuesta sale por plantilla. |
| Error de conexión a Azure SQL | Revisa firewall del servidor (tu IP), que la base no esté pausada (serverless tarda en despertar) y reintenta. |
| `ModuleNotFoundError: mcp.server.fastmcp` | Instaló mcp 2.x: `uv sync --extra dev` (el rango correcto es `mcp>=1.10,<2`). |
| Caracteres raros (`Crédito`) | `chcp 65001` y `$env:PYTHONIOENCODING = "utf-8"`. |

---

## 11. Después de grabar

```powershell
uv run andes-init-db --limpiar-demo
Copy-Item $env:TEMP\config_caso.bak src\andes_agent\config_caso.py -Force   # solo si cambiaste el código
git log --stat > git_log.txt                                                 # regenerar tras tus commits
```

Pega el enlace del video en `VIDEO_LINK.txt` y no incluyas `.env` en la entrega.
