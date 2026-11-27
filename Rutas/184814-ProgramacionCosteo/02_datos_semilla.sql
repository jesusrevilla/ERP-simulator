-- =====================================================================
--  Datos semilla: ruta de la Gaming PC (TechAssembly S.A.)
--  Autor: Diego Luna Saucedo - 184814  ·  Issue #300
--
--  Orden de ejecución:
--    1. Rutas/Scheme.sql
--    2. 01_esquema_programacion.sql
--    3. este archivo
--
--  Las 3 etapas y sus materiales siguen los ejemplos ISA-95 de la
--  carpeta Rutas (172122_gaming_pc_ruta_isa95.json y 178218PcGaming.json):
--    Etapa 1 Base      (Motherboard, CPU, RAM, SSD)   90 min por PC
--    Etapa 2 Energía   (Fuente de poder)              60 min por PC
--    Etapa 3 Gráficos  (Tarjeta gráfica)              60 min por PC
--  Los costos son valores de ejemplo en pesos mexicanos.
-- =====================================================================

BEGIN;

-- Usuarios (los roles ya los crea Scheme.sql)
INSERT INTO usuario (rol_id, nombre, correo)
SELECT r.rol_id, u.nombre, u.correo
FROM (VALUES
    ('INGENIERO_PROCESOS', 'Ingeniera de Procesos', 'procesos@techassembly.mx'),
    ('JEFE_PRODUCCION',    'Jefe de Producción',    'produccion@techassembly.mx'),
    ('PLANEADOR',          'Planeador MRP',         'planeacion@techassembly.mx')
) AS u (rol, nombre, correo)
JOIN rol r ON r.clave = u.rol;

INSERT INTO almacen (codigo, nombre) VALUES
    ('ALM-MP', 'Almacén de materia prima'),
    ('ALM-PT', 'Almacén de producto terminado');

INSERT INTO material (codigo, descripcion, unidad_medida, tipo, costo_unitario) VALUES
    ('GAMING_PC',        'Gaming PC ensamblada',        'PZA', 'FABRICADO',    0),
    ('CPU_RYZEN7',       'CPU Ryzen 7',                 'PZA', 'COMPRADO',  5200),
    ('MOTHERBOARD_B650', 'Motherboard B650',            'PZA', 'COMPRADO',  3600),
    ('RAM_16GB_DDR5',    'Memoria RAM 16GB DDR5',       'PZA', 'COMPRADO',  1400),
    ('SSD_1TB_NVME',     'SSD 1TB NVMe',                'PZA', 'COMPRADO',  1300),
    ('PSU_750W',         'Fuente de poder 750W',        'PZA', 'COMPRADO',  1700),
    ('GPU_RTX',          'Tarjeta gráfica RTX',         'PZA', 'COMPRADO',  9800);

INSERT INTO existencia (material_id, almacen_id, cantidad)
SELECT m.material_id, a.almacen_id, 100
FROM material m CROSS JOIN almacen a
WHERE m.tipo = 'COMPRADO' AND a.codigo = 'ALM-MP';

INSERT INTO centro_trabajo (codigo, nombre, capacidad_horas_dia, costo_hora) VALUES
    ('CT-ENS', 'Línea de ensamble base',     8, 180),
    ('CT-ENE', 'Estación de energía',        8, 160),
    ('CT-GPU', 'Estación de gráficos y QA',  8, 200);

INSERT INTO recurso (centro_trabajo_id, codigo, nombre, tipo, costo_hora)
SELECT ct.centro_trabajo_id, r.codigo, r.nombre, r.tipo, r.costo_hora
FROM (VALUES
    ('CT-ENS', 'TEC-ENS', 'Técnico de ensamble',     'MANO_OBRA', 95),
    ('CT-ENE', 'TEC-ENE', 'Técnico de energía',      'MANO_OBRA', 95),
    ('CT-GPU', 'BANCO-QA', 'Banco de pruebas de QA', 'MAQUINA',   60)
) AS r (centro, codigo, nombre, tipo, costo_hora)
JOIN centro_trabajo ct ON ct.codigo = r.centro;

