# AI Operations Agent · CRE-001 (Crédito) · semilla 7885

Agente de liberación de ventas a crédito sobre **Azure AI Foundry** (chat + embeddings), **Azure SQL** (datos de negocio), **Qdrant** (RAG de políticas), **LangGraph** (workflow con HITL) y **MCP** stdio (capacidades de solo lectura).

## Requisitos
- Python 3.11+, [ODBC Driver 18 for SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server)
- Azure: base Azure SQL y un recurso Azure AI Foundry con 2 deployments (chat, p. ej. `gpt-5-mini`; embeddings, p. ej. `text-embedding-3-small`). `AZURE_OPENAI_ENDPOINT` es el endpoint **del recurso** (`https://<recurso>.openai.azure.com/`), no el del proyecto.
- Qdrant: Qdrant Cloud (`QDRANT_URL` + `QDRANT_API_KEY`) o local con `docker run -p 6333:6333 qdrant/qdrant`
- Autenticación: `az login` (Microsoft Entra ID por `DefaultAzureCredential`) o claves/usuario SQL en `.env`. **No subas `.env` al repositorio.**

## Puesta en marcha
```powershell
uv sync --extra dev          # o: python -m venv .venv; .venv\Scripts\activate; pip install -e ".[dev]"
copy .env.example .env       # completar endpoints y deployments
uv run andes-init-db         # esquema ops + datos de prueba + parámetros de la semilla en Azure SQL
uv run andes-index           # embeddings en Foundry -> colección en Qdrant
```
Opcional: ejecutar `sql\03_permisos.sql` para crear los roles de mínimo privilegio.

## Demo
```powershell
uv run andes-demo ejecutar --hilo H1                                   # caso base: se pausa (HITL)
uv run andes-demo reanudar --hilo H1 --decision aprobar --aprobador "Ana (Finanzas)"
uv run andes-demo reanudar --hilo H1 --decision rechazar               # (en otro hilo pausado)
uv run andes-demo ejecutar --hilo H2 "C-1001 pide 2 EDGE-ORIN a crédito"   # ruta directa
uv run andes-mcp-cliente                                               # cliente MCP puro, sin LLM
```
- `SIMULAR_FALLOS_FUENTES=2` en `.env` provoca 2 fallos transitorios y muestra el `RetryPolicy`.
- `USE_LLM=false` desactiva Foundry para el chat (router por reglas, respuesta por plantilla).
- `--directo` consulta Azure SQL sin pasar por MCP. El recorrido lo indica en `[consultar_fuentes] canal de acceso: ...` (MCP por stdio o acceso directo a Azure SQL).
- `ejecutar` y `reanudar` imprimen el recorrido del grafo nodo por nodo (`[paso n] nodo '...' terminado`); `--sin-progreso` lo oculta.
- Cada `ejecutar` necesita un `--hilo` nuevo; `uv run andes-init-db --limpiar-demo` borra liberaciones e hilos de demos anteriores.
- Guion completo de comandos para el video: [GUIA_EXPOSICION.md](./GUIA_EXPOSICION.md).

## Pruebas
```powershell
uv run pytest        # 77 pruebas; no requieren Azure ni Qdrant (conexiones simuladas, Qdrant en memoria, servidor MCP de prueba por stdio)
```

## Estructura
| Ruta | Contenido |
|---|---|
| `sql/` | `01_schema.sql` (tablas + vistas), `02_seed.sql` (datos), `03_permisos.sql` (roles), `04_checkpoints.sql` (tablas del checkpointer) |
| `data/politicas/` | 3 documentos de política para RAG |
| `src/andes_agent/` | `config_caso`, `reglas`, `router`, `rag`, `db`, `foundry`, `graph`, `checkpointer`, `mcp_server`, `mcp_client`, `demo`… |
| `tests/` | reglas, router (14 casos), RAG, SQL, workflow, checkpointer, MCP y agente-MCP |
| `docs/` | `consulta_capacidad.md` (Hito 1), `arquitectura.md` (incluye antes/después de MCP), `workflow_state.md` (diagrama y State) |
| `HITOS.md`, `EVIDENCIAS.md`, `DECISIONES.md`, `USO_IA.md` | documentación del proceso |
| `CHECKLIST.md` | validación contra el checklist del PDF |

## Diagramas de secuencia por caso

Los diagramas usan Mermaid (se ven en GitHub o en VS Code con una extensión de Mermaid). Cada caso indica el comando que lo ejecuta. Participantes comunes:

