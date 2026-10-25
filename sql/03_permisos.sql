-- Permisos de mínimo privilegio (plantilla, NO la ejecuta init_db.py).
-- Ejecutar conectado a la base de datos como administrador Entra ID.
-- Sustituye los nombres entre corchetes por las identidades reales
-- (usuario, grupo o identidad administrada del recurso que ejecute cada proceso).

IF DATABASE_PRINCIPAL_ID('rol_mcp_lectura') IS NULL CREATE ROLE rol_mcp_lectura;
IF DATABASE_PRINCIPAL_ID('rol_agente_liberaciones') IS NULL CREATE ROLE rol_agente_liberaciones;
GO

-- El servidor MCP solo lee vistas y el parámetro de revisión.
GRANT SELECT ON ops.v_stock            TO rol_mcp_lectura;
GRANT SELECT ON ops.v_estado_credito   TO rol_mcp_lectura;
GRANT SELECT ON ops.v_ventas_cliente   TO rol_mcp_lectura;
GRANT SELECT ON ops.v_pagos_cliente    TO rol_mcp_lectura;
GRANT SELECT ON ops.parametros_caso    TO rol_mcp_lectura;
GO

-- El agente solo puede registrar y consultar liberaciones; nunca modifica límites ni stock.
GRANT SELECT, INSERT ON ops.liberaciones TO rol_agente_liberaciones;
GRANT SELECT ON ops.v_stock          TO rol_agente_liberaciones;
GRANT SELECT ON ops.v_estado_credito TO rol_agente_liberaciones;
GRANT SELECT ON ops.v_ventas_cliente TO rol_agente_liberaciones;
GRANT SELECT ON ops.v_pagos_cliente  TO rol_agente_liberaciones;
GRANT SELECT ON ops.parametros_caso  TO rol_agente_liberaciones;

-- Checkpointer de LangGraph (estado de los hilos pausados).
GRANT SELECT, INSERT, UPDATE, DELETE ON lg.checkpoints TO rol_agente_liberaciones;
GRANT SELECT, INSERT, UPDATE, DELETE ON lg.writes      TO rol_agente_liberaciones;
GO

-- Ejemplos (descomentar y ajustar):
-- CREATE USER [agente-mcp@tu-tenant.onmicrosoft.com] FROM EXTERNAL PROVIDER;
-- ALTER ROLE rol_mcp_lectura ADD MEMBER [agente-mcp@tu-tenant.onmicrosoft.com];
-- CREATE USER [mi-app-identidad-administrada] FROM EXTERNAL PROVIDER;
-- ALTER ROLE rol_agente_liberaciones ADD MEMBER [mi-app-identidad-administrada];
