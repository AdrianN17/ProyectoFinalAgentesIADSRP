# Hito 1 · consulta → capacidad esperada → justificación

Caso asignado: **CRE-001 · Crédito · liberación de venta · semilla 7885** (excepción HITL: cliente en *hold* o línea insuficiente; aprobador: Finanzas/Crédito).

## Tabla de decisión (10 solicitudes reales del caso)

| # | Solicitud | Capacidad esperada | Justificación |
|---|---|---|---|
| 1 | "C-1003 solicita liberar la venta de 12 EDGE-ORIN para un proyecto industrial, con pago a crédito y entrega esta semana." | **Workflow**: Tools (stock, crédito, historial, parámetros) + **regla** + posible HITL | Es una decisión de negocio: necesita datos transaccionales y una regla objetiva (`exposición + monto > límite`). La excepción la decide un humano. |
| 2 | "¿Cuánto stock hay de EDGE-ORIN?" | **Tool** `consultar_stock` | Dato transaccional que cambia constantemente; no va en un prompt ni en un documento. No se usa RAG. |
| 3 | "¿Cómo está la línea de crédito de C-1003?" | **Tool** `consultar_estado_credito` | Estado, límite y exposición viven en la base de datos. |
| 4 | "Muéstrame el historial de pagos de C-1004" | **SQL** parametrizado (`consultar_historial_ventas`) | Consulta de ventas históricas: se resuelve con una consulta fija, no con RAG (RAG recupera texto, no agrega filas). |
| 5 | "¿Qué dice la política cuando un cliente está en hold?" | **RAG** | Información documental (política de crédito) con cita de fuente. |
| 6 | "El cliente C-1004 no pagó, ¿qué dice la política de hold?" | **RAG** | Menciona un cliente, pero la pregunta es sobre la política. (Error real del router corregido, ver `EVIDENCIAS.md`.) |
| 7 | "Hola, ¿qué puedes hacer?" | **DIRECT** (ninguna tool) | No requiere ninguna fuente: usar tools sería costo y riesgo sin beneficio. |
| 8 | "Libera la venta de C-1003" | **CLARIFY** | Faltan SKU y cantidad: no se adivina, se pregunta. |
| 9 | "C-9999 pide 2 EDGE-ORIN a crédito" | **Regla** (`datos_invalidos`) | El cliente no existe: el sistema detiene la ejecución de forma segura, sin escalar a Finanzas. |
| 10 | "C-1001 pide 500 EDGE-ORIN a crédito" | **Regla** (`no_liberable`) | Falta de stock: Finanzas no puede resolverlo, se informa en lugar de pausar. |

## Preguntas de razonamiento del hito

**¿Qué decisiones NO necesitan un LLM?**
Todas las objetivas: línea insuficiente (`exposición + monto > límite`), cliente en hold, monto ≥ monto de revisión, stock insuficiente, existencia de cliente/SKU. Son reglas de `reglas.py` y deben ser reproducibles y auditables.

**¿Qué dato cambia frecuentemente y no debería vivir en un prompt?**
Stock, exposición actual, estado de crédito (hold) y pagos vencidos. Se leen de Azure SQL en cada solicitud.

**¿Qué información es documental y qué información es transaccional?**
- Documental (RAG, Qdrant): políticas de crédito, entrega y excepciones (`data/politicas/`).
- Transaccional (SQL/Tools): clientes, inventario, ventas, pagos y liberaciones (esquema `ops` en Azure SQL).