INSERT INTO etapa_ruta (codigo, descripcion) VALUES
    ('ETAPA_1_BASE',     'Ensamble base: motherboard, CPU, RAM y SSD'),
    ('ETAPA_2_ENERGIA',  'Instalación de fuente de poder y cableado'),
    ('ETAPA_3_GRAFICOS', 'Instalación de tarjeta gráfica y pruebas');

-- Hoja de ruta de la Gaming PC
INSERT INTO hoja_ruta (numero, descripcion, vigente_desde, creado_por)
SELECT 'HR-GPC-001', 'Ruta de ensamble Gaming PC', DATE '2026-11-01', u.usuario_id
FROM usuario u WHERE u.correo = 'procesos@techassembly.mx';

INSERT INTO hoja_ruta_operacion (
    hoja_ruta_id, secuencia, etapa_ruta_id, centro_trabajo_id, descripcion,
    tiempo_preparacion_min, tiempo_ejecucion_min, dias_espera)
SELECT h.hoja_ruta_id, o.secuencia, er.etapa_ruta_id, ct.centro_trabajo_id, o.descripcion,
       o.prep, o.ejec, o.espera
FROM (VALUES
    (1, 'ETAPA_1_BASE',     'CT-ENS', 'Ensamble base',              30, 90, 0),
    (2, 'ETAPA_2_ENERGIA',  'CT-ENE', 'Energía y cableado',         20, 60, 0),
    (3, 'ETAPA_3_GRAFICOS', 'CT-GPU', 'Gráficos y prueba de QA',    20, 60, 1)
) AS o (secuencia, etapa, centro, descripcion, prep, ejec, espera)
JOIN hoja_ruta h       ON h.numero = 'HR-GPC-001'
JOIN etapa_ruta er     ON er.codigo = o.etapa
JOIN centro_trabajo ct ON ct.codigo = o.centro;

INSERT INTO hoja_ruta_operacion_material (hoja_ruta_operacion_id, material_id, cantidad_base, almacen_id)
SELECT op.hoja_ruta_operacion_id, m.material_id, 1, a.almacen_id
FROM (VALUES
    (1, 'MOTHERBOARD_B650'), (1, 'CPU_RYZEN7'), (1, 'RAM_16GB_DDR5'), (1, 'SSD_1TB_NVME'),
    (2, 'PSU_750W'),
    (3, 'GPU_RTX')
) AS x (secuencia, material)
JOIN hoja_ruta h            ON h.numero = 'HR-GPC-001'
JOIN hoja_ruta_operacion op ON op.hoja_ruta_id = h.hoja_ruta_id AND op.secuencia = x.secuencia
JOIN material m             ON m.codigo = x.material
JOIN almacen a              ON a.codigo = 'ALM-MP';

-- Horas de recurso por PC
INSERT INTO hoja_ruta_operacion_recurso (hoja_ruta_operacion_id, recurso_id, horas_base)
SELECT op.hoja_ruta_operacion_id, r.recurso_id, x.horas
FROM (VALUES (1, 'TEC-ENS', 1.5), (2, 'TEC-ENE', 1.0), (3, 'BANCO-QA', 0.5)) AS x (secuencia, recurso, horas)
JOIN hoja_ruta h            ON h.numero = 'HR-GPC-001'
JOIN hoja_ruta_operacion op ON op.hoja_ruta_id = h.hoja_ruta_id AND op.secuencia = x.secuencia
JOIN recurso r              ON r.codigo = x.recurso;

INSERT INTO hoja_ruta_asignacion (hoja_ruta_id, material_id, lote_minimo, lote_maximo)
SELECT h.hoja_ruta_id, m.material_id, 1, 100
FROM hoja_ruta h, material m
WHERE h.numero = 'HR-GPC-001' AND m.codigo = 'GAMING_PC';

-- Liberación (RN-12: aprueba alguien distinto de quien la creó)
UPDATE hoja_ruta
   SET estatus      = 'LIBERADA',
       aprobado_por = (SELECT usuario_id FROM usuario WHERE correo = 'produccion@techassembly.mx'),
       liberado_en  = TIMESTAMP '2026-11-20 10:00'
 WHERE numero = 'HR-GPC-001';

