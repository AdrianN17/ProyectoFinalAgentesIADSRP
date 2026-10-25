-- Esquema Azure SQL · AndesSupply · caso CRE-001 (Crédito)
-- Re-ejecutable: elimina y recrea los objetos del esquema [ops].
-- Los lotes se separan con GO (src/andes_agent/init_db.py los ejecuta uno a uno).

IF SCHEMA_ID('ops') IS NULL EXEC('CREATE SCHEMA ops');
GO

DROP VIEW  IF EXISTS ops.v_stock;
DROP VIEW  IF EXISTS ops.v_estado_credito;
DROP VIEW  IF EXISTS ops.v_ventas_cliente;
DROP VIEW  IF EXISTS ops.v_pagos_cliente;
DROP TABLE IF EXISTS ops.liberaciones;
DROP TABLE IF EXISTS ops.pagos;
DROP TABLE IF EXISTS ops.venta_items;
DROP TABLE IF EXISTS ops.ventas;
DROP TABLE IF EXISTS ops.inventario;
DROP TABLE IF EXISTS ops.productos;
DROP TABLE IF EXISTS ops.clientes;
DROP TABLE IF EXISTS ops.parametros_caso;
GO

CREATE TABLE ops.parametros_caso (
    clave      VARCHAR(50)   NOT NULL CONSTRAINT pk_parametros_caso PRIMARY KEY,
    valor      NVARCHAR(100) NOT NULL,
    actualizado_en DATETIME2(0) NOT NULL CONSTRAINT df_param_act DEFAULT SYSUTCDATETIME()
);

CREATE TABLE ops.clientes (
    cliente_id        VARCHAR(10)   NOT NULL CONSTRAINT pk_clientes PRIMARY KEY,
    nombre            NVARCHAR(120) NOT NULL,
    segmento          VARCHAR(30)   NOT NULL,
    estado_credito    VARCHAR(10)   NOT NULL,
    limite_credito    DECIMAL(14,2) NOT NULL,
    exposicion_actual DECIMAL(14,2) NOT NULL,
    plazo_dias        INT           NOT NULL,
    creado_en         DATETIME2(0)  NOT NULL CONSTRAINT df_clientes_creado DEFAULT SYSUTCDATETIME(),
    CONSTRAINT ck_clientes_estado CHECK (estado_credito IN ('activo', 'hold')),
    CONSTRAINT ck_clientes_limite CHECK (limite_credito >= 0 AND exposicion_actual >= 0)
);

CREATE TABLE ops.productos (
    sku             VARCHAR(20)   NOT NULL CONSTRAINT pk_productos PRIMARY KEY,
    nombre          NVARCHAR(120) NOT NULL,
    categoria       VARCHAR(40)   NOT NULL,
    precio_unitario DECIMAL(12,2) NOT NULL,
    lead_time_dias  INT           NOT NULL,
    CONSTRAINT ck_productos_precio CHECK (precio_unitario > 0)
);

CREATE TABLE ops.inventario (
    sku              VARCHAR(20)  NOT NULL CONSTRAINT pk_inventario PRIMARY KEY,
    stock_disponible INT          NOT NULL,
    stock_reservado  INT          NOT NULL CONSTRAINT df_inv_res DEFAULT 0,
    actualizado_en   DATETIME2(0) NOT NULL CONSTRAINT df_inv_act DEFAULT SYSUTCDATETIME(),
    CONSTRAINT fk_inventario_producto FOREIGN KEY (sku) REFERENCES ops.productos (sku),
    CONSTRAINT ck_inventario_stock CHECK (stock_disponible >= 0 AND stock_reservado >= 0)
);

CREATE TABLE ops.ventas (
    venta_id       INT           NOT NULL CONSTRAINT pk_ventas PRIMARY KEY,
    cliente_id     VARCHAR(10)   NOT NULL,
    fecha          DATE          NOT NULL,
    total          DECIMAL(14,2) NOT NULL,
    estado         VARCHAR(15)   NOT NULL,
    condicion_pago VARCHAR(20)   NOT NULL,
    CONSTRAINT fk_ventas_cliente FOREIGN KEY (cliente_id) REFERENCES ops.clientes (cliente_id),
    CONSTRAINT ck_ventas_estado CHECK (estado IN ('pendiente', 'liberada', 'facturada'))
);
CREATE INDEX ix_ventas_cliente_fecha ON ops.ventas (cliente_id, fecha DESC);

