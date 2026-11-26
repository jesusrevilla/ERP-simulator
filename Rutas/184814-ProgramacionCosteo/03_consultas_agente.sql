-- =====================================================================
--  Consultas SQL para los agentes inteligentes del módulo de Rutas
--  Autor: Diego Luna Saucedo - 184814  ·  Issue #300
--  Requiere: Scheme.sql, 01_esquema_programacion.sql y 02_datos_semilla.sql
-- =====================================================================

-- ---------------------------------------------------------------------
-- Q1. ¿Para cuándo puedo entregar N Gaming PC y cuánto cuesta?
--     Simulación: se crea la orden, se programa y se deshace todo con
--     ROLLBACK, así que no queda nada guardado.
--     Decisión: el agente acepta la fecha que pide el cliente o propone
--     la fecha calculada.
-- ---------------------------------------------------------------------
BEGIN;

INSERT INTO orden_produccion (folio, material_id, cantidad, almacen_id, hoja_ruta_id,
                              fecha_inicio, fecha_fin, creado_por)
SELECT 'SIM-001', m.material_id, 30, a.almacen_id, h.hoja_ruta_id,
       DATE '2026-12-07', DATE '2026-12-07', u.usuario_id
FROM material m, almacen a, hoja_ruta h, usuario u
WHERE m.codigo = 'GAMING_PC' AND a.codigo = 'ALM-PT'
  AND h.numero = 'HR-GPC-001' AND u.correo = 'planeacion@techassembly.mx';

SELECT o.folio,
       o.cantidad,
       p.fecha_fin_nueva    AS fecha_entrega_calculada,
       p.costo_planificado,
       round(p.costo_planificado / o.cantidad, 2) AS costo_por_pc
FROM orden_produccion o
CROSS JOIN LATERAL fn_programar_orden(o.orden_produccion_id, 'Simulación') p
WHERE o.folio = 'SIM-001';

ROLLBACK;

-- ---------------------------------------------------------------------
-- Q2. Órdenes cuya fecha calculada excede la fecha compromiso
--     Decisión: avisar al cliente, priorizar la orden o liberar capacidad.
-- ---------------------------------------------------------------------
SELECT DISTINCT folio, estatus_orden, fecha_fin_orden, fecha_compromiso,
       -holgura_dias AS dias_de_atraso
FROM vw_programa_ordenes
WHERE holgura_dias < 0
ORDER BY dias_de_atraso DESC;

-- ---------------------------------------------------------------------
-- Q3. Centros de trabajo sobreprogramados por día
--     Decisión: mover una orden, abrir horas extra o subcontratar.
-- ---------------------------------------------------------------------
SELECT centro_trabajo, fecha, horas_programadas, capacidad_horas_dia,
       porcentaje_uso, ordenes
FROM vw_carga_centro_dia
WHERE sobrecargado
ORDER BY fecha, centro_trabajo;

-- ---------------------------------------------------------------------
-- Q4. Órdenes con mayor desviación entre costo real y planificado
--     Decisión: revisar al proveedor o actualizar el costo estándar.
-- ---------------------------------------------------------------------
SELECT folio, costo_planificado, costo_estandar_despachado, costo_real_despachado,
       desviacion, desviacion_pct, avance_despacho_pct
FROM vw_desviacion_costos
WHERE nivel = 'ORDEN'
ORDER BY abs(desviacion) DESC
LIMIT 5;

-- ---------------------------------------------------------------------
-- Q5. Costo planificado por etapa y por tipo de costo
--     Decisión: identificar qué etapa encarece la orden.
-- ---------------------------------------------------------------------
SELECT o.folio,
       e.secuencia,
       er.codigo AS etapa,
       round(COALESCE(sum(l.cantidad_planificada * l.costo_unitario)
                      FILTER (WHERE l.tipo = 'MATERIAL'), 0), 2) AS material,
       round(COALESCE(sum(l.cantidad_planificada * l.costo_unitario)
                      FILTER (WHERE l.tipo = 'RECURSO'), 0), 2)  AS recurso,
       round((e.tiempo_preparacion_min + e.tiempo_ejecucion_min * o.cantidad)
             / 60.0 * ct.costo_hora, 2)                          AS centro_trabajo
FROM orden_produccion o
JOIN orden_produccion_etapa e   ON e.orden_produccion_id = o.orden_produccion_id
JOIN etapa_ruta er              ON er.etapa_ruta_id = e.etapa_ruta_id
JOIN centro_trabajo ct          ON ct.centro_trabajo_id = e.centro_trabajo_id
LEFT JOIN orden_produccion_linea l ON l.orden_produccion_etapa_id = e.orden_produccion_etapa_id
GROUP BY o.folio, o.cantidad, e.secuencia, er.codigo, e.tiempo_preparacion_min,
         e.tiempo_ejecucion_min, ct.costo_hora
ORDER BY o.folio, e.secuencia;

-- ---------------------------------------------------------------------
-- Q6. Historial de reprogramaciones de una orden (auditoría)
--     En los registros RETRASO las fechas son las de la etapa retrasada;
--     en PROGRAMACION son las de la orden.
-- ---------------------------------------------------------------------
SELECT l.ejecutado_en, l.tipo, l.fecha_fin_anterior, l.fecha_fin_nueva,
       l.costo_anterior, l.costo_nuevo, l.motivo, u.nombre AS ejecutado_por
FROM orden_programacion_log l
JOIN orden_produccion o ON o.orden_produccion_id = l.orden_produccion_id
LEFT JOIN usuario u     ON u.usuario_id = l.ejecutado_por
WHERE o.folio = 'OP-2026-001'
ORDER BY l.orden_programacion_log_id;

-- ---------------------------------------------------------------------
-- Q7. Siguiente día laborable para comprometer una fecha
-- ---------------------------------------------------------------------
SELECT fn_siguiente_laborable(DATE '2026-12-25') AS siguiente_dia_laborable;
