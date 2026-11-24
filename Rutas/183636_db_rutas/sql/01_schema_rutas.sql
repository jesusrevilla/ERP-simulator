-- ============================================================================
-- Issue #249 - Esquema Relacional de Rutas Operativas (PostgreSQL)
-- Matrícula: 183636
-- ============================================================================

DROP TABLE IF EXISTS auditoria_rutas CASCADE;
DROP TABLE IF EXISTS ruta_operaciones CASCADE;
DROP TABLE IF EXISTS rutas CASCADE;
DROP TABLE IF EXISTS estaciones_trabajo CASCADE;

-- 1. Catálogo de Estaciones de Trabajo
CREATE TABLE estaciones_trabajo (
    estacion_id SERIAL PRIMARY KEY,
    codigo VARCHAR(20) NOT NULL UNIQUE,
    nombre VARCHAR(100) NOT NULL,
    capacidad_diaria_min INT NOT NULL CHECK (capacidad_diaria_min > 0),
    costo_por_hora NUMERIC(10, 2) NOT NULL CHECK (costo_por_hora > 0),
    estado VARCHAR(20) NOT NULL DEFAULT 'ACTIVA' CHECK (estado IN ('ACTIVA', 'MANTENIMIENTO', 'INACTIVA'))
);

-- 2. Encabezado de Rutas Operativas
CREATE TABLE rutas (
    ruta_id SERIAL PRIMARY KEY,
    codigo_ruta VARCHAR(30) NOT NULL UNIQUE,
    producto_sku VARCHAR(50) NOT NULL,
    version VARCHAR(10) NOT NULL DEFAULT '1.0',
    tiempo_total_estimado_min INT NOT NULL DEFAULT 0 CHECK (tiempo_total_estimado_min >= 0),
    activa BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 3. Detalle de Operaciones por Ruta
CREATE TABLE ruta_operaciones (
    operacion_id SERIAL PRIMARY KEY,
    ruta_id INT NOT NULL REFERENCES rutas(ruta_id) ON DELETE CASCADE,
    estacion_id INT NOT NULL REFERENCES estaciones_trabajo(estacion_id),
    numero_secuencia INT NOT NULL CHECK (numero_secuencia > 0),
    nombre_operacion VARCHAR(120) NOT NULL,
    tiempo_setup_min INT NOT NULL DEFAULT 0 CHECK (tiempo_setup_min >= 0),
    tiempo_ejecucion_min INT NOT NULL CHECK (tiempo_ejecucion_min > 0),
    CONSTRAINT uq_ruta_secuencia UNIQUE (ruta_id, numero_secuencia)
);

-- 4. Bitácora de Auditoría de Cambios en Rutas
CREATE TABLE auditoria_rutas (
    auditoria_id SERIAL PRIMARY KEY,
    operacion_id INT,
    ruta_id INT NOT NULL,
    accion VARCHAR(10) NOT NULL CHECK (accion IN ('INSERT', 'UPDATE', 'DELETE')),
    detalle_cambio TEXT NOT NULL,
    fecha_registro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Índices para acelerar consultas analíticas de los agentes inteligentes
CREATE INDEX idx_ruta_operaciones_ruta ON ruta_operaciones(ruta_id);
CREATE INDEX idx_ruta_operaciones_estacion ON ruta_operaciones(estacion_id);
CREATE INDEX idx_rutas_producto ON rutas(producto_sku);