- **CLI** = `andes-demo` · **Grafo** = LangGraph (`graph.py`) · **Router** = `router.py`
- **MCP** = servidor MCP de solo lectura (subproceso por stdio) · **SQL** = Azure SQL (`ops.*`)
- **Qdrant** = RAG de políticas · **Foundry** = Azure AI Foundry (embeddings y `gpt-5-mini`)
- **Checkpoints** = tablas `lg.*` de Azure SQL, donde LangGraph guarda el estado tras cada nodo

| # | Caso | Ejemplo | Destino del router |
|---|---|---|---|
| 1 | Arranque y errores de hilo | `ejecutar --hilo A1 ...` | (común a todos) |
| 2 | Sin fuentes: saludo, aclaración, baja confianza | `"Hola, ¿qué puedes hacer?"`, `"Libera la venta de C-1003"`, `"necesito algo urgente"` | `DIRECT` / `CLARIFY` |
| 3 | Consulta informativa con tools o SQL | `"¿Cuánto stock hay de EDGE-ORIN?"` | `TOOLS` / `SQL` |
| 4 | Política con RAG | `"¿Qué dice la política cuando un cliente está en hold?"` | `RAG` |
| 5 | Liberación automática | `"C-1001 pide 2 EDGE-ORIN a crédito"` | `TOOLS` (liberación) |
| 6 | Excepción: pausa (HITL) | caso base, `"C-1004 pide 1 EDGE-ORIN a crédito"` | `TOOLS` (liberación) |
| 7 | Reanudación: aprobar, rechazar o error | `reanudar --hilo H1 --decision ...` | (continúa el hilo) |
| 8 | Sin escalar: datos inválidos o stock insuficiente | `"C-9999 pide 2 EDGE-ORIN"`, `"C-1001 pide 500 EDGE-ORIN"` | `TOOLS` (liberación) |
| 9 | Fallos técnicos: retry y degradación | `SIMULAR_FALLOS_FUENTES=2` | (cualquiera con fuentes) |

### 1. Arranque y errores de hilo
```mermaid
sequenceDiagram
    autonumber
    actor U as Analista
    participant C as CLI
    participant K as Checkpoints
    participant G as Grafo

    U->>C: ejecutar --hilo A1 "solicitud"
    C->>K: get_state(thread_id = A1)
    alt el hilo ya existe
        K-->>C: estado guardado
        C-->>U: "El hilo A1 ya existe. Usa otro --hilo"
    else hilo nuevo
        C-->>U: imprime CRE-001 · semilla 7885 y sus 5 parámetros
        C->>G: stream({solicitud, id_hilo = A1})
        Note over G,K: tras cada nodo LangGraph guarda un checkpoint
        G-->>C: un evento por nodo terminado
        C-->>U: [paso n] nodo '...' terminado
    end
```

### 2. Sin fuentes: saludo, aclaración y baja confianza
```mermaid
sequenceDiagram
    autonumber
    participant G as Grafo
    participant R as Router
    participant F as Foundry
    participant C as CLI
    actor U as Analista

    G->>G: parsear_solicitud (regex: cliente, SKU, cantidad)
    G->>R: decidir(solicitud, datos extraídos)
    alt reglas con confianza alta (>= 0.6)
        R-->>G: DIRECT (saludo) o CLARIFY (faltan SKU o cantidad)
    else confianza baja y USE_LLM=true
        R->>F: salida estructurada SalidaRouter
        F-->>R: destino, intención, confianza
        R->>R: valida confianza >= 0.6 y datos completos
        alt la validación pasa
            R-->>G: ruta propuesta por el modelo
        else no pasa
            R-->>G: CLARIFY
        end
    else confianza baja y sin LLM
        R-->>G: CLARIFY
    end
    Note over G: tras_enrutar: DIRECT o CLARIFY van directo a responder (sin tools, SQL ni RAG)
    G->>G: responder (plantilla: "Necesito más información..." o lista de capacidades)
    G-->>C: respuesta + Trazabilidad
    C-->>U: == RESPUESTA ==
```

