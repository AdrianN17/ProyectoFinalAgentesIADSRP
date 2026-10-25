-- Tablas del checkpointer de LangGraph en Azure SQL (esquema [lg]).
-- Idempotente y NO destructivo: no borra checkpoints existentes (a diferencia de 01_schema.sql).
-- Las columnas de clave usan colación binaria para que ORDER BY checkpoint_id respete el orden
-- cronológico de los UUID v6 (las colaciones normales ignoran los guiones al ordenar).

IF SCHEMA_ID('lg') IS NULL EXEC('CREATE SCHEMA lg');
GO

IF OBJECT_ID('lg.checkpoints', 'U') IS NULL
CREATE TABLE lg.checkpoints (
    thread_id            NVARCHAR(100) COLLATE Latin1_General_100_BIN2 NOT NULL,
    checkpoint_ns        NVARCHAR(100) COLLATE Latin1_General_100_BIN2 NOT NULL CONSTRAINT df_lgcp_ns DEFAULT N'',
    checkpoint_id        NVARCHAR(50)  COLLATE Latin1_General_100_BIN2 NOT NULL,
    parent_checkpoint_id NVARCHAR(50)  COLLATE Latin1_General_100_BIN2 NULL,
    type                 NVARCHAR(50)  NULL,
    [checkpoint]         VARBINARY(MAX) NULL,
    metadata             NVARCHAR(MAX) NULL,
    creado_en            DATETIME2(0)  NOT NULL CONSTRAINT df_lgcp_creado DEFAULT SYSUTCDATETIME(),
    CONSTRAINT pk_lg_checkpoints PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);
GO

IF OBJECT_ID('lg.writes', 'U') IS NULL
CREATE TABLE lg.writes (
    thread_id     NVARCHAR(100) COLLATE Latin1_General_100_BIN2 NOT NULL,
    checkpoint_ns NVARCHAR(100) COLLATE Latin1_General_100_BIN2 NOT NULL CONSTRAINT df_lgw_ns DEFAULT N'',
    checkpoint_id NVARCHAR(50)  COLLATE Latin1_General_100_BIN2 NOT NULL,
    task_id       NVARCHAR(50)  COLLATE Latin1_General_100_BIN2 NOT NULL,
    task_path     NVARCHAR(500) NOT NULL CONSTRAINT df_lgw_path DEFAULT N'',
    idx           INT           NOT NULL,
    channel       NVARCHAR(200) NOT NULL,
    type          NVARCHAR(50)  NULL,
    value         VARBINARY(MAX) NULL,
    CONSTRAINT pk_lg_writes PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);
GO