CREATE TABLE ops.venta_items (
    venta_id        INT           NOT NULL,
    sku             VARCHAR(20)   NOT NULL,
    cantidad        INT           NOT NULL,
    precio_unitario DECIMAL(12,2) NOT NULL,
    CONSTRAINT pk_venta_items PRIMARY KEY (venta_id, sku),
    CONSTRAINT fk_items_venta FOREIGN KEY (venta_id) REFERENCES ops.ventas (venta_id),
    CONSTRAINT fk_items_producto FOREIGN KEY (sku) REFERENCES ops.productos (sku),
    CONSTRAINT ck_items_cantidad CHECK (cantidad > 0)
);

CREATE TABLE ops.pagos (
    pago_id           INT           NOT NULL CONSTRAINT pk_pagos PRIMARY KEY,
    venta_id          INT           NOT NULL,
    cliente_id        VARCHAR(10)   NOT NULL,
    monto             DECIMAL(14,2) NOT NULL,
    fecha_vencimiento DATE          NOT NULL,
    fecha_pago        DATE          NULL,
    estado            VARCHAR(10)   NOT NULL,
    CONSTRAINT fk_pagos_venta FOREIGN KEY (venta_id) REFERENCES ops.ventas (venta_id),
    CONSTRAINT fk_pagos_cliente FOREIGN KEY (cliente_id) REFERENCES ops.clientes (cliente_id),
    CONSTRAINT ck_pagos_estado CHECK (estado IN ('pagado', 'pendiente', 'vencido'))
);
CREATE INDEX ix_pagos_cliente ON ops.pagos (cliente_id, fecha_vencimiento DESC);

-- Registro de liberaciones: el UNIQUE sobre id_hilo hace idempotente la escritura
-- posterior al interrupt() (reanudar dos veces no duplica la liberación).
CREATE TABLE ops.liberaciones (
    liberacion_id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_liberaciones PRIMARY KEY,
    id_hilo       VARCHAR(100)  NOT NULL CONSTRAINT uq_liberaciones_hilo UNIQUE,
    cliente_id    VARCHAR(10)   NOT NULL,
    sku           VARCHAR(20)   NOT NULL,
    cantidad      INT           NOT NULL,
    monto         DECIMAL(14,2) NOT NULL,
    aprobado_por  NVARCHAR(100) NOT NULL,
    motivos       NVARCHAR(400) NULL,
    creada_en     DATETIME2(0)  NOT NULL CONSTRAINT df_lib_creada DEFAULT SYSUTCDATETIME(),
    CONSTRAINT fk_lib_cliente FOREIGN KEY (cliente_id) REFERENCES ops.clientes (cliente_id),
    CONSTRAINT fk_lib_producto FOREIGN KEY (sku) REFERENCES ops.productos (sku)
);
GO

-- Vistas de solo lectura: es lo único que consume el servidor MCP (mínimo privilegio).
CREATE VIEW ops.v_stock AS
SELECT p.sku, p.nombre, p.precio_unitario, p.lead_time_dias,
       i.stock_disponible, i.stock_reservado
FROM ops.productos p
JOIN ops.inventario i ON i.sku = p.sku;
GO

CREATE VIEW ops.v_estado_credito AS
SELECT cliente_id, nombre, estado_credito, limite_credito, exposicion_actual,
       limite_credito - exposicion_actual AS credito_disponible,
       plazo_dias
FROM ops.clientes;
GO

CREATE VIEW ops.v_ventas_cliente AS
SELECT venta_id, cliente_id, fecha, total, estado, condicion_pago
FROM ops.ventas;
GO

CREATE VIEW ops.v_pagos_cliente AS
SELECT pago_id, venta_id, cliente_id, monto, fecha_vencimiento, fecha_pago, estado
FROM ops.pagos;
GO