### 3. Consulta informativa con tools o SQL (stock, crédito, historial)
```mermaid
sequenceDiagram
    autonumber
    participant G as Grafo
    participant R as Router
    participant M as MCP (stdio)
    participant S as SQL
    participant C as CLI
    actor U as Analista

    G->>R: decidir(solicitud)
    R-->>G: TOOLS/stock · TOOLS/credito · SQL/historial (confianza 0.85)
    Note over G: consultar_fuentes (nodo con RetryPolicy)
    G->>M: lanza el subproceso y llama la tool (consultar_stock, consultar_estado_credito o consultar_historial_ventas)
    M->>M: valida el formato de la entrada (C-#### o SKU)
    M->>S: SELECT ... FROM vista WHERE clave = ? (parametrizada)
    S-->>M: fila
    M-->>G: JSON con "fuente"
    Note over G: tras_fuentes: la intención no es liberación, va directo a responder
    G->>G: responder (plantilla, sin LLM, sin RAG)
    G-->>C: respuesta + Fuentes + Trazabilidad
    C-->>U: == RESPUESTA ==
```

### 4. Política con RAG
```mermaid
sequenceDiagram
    autonumber
    participant G as Grafo
    participant R as Router
    participant F as Foundry
    participant Q as Qdrant
    participant C as CLI
    actor U as Analista

    G->>R: decidir(solicitud)
    R-->>G: RAG/politica (confianza 0.80)
    Note over G: consultar_fuentes (sin tools de negocio)
    G->>F: embedding de la consulta
    F-->>G: vector
    G->>Q: búsqueda por similitud (k = 2, umbral 0.35)
    alt Qdrant responde
        Q-->>G: fragmentos con archivo y sección
        G->>G: responder: texto del fragmento + "Fuentes: archivo · sección"
    else Qdrant falla
        Q--xG: error
        G->>G: advertencia "RAG (Qdrant) no disponible" y responde sin cita
    end
    G-->>C: respuesta + Fuentes + Trazabilidad
    C-->>U: == RESPUESTA ==
```

### 5. Liberación automática (sin excepción)
```mermaid
sequenceDiagram
    autonumber
    participant G as Grafo
    participant M as MCP (stdio)
    participant S as SQL
    participant F as Foundry
    participant Q as Qdrant
    participant C as CLI
    actor U as Analista

    G->>G: enrutar: TOOLS/liberación (reglas, 0.90, sin LLM)
    Note over G: consultar_fuentes (con RetryPolicy)
    G->>M: 4 tools en una sesión: stock, estado de crédito, historial, parámetros
    M->>S: 4 consultas parametrizadas sobre vistas ops.v_*
    S-->>M: filas
    M-->>G: 4 JSON con "fuente"
    G->>F: embedding de la consulta de política
    G->>Q: búsqueda (k = 2, umbral 0.35)
    Q-->>G: fragmentos citables
    G->>G: evaluar_reglas (Python puro): resultado = ok
    Note over G: tras_reglas: ok va a registrar_liberacion
    G->>S: INSERT en ops.liberaciones (aprobador REGLAS_AUTOMATICAS)
    Note over G,S: idempotente: si existe el id_hilo no inserta, y hay UNIQUE(id_hilo)
    G->>F: salida estructurada RespuestaLiberacion
    F-->>G: estado, aprobador, monto, mensaje
    G->>G: validar_respuesta contra los hechos
    alt coincide
        G->>G: usa el mensaje del LLM y añade "(liberación #N)"
    else no coincide o el LLM falla
        G->>G: usa la plantilla y agrega una advertencia
    end
    G-->>C: respuesta + Fuentes + Trazabilidad
    C-->>U: "liberada automáticamente"
```

### 6. Excepción: el flujo se pausa (HITL)
Ocurre con cliente en hold, línea insuficiente o monto ≥ monto de revisión.
```mermaid
sequenceDiagram
    autonumber
    participant G as Grafo
    participant M as MCP (stdio)
    participant S as SQL
    participant K as Checkpoints
    participant C as CLI
    actor U as Analista

    G->>M: consultar_fuentes (4 tools) y RAG, igual que en el caso 5
    M->>S: consultas parametrizadas
    S-->>G: stock, crédito, historial y parámetros
    G->>G: evaluar_reglas: resultado = excepción, motivos [linea_insuficiente, monto_requiere_revision, cliente_en_hold]
    Note over G: tras_reglas: excepción va a aprobacion_humana
    G->>G: aprobacion_humana: sin efectos secundarios antes del interrupt()
    G->>K: guarda el checkpoint del hilo (id_hilo)
    G-->>C: __interrupt__ con cliente, SKU, cantidad, monto y motivos
    C-->>U: == FLUJO PAUSADO · id_hilo=H1 · esperando a Finanzas/Crédito ==
    Note over C,K: el proceso termina, el estado queda en Azure SQL y no se escribió ninguna liberación
```

