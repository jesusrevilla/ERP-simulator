-- ==========================================
-- 1. DATOS MAESTROS (Master Data)
-- ==========================================

-- Ubicaciones físicas o lógicas
CREATE TABLE location (
    location_id VARCHAR(100) PRIMARY KEY,
    location_type VARCHAR(50) NOT NULL, -- Ej: Enterprise, Site, Area
    description TEXT
);

-- Catálogo de equipos y estaciones de trabajo
CREATE TABLE equipment (
    equipment_id VARCHAR(100) PRIMARY KEY,
    location_id VARCHAR(100) REFERENCES location(location_id),
    description TEXT,
    equipment_level VARCHAR(50), -- Ej: WorkCell, WorkUnit
    properties JSONB -- Para almacenar arreglos dinámicos como EquipmentProperty
);

-- Catálogo de materiales, componentes y productos terminados
CREATE TABLE material (
    material_id VARCHAR(100) PRIMARY KEY, -- Ej: CPU-RYZEN-7, MB-B650
    description TEXT NOT NULL,
    stock_quantity INT DEFAULT 0
);

-- Bill of Materials (BOM) - Lista de Materiales Recursiva
CREATE TABLE bill_of_materials (
    parent_material_id VARCHAR(100) REFERENCES material(material_id),
    child_material_id VARCHAR(100) REFERENCES material(material_id),
    quantity DECIMAL(10,4) DEFAULT 1.0,
    PRIMARY KEY (parent_material_id, child_material_id),
    CONSTRAINT chk_no_self_reference CHECK (parent_material_id != child_material_id)
);

-- ==========================================
-- 2. DATOS TRANSACCIONALES (Transactional Data)
-- ==========================================

-- Extensión para generar UUIDs en PostgreSQL
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Órdenes de Producción (MRP)
CREATE TABLE production_orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_number VARCHAR(50) UNIQUE NOT NULL,
    material_id VARCHAR(100) NOT NULL REFERENCES material(material_id),
    target_quantity INTEGER NOT NULL CHECK (target_quantity > 0),
    status VARCHAR(50) NOT NULL DEFAULT 'Planned' CHECK (status IN ('Planned', 'Released', 'InProgress', 'Completed', 'Cancelled')),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Operaciones asociadas a las órdenes
CREATE TABLE operation (
    operation_id VARCHAR(100) PRIMARY KEY, -- Ej: ACT-PREP-MB-01
    production_order_id UUID REFERENCES production_orders(id) ON DELETE CASCADE,
    equipment_id VARCHAR(100) REFERENCES equipment(equipment_id),
    description TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'Pending',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Eventos y trazabilidad de calidad/ensamble
CREATE TABLE operation_event (
    event_id VARCHAR(100) PRIMARY KEY, -- Ej: EVT-ASM-001
    operation_id VARCHAR(100) REFERENCES operation(operation_id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL, -- Ej: ComponentMounting, Start, Complete
    description TEXT,
    event_time TIMESTAMPTZ NOT NULL -- Ej: 2026-11-10T20:41:05Z
);

-- ==========================================
-- 3. ÍNDICES DE RENDIMIENTO (Performance)
-- ==========================================
CREATE INDEX idx_equipment_location ON equipment(location_id);
CREATE INDEX idx_operation_equipment ON operation(equipment_id);
CREATE INDEX idx_operation_order ON operation(production_order_id);
CREATE INDEX idx_event_operation ON operation_event(operation_id);
CREATE INDEX idx_event_time ON operation_event(event_time);