-- ============================================================================
-- Issue #249 - Datos de Prueba y Consultas para Agentes Inteligentes
-- ============================================================================

-- 1. Poblar estaciones de trabajo
INSERT INTO estaciones_trabajo (codigo, nombre, capacidad_diaria_min, costo_por_hora, estado) VALUES
('EST-CORTE', 'Estación de Corte CNC', 480, 45.00, 'ACTIVA'),
('EST-SOLD',  'Estación de Soldadura Robotizada', 480, 60.00, 'ACTIVA'),
('EST-ENS',   'Línea de Ensamble Final', 480, 35.00, 'ACTIVA'),
('EST-CAL',   'Inspección de Calidad', 240, 30.00, 'ACTIVA');

-- 2. Poblar rutas (Principal y Alternativa para el mismo producto)
INSERT INTO rutas (codigo_ruta, producto_sku, version) VALUES
('RUT-CHASIS-A', 'SKU-1001', '1.0'),
('RUT-CHASIS-B', 'SKU-1001', '1.1');

-- 3. Registrar operaciones usando el Procedimiento Almacenado (dispara el Trigger)
CALL sp_registrar_operacion_ruta(1, 1, 1, 'Corte de lámina principal', 15, 45);
CALL sp_registrar_operacion_ruta(1, 2, 2, 'Soldadura estructural', 20, 90);
CALL sp_registrar_operacion_ruta(1, 3, 3, 'Ensamble de componentes', 10, 60);
CALL sp_registrar_operacion_ruta(1, 4, 4, 'Prueba de tolerancias', 10, 30);

-- Ruta alternativa (omite soldadura y va directo a ensamble modular)
CALL sp_registrar_operacion_ruta(2, 1, 1, 'Corte de lámina modular', 10, 40);
CALL sp_registrar_operacion_ruta(2, 3, 2, 'Ensamble modular rápido', 15, 70);
CALL sp_registrar_operacion_ruta(2, 4, 3, 'Prueba de tolerancias', 10, 25);

-- 4. Prueba de actualización (valida trigger UPDATE)
UPDATE ruta_operaciones
SET tiempo_ejecucion_min = 105
WHERE ruta_id = 1 AND numero_secuencia = 2;

-- ============================================================================
-- CONSULTAS DE VALIDACIÓN Y SOPORTE A AGENTES INTELIGENTES
-- ============================================================================

-- A) Eficiencia y costo por ruta (para elegir la ruta más rentable)
SELECT * FROM vw_resumen_rutas ORDER BY costo_estimado_usd ASC;

-- B) Detección de estaciones con mayor carga / posibles cuellos de botella
SELECT * FROM vw_carga_estaciones ORDER BY porcentaje_ocupacion DESC;

-- C) Auditoría de trazabilidad de cambios
SELECT * FROM auditoria_rutas ORDER BY fecha_registro DESC;