-- Calendario: días no laborables de diciembre 2026 y enero 2027
-- (los fines de semana ya son no laborables por defecto)
INSERT INTO calendario_laboral (fecha, laborable, motivo) VALUES
    (DATE '2026-12-25', FALSE, 'Navidad'),
    (DATE '2027-01-01', FALSE, 'Año Nuevo');

-- Órdenes de producción (fecha_fin provisional: la calcula fn_programar_orden)
INSERT INTO orden_produccion (folio, material_id, cantidad, almacen_id, hoja_ruta_id,
                              fecha_inicio, fecha_fin, creado_por)
SELECT x.folio, m.material_id, x.cantidad, a.almacen_id, h.hoja_ruta_id,
       x.inicio, x.inicio, u.usuario_id
FROM (VALUES
    ('OP-2026-001', 30, DATE '2026-12-01'),
    ('OP-2026-002', 20, DATE '2026-12-03'),
    ('OP-2026-003', 10, DATE '2026-12-22')
) AS x (folio, cantidad, inicio)
JOIN material m  ON m.codigo = 'GAMING_PC'
JOIN almacen a   ON a.codigo = 'ALM-PT'
JOIN hoja_ruta h ON h.numero = 'HR-GPC-001'
JOIN usuario u   ON u.correo = 'planeacion@techassembly.mx';

INSERT INTO orden_fecha_compromiso (orden_produccion_id, fecha_compromiso)
SELECT o.orden_produccion_id, x.compromiso
FROM (VALUES
    ('OP-2026-001', DATE '2026-12-18'),
    ('OP-2026-002', DATE '2026-12-23'),
    ('OP-2026-003', DATE '2027-01-08')
) AS x (folio, compromiso)
JOIN orden_produccion o ON o.folio = x.folio;

COMMIT;

-- Programar las tres órdenes (genera etapas, líneas, fechas y costo)
SELECT * FROM fn_programar_orden(
    (SELECT orden_produccion_id FROM orden_produccion WHERE folio = 'OP-2026-001'),
    'Programación inicial',
    (SELECT usuario_id FROM usuario WHERE correo = 'planeacion@techassembly.mx'));
SELECT * FROM fn_programar_orden(
    (SELECT orden_produccion_id FROM orden_produccion WHERE folio = 'OP-2026-002'),
    'Programación inicial',
    (SELECT usuario_id FROM usuario WHERE correo = 'planeacion@techassembly.mx'));
SELECT * FROM fn_programar_orden(
    (SELECT orden_produccion_id FROM orden_produccion WHERE folio = 'OP-2026-003'),
    'Programación inicial',
    (SELECT usuario_id FROM usuario WHERE correo = 'planeacion@techassembly.mx'));

-- Liberar la OP-2026-001 y despachar la etapa 1. El CPU llegó más caro
-- (5,350 en vez de 5,200) para que se vea la desviación de costo.
UPDATE orden_produccion SET estatus = 'LIBERADA' WHERE folio = 'OP-2026-001';

INSERT INTO despacho_produccion (orden_produccion_id, orden_produccion_etapa_id,
                                 orden_produccion_linea_id, material_id, almacen_id,
                                 cantidad, costo_unitario, usuario_id)
SELECT l.orden_produccion_id, l.orden_produccion_etapa_id, l.orden_produccion_linea_id,
       l.material_id, l.almacen_id, l.cantidad_planificada,
       CASE m.codigo WHEN 'CPU_RYZEN7' THEN 5350 ELSE l.costo_unitario END,
       (SELECT usuario_id FROM usuario WHERE correo = 'planeacion@techassembly.mx')
FROM orden_produccion_linea l
JOIN orden_produccion o       ON o.orden_produccion_id = l.orden_produccion_id
JOIN orden_produccion_etapa e ON e.orden_produccion_etapa_id = l.orden_produccion_etapa_id
JOIN material m               ON m.material_id = l.material_id
WHERE o.folio = 'OP-2026-001' AND e.secuencia = 1 AND l.tipo = 'MATERIAL';
