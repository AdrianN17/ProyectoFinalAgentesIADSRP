# Arquitectura · AI Operations Agent · CRE-001 (Crédito) · semilla 7885

## 1. Vista general

```mermaid
flowchart TB
    U["Analista de ventas<br/>(lenguaje natural)"] --> LG

    subgraph APP["Proceso 1 · agente (andes-demo)"]
        direction TB
        CFG["config_caso<br/>CRE-001 · semilla 7885"]
        ROUTER{{"Router híbrido<br/>reglas + Foundry (baja confianza)<br/>RAG · SQL · TOOLS · CLARIFY · DIRECT"}}
        LG["LangGraph · workflow con estado"]
        REGLAS["reglas.py<br/>(Python determinista)"]
        RED["Redactor<br/>(plantilla + Foundry opcional)"]
        LG --- ROUTER
        LG --> REGLAS
        LG --> RED
    end

    subgraph MCP["Proceso 2 · servidor MCP (stdio) · solo lectura"]
        T["Tools: consultar_stock<br/>consultar_estado_credito<br/>consultar_historial_ventas<br/>consultar_parametros_credito"]
        R["Resource: politica://credito"]
    end

    FOUNDRY["Azure AI Foundry<br/>gpt-5-mini · text-embedding-3-small"]
    QDRANT[("Qdrant Cloud<br/>políticas (3 docs, 12 fragmentos)")]
    SQL[("Azure SQL<br/>ops.* (negocio) · lg.* (checkpoints)")]
    HUMAN["Finanzas / Crédito<br/>(aprobador HITL)"]
    CLI["Cliente MCP puro (sin LLM)"]

    ROUTER -. "solo con baja confianza" .-> FOUNDRY
    RED -. "opcional" .-> FOUNDRY
    LG -- "embeddings + búsqueda" --> QDRANT
    QDRANT -. "vectores generados con" .-> FOUNDRY
    LG -- "tools vía MCP" --> T
    T -- "vistas ops.v_*" --> SQL
    LG -- "INSERT idempotente tras aprobación" --> SQL
    LG <-- "checkpoint por id_hilo" --> SQL
    LG <-. "interrupt / resume" .-> HUMAN
    CLI --> T
    CLI --> R
```

## 2. Qué decide cada componente

| Componente | Tipo de decisión | Detalle |
|---|---|---|
| `reglas.py` | **Determinista** | línea insuficiente, hold, monto ≥ monto de revisión, stock, datos inválidos. Nunca el LLM. |
| Router | **Semántica** | Reglas primero; Foundry solo con confianza < 0.6, con salida validada (Pydantic) y comprobación de datos completos. |
| LangGraph | **Proceso** | qué nodo sigue, qué estado persiste, pausa y reanudación. |
| MCP | **Integración** | stock, crédito, historial y política como capacidades reutilizables y de solo lectura. |
| Redactor (Foundry) | Probabilístico | redacta el mensaje de las liberaciones con salida estructurada; el código valida estado, aprobador y monto y, si no coinciden, usa la plantilla. No controla ramas ni decisiones. |

## 3. Antes / después de MCP

```mermaid
flowchart LR
    subgraph ANTES["ANTES: acoplado"]
        A1["Agente"] --> DB1[("Azure SQL")]
        A2["App Ventas"] --> DB1
        A3["App Logística"] --> DB1
    end
    subgraph DESPUES["DESPUÉS: desacoplado con MCP"]
        B1["Agente"] --> S["Servidor MCP<br/>(Tools + Resource, solo lectura)"]
        B2["Cliente MCP puro"] --> S
        B3["Ventas / Logística"] --> S
        S --> DB2[("Azure SQL<br/>vistas ops.v_*")]
    end
```

- **Antes:** cada consumidor repite el acceso a la base y queda atado al esquema.
- **Después:** un contrato único, de mínimo privilegio, reutilizable por cualquier cliente MCP.

### Qué se expone por MCP y qué no

| Se expone (solo lectura, acotado) | NO se expone |
|---|---|
| `consultar_stock(sku)` | `ejecutar_sql(sql)` (SQL libre) |
| `consultar_estado_credito(cliente_id)` | Aprobar o liberar ventas (decisión humana + reglas) |
| `consultar_historial_ventas(cliente_id)` | Modificar límites de crédito |
| `consultar_parametros_credito()` | Datos de otros clientes sin necesidad |
| Resource `politica://credito` | |

> Un *Resource* informa, no autoriza: la autorización sigue siendo de las reglas y del aprobador humano.

## 4. Pausa y reanudación (HITL)

```mermaid
sequenceDiagram
    autonumber
    actor V as Analista
    participant G as Grafo LangGraph
    participant M as Servidor MCP
    participant K as Checkpoints (Azure SQL · lg.*)
    actor F as Finanzas/Crédito

    V->>G: "C-1003 solicita liberar 12 EDGE-ORIN" (id_hilo=H1)
    G->>M: call_tool stock / crédito / historial / parámetros
    M-->>G: datos con fuente
    G->>G: evaluar_reglas (Python): línea insuficiente
    G->>K: checkpoint (H1)
    G-->>V: FLUJO PAUSADO
    F->>G: reanudar(H1, aprobar/rechazar)
    G->>K: carga estado de H1
    G->>G: registrar_liberacion (idempotente) o rechazo
    G-->>V: respuesta final + fuentes + trazabilidad
```

El diagrama del workflow y la explicación del State están en [workflow_state.md](./workflow_state.md).