### 7. Reanudación: aprobar, rechazar o error
```mermaid
sequenceDiagram
    autonumber
    actor H as Finanzas/Crédito
    participant C as CLI
    participant K as Checkpoints
    participant G as Grafo
    participant S as SQL
    participant F as Foundry

    H->>C: reanudar --hilo H1 --decision aprobar o rechazar --aprobador "Ana"
    C->>K: get_state(thread_id = H1)
    alt el hilo no existe, ya terminó o es otro id_hilo
        K-->>C: sin nodos pendientes
        C-->>H: "El hilo no está pausado (no existe o ya terminó)"
    else el hilo está pausado
        C->>G: stream(Command(resume = {aprobado, aprobador, comentario}))
        G->>K: carga el checkpoint de H1
        G->>G: aprobacion_humana se ejecuta de nuevo desde el inicio, interrupt() devuelve la decisión
        alt aprobada
            Note over G: tras_aprobacion: va a registrar_liberacion
            G->>S: INSERT en ops.liberaciones (aprobador = Ana), idempotente
            S-->>G: liberacion_id
        else rechazada
            Note over G: tras_aprobacion: va directo a responder, sin escribir en la base
        end
        G->>F: redacción estructurada RespuestaLiberacion (validada, o plantilla)
        F-->>G: estado, aprobador, monto, mensaje
        G->>G: responder
        G-->>C: respuesta + Trazabilidad
        C-->>H: "liberada tras aprobación de Ana" o "RECHAZADA por Ana"
    end
```

### 8. Sin escalar: datos inválidos o stock insuficiente
```mermaid
sequenceDiagram
    autonumber
    participant G as Grafo
    participant M as MCP (stdio)
    participant S as SQL
    participant C as CLI
    actor U as Analista

    G->>M: consultar_fuentes (4 tools)
    M->>S: consultas parametrizadas
    S-->>G: encontrado = false (cliente o SKU) o stock menor a la cantidad
    G->>G: evaluar_reglas (Python puro)
    alt cliente o SKU inexistente, o cantidad inválida
        G->>G: resultado = datos_invalidos
    else stock menor a la cantidad pedida
        G->>G: resultado = no_liberable (Finanzas no puede resolver falta de stock)
    end
    Note over G: tras_reglas: ambos van directo a responder, sin HITL y sin escribir
    G->>G: responder (plantilla o LLM validado)
    G-->>C: "No se puede evaluar: el cliente no existe" o "NO liberable: no hay stock suficiente"
    C-->>U: == RESPUESTA ==
```

### 9. Fallos técnicos: retry y degradación
```mermaid
sequenceDiagram
    autonumber
    participant G as Grafo
    participant M as MCP (stdio)
    participant S as SQL
    participant Q as Qdrant

    Note over G: consultar_fuentes tiene RetryPolicy (3 intentos, solo para FalloTransitorio)
    G->>M: llamar tools
    M--xG: fallo transitorio (conexión, timeout, Azure SQL despertando o subproceso caído)
    G->>G: espera y reintenta el nodo (intento 2 de 3)
    alt la dependencia se recupera
        G->>M: llamar tools
        M->>S: consultas parametrizadas
        S-->>G: datos, el flujo continúa
    else se agotan los 3 intentos
        G-->>G: el error FalloTransitorio sale al CLI (visible, el estado previo queda en el checkpoint)
    end
    Note over G: una regla de negocio incumplida (hold, línea) NO se reintenta: evaluar_reglas va a aprobacion_humana
    G->>Q: búsqueda de política
    Q--xG: error (por ejemplo 403)
    G->>G: no es un fallo de negocio: agrega la advertencia y continúa sin citas
```

## Notas de diseño
- Las reglas de crédito son Python determinista; el LLM solo enruta (con validación posterior) y redacta.
- El servidor MCP solo lee **vistas** (`ops.v_*`); la única escritura (`ops.liberaciones`) la hace el agente después del `interrupt()` y es idempotente por `UNIQUE(id_hilo)`.
- El estado de los hilos pausados (checkpoints de LangGraph) vive en Azure SQL, esquema `lg` (`sql/04_checkpoints.sql`), mediante `AzureSqlSaver` (`checkpointer.py`). Así `ejecutar` y `reanudar` funcionan desde cualquier máquina o instancia, sin archivos locales.
- Si ya habías ejecutado `andes-init-db` antes de este cambio, crea solo las tablas nuevas con `andes-init-db --solo-checkpoints` (no borra datos).
