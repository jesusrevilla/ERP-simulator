-- =============================================================================
-- Escenario hipotético y consultas — Matrícula 181914 (issue #239)
-- Requiere: BOM/BD/schema.sql + schema_descontinuados.sql
-- Reproduce en PostgreSQL el escenario de gestor_descontinuados.py: la tarjeta
-- madre MB-B550-PLUS se descontinúa y se sustituye por MB-B550-PRO.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Datos maestros
-- -----------------------------------------------------------------------------
INSERT INTO unidades_medida (uom_id, nombre, dimension) VALUES ('PCS', 'Pieza', 'CONTEO');

INSERT INTO articulos (sku, descripcion, tipo_item, uom_base_id, costo_estandar, categoria) VALUES
 ('MB-B550-PLUS',   'Tarjeta madre B550 ATX (original)',      'MP', 'PCS', 2300, 'TARJETA_MADRE'),
 ('MB-B550-PRO',    'Tarjeta madre B550 PRO ATX',             'MP', 'PCS', 2450, 'TARJETA_MADRE'),
 ('MB-X570-ELITE',  'Tarjeta madre X570 ATX',                 'MP', 'PCS', 3600, 'TARJETA_MADRE'),
 ('MB-B550-LEGACY', 'Tarjeta madre B550 ATX (EOL anunciado)', 'MP', 'PCS', 2200, 'TARJETA_MADRE'),
 ('MB-A520M-LITE',  'Tarjeta madre A520 mATX',                'MP', 'PCS', 1500, 'TARJETA_MADRE'),
 ('MB-B650-AURA',   'Tarjeta madre B650 ATX (AM5)',           'MP', 'PCS', 3100, 'TARJETA_MADRE'),
 ('CPU-R5-5600',    'Procesador Ryzen 5 5600',                'MP', 'PCS', 2600, 'PROCESADOR'),
 ('CPU-R7-5700X',   'Procesador Ryzen 7 5700X',               'MP', 'PCS', 3900, 'PROCESADOR'),
 ('RAM-16-DDR4',    'Memoria 16 GB DDR4 3200',                'MP', 'PCS',  700, 'MEMORIA_RAM'),
 ('SSD-1TB',        'Unidad SSD NVMe 1 TB',                   'MP', 'PCS', 1100, 'ALMACENAMIENTO'),
 ('PSU-650-B',      'Fuente 650 W 80+ Bronze',                'MP', 'PCS', 1200, 'FUENTE_PODER'),
 ('GAB-ATX',        'Gabinete ATX',                           'MP', 'PCS',  900, 'GABINETE'),
 ('GPU-RTX-4060',   'Tarjeta gráfica RTX 4060',               'MP', 'PCS', 6500, 'GPU'),
 ('ENS-BASE-AM4',   'Subensamble base AM4 (placa + CPU)',     'SE', 'PCS',    0, 'SUBENSAMBLE'),
 ('PC-OFI-100',     'PC de oficina',                          'PT', 'PCS',    0, 'PRODUCTO'),
 ('PC-GAM-200',     'PC gamer',                               'PT', 'PCS',    0, 'PRODUCTO'),
 ('PC-WS-300',      'Estación de trabajo',                    'PT', 'PCS',    0, 'PRODUCTO'),
 ('PC-MINI-400',    'Mini PC (AM5)',                          'PT', 'PCS',    0, 'PRODUCTO');

INSERT INTO criterios_compatibilidad (categoria, atributo, regla) VALUES
 ('TARJETA_MADRE', 'socket', 'IGUAL'),
 ('TARJETA_MADRE', 'tipo_memoria', 'IGUAL'),
 ('TARJETA_MADRE', 'form_factor', 'IGUAL'),
 ('TARJETA_MADRE', 'pcie_gen', 'MINIMO'),
 ('TARJETA_MADRE', 'ranuras_m2', 'MINIMO');

INSERT INTO articulo_especificaciones (sku, atributo, valor_texto, valor_numerico)
SELECT sku, a, t, n FROM (VALUES
 ('MB-B550-PLUS','socket','AM4',NULL),('MB-B550-PLUS','tipo_memoria','DDR4',NULL),('MB-B550-PLUS','form_factor','ATX',NULL),('MB-B550-PLUS','pcie_gen',NULL,4),('MB-B550-PLUS','ranuras_m2',NULL,2),
 ('MB-B550-PRO','socket','AM4',NULL),('MB-B550-PRO','tipo_memoria','DDR4',NULL),('MB-B550-PRO','form_factor','ATX',NULL),('MB-B550-PRO','pcie_gen',NULL,4),('MB-B550-PRO','ranuras_m2',NULL,2),
 ('MB-X570-ELITE','socket','AM4',NULL),('MB-X570-ELITE','tipo_memoria','DDR4',NULL),('MB-X570-ELITE','form_factor','ATX',NULL),('MB-X570-ELITE','pcie_gen',NULL,4),('MB-X570-ELITE','ranuras_m2',NULL,3),
 ('MB-B550-LEGACY','socket','AM4',NULL),('MB-B550-LEGACY','tipo_memoria','DDR4',NULL),('MB-B550-LEGACY','form_factor','ATX',NULL),('MB-B550-LEGACY','pcie_gen',NULL,4),('MB-B550-LEGACY','ranuras_m2',NULL,2),
 ('MB-A520M-LITE','socket','AM4',NULL),('MB-A520M-LITE','tipo_memoria','DDR4',NULL),('MB-A520M-LITE','form_factor','mATX',NULL),('MB-A520M-LITE','pcie_gen',NULL,3),('MB-A520M-LITE','ranuras_m2',NULL,1),
 ('MB-B650-AURA','socket','AM5',NULL),('MB-B650-AURA','tipo_memoria','DDR5',NULL),('MB-B650-AURA','form_factor','ATX',NULL),('MB-B650-AURA','pcie_gen',NULL,4),('MB-B650-AURA','ranuras_m2',NULL,2)
) AS v(sku, a, t, n);

INSERT INTO proveedores VALUES ('PRV-01', 'Mayorista de componentes A', TRUE), ('PRV-02', 'Distribuidor B', TRUE);

INSERT INTO articulo_proveedor (sku, proveedor_id, costo, tiempo_entrega_dias, disponible) VALUES
 ('MB-B550-PLUS',   'PRV-01', 2300,  6, TRUE),
 ('MB-B550-PRO',    'PRV-01', 2450,  5, TRUE),
 ('MB-X570-ELITE',  'PRV-02', 3600,  7, TRUE),
 ('MB-B550-LEGACY', 'PRV-02', 2200, 10, TRUE),
 ('MB-A520M-LITE',  'PRV-02', 1500,  4, TRUE),
 ('MB-B650-AURA',   'PRV-01', 3100,  5, TRUE),
 ('RAM-16-DDR4',    'PRV-01',  700,  3, TRUE),
 ('SSD-1TB',        'PRV-01', 1100,  3, TRUE),
 ('PSU-650-B',      'PRV-02', 1200,  5, TRUE);

INSERT INTO existencias (sku, almacen, cantidad_disponible) VALUES
 ('MB-B550-PLUS', 'ALM-01', 12), ('MB-B550-PRO', 'ALM-01', 40), ('MB-X570-ELITE', 'ALM-01', 10),
 ('MB-B550-LEGACY', 'ALM-01', 60), ('MB-A520M-LITE', 'ALM-01', 80), ('MB-B650-AURA', 'ALM-01', 25),
 ('CPU-R5-5600', 'ALM-01', 100), ('CPU-R7-5700X', 'ALM-01', 100), ('RAM-16-DDR4', 'ALM-01', 50),
 ('SSD-1TB', 'ALM-01', 20), ('PSU-650-B', 'ALM-01', 15), ('GAB-ATX', 'ALM-01', 40), ('GPU-RTX-4060', 'ALM-01', 5);

INSERT INTO componente_ciclo_vida (sku, estado, usuario)
SELECT sku, 'ACTIVO', 'carga_inicial' FROM articulos WHERE tipo_item = 'MP';
UPDATE componente_ciclo_vida SET estado = 'PROXIMO_A_DESCONTINUAR', fecha_anuncio_eol = '2026-10-01',
       usuario = 'carga_inicial'
WHERE sku = 'MB-B550-LEGACY';
-- La carga inicial no debe dejar alertas históricas para este escenario.
DELETE FROM alerta_bom_afectada;
DELETE FROM alertas_descontinuacion;

-- -----------------------------------------------------------------------------
-- 2. BOM activas (aprobadas) y órdenes
-- -----------------------------------------------------------------------------
INSERT INTO bom_cabecera (parent_sku, version_codigo, uom_id, estado, fecha_inicio,
                          usuario_creacion, usuario_aprobacion, fecha_aprobacion)
SELECT p, 'v1', 'PCS', 'ACTIVO', '2026-01-01', 'ing.bom', 'resp.produccion', '2026-01-01'
FROM unnest(ARRAY['ENS-BASE-AM4','PC-OFI-100','PC-GAM-200','PC-WS-300','PC-MINI-400']) AS p;

INSERT INTO bom_detalle (bom_id, component_sku, cantidad, uom_id)
SELECT c.bom_id, v.hijo, v.cant, 'PCS'
FROM (VALUES
 ('ENS-BASE-AM4','MB-B550-PLUS',1),('ENS-BASE-AM4','CPU-R5-5600',1),
 ('PC-OFI-100','ENS-BASE-AM4',1),('PC-OFI-100','RAM-16-DDR4',1),('PC-OFI-100','SSD-1TB',1),('PC-OFI-100','PSU-650-B',1),('PC-OFI-100','GAB-ATX',1),
 ('PC-GAM-200','ENS-BASE-AM4',1),('PC-GAM-200','RAM-16-DDR4',2),('PC-GAM-200','SSD-1TB',1),('PC-GAM-200','PSU-650-B',1),('PC-GAM-200','GAB-ATX',1),('PC-GAM-200','GPU-RTX-4060',1),
 ('PC-WS-300','MB-B550-PLUS',1),('PC-WS-300','CPU-R7-5700X',1),('PC-WS-300','RAM-16-DDR4',4),('PC-WS-300','SSD-1TB',2),('PC-WS-300','PSU-650-B',1),('PC-WS-300','GAB-ATX',1),
 ('PC-MINI-400','MB-B650-AURA',1),('PC-MINI-400','SSD-1TB',1)
) AS v(padre, hijo, cant)
JOIN bom_cabecera c ON c.parent_sku = v.padre AND c.version_codigo = 'v1';

INSERT INTO ordenes_produccion (codigo_orden, parent_sku, bom_id, cantidad_requerida, fecha_requerida,
                                estado, usuario_creacion)
SELECT v.cod, v.sku, c.bom_id, v.cant, v.fecha::DATE, v.estado, 'planeacion'
FROM (VALUES
 ('OF-1001','PC-OFI-100',30,'2026-12-05','PLANIFICADA'),
 ('OF-1002','PC-WS-300', 10,'2026-12-08','PLANIFICADA'),
 ('OF-0990','PC-GAM-200', 5,'2026-11-28','EN_PROCESO'),
 ('OF-0950','PC-MINI-400',8,'2026-12-02','PLANIFICADA'),
 ('OF-0900','PC-OFI-100',20,'2026-11-10','TERMINADA')
) AS v(cod, sku, cant, fecha, estado)
JOIN bom_cabecera c ON c.parent_sku = v.sku AND c.version_codigo = 'v1';

-- -----------------------------------------------------------------------------
-- 3. Proceso TO-BE
-- -----------------------------------------------------------------------------

-- 3.1 El comprador registra la descontinuación -> el trigger genera la alerta.
UPDATE componente_ciclo_vida
SET estado = 'DESCONTINUADO', fecha_descontinuacion = '2026-11-20 09:00:00+00',
    uso_stock_autorizado = TRUE, fuente = 'PCN PRV-01', usuario = 'comprador01'
WHERE sku = 'MB-B550-PLUS';

-- El trigger detecta la descontinuación en la misma transacción. Para reproducir
-- el escenario (job de notificación cada 15 min) se fija la hora simulada de la alerta.
UPDATE alertas_descontinuacion SET fecha_alerta = '2026-11-20 09:15:00+00' WHERE sku = 'MB-B550-PLUS';

\echo '--- Alerta generada automáticamente ---'
SELECT alerta_id, sku, prioridad, existencias, estado FROM alertas_descontinuacion;

\echo '--- BOM afectadas (where-used multinivel) ---'
SELECT c.parent_sku, c.version_codigo, a.nivel, a.ruta
FROM alerta_bom_afectada a JOIN bom_cabecera c USING (bom_id)
ORDER BY a.nivel, c.parent_sku;

\echo '--- KPI 3 al momento de la detección: % de BOM activas afectadas ---'
SELECT round(100.0 * count(DISTINCT f.bom_id)
             / NULLIF((SELECT count(*) FROM bom_cabecera WHERE estado = 'ACTIVO'), 0), 2) AS boms_afectadas_pct
FROM componente_ciclo_vida v
CROSS JOIN LATERAL fn_boms_afectadas(v.sku) f
WHERE v.estado = 'DESCONTINUADO';

-- 3.2 Evaluación técnica de candidatos (filtro de compatibilidad del agente).
\echo '--- Candidatos y criterios incumplidos ---'
WITH original AS (SELECT categoria FROM articulos WHERE sku = 'MB-B550-PLUS'),
candidatos AS (
    SELECT a.sku FROM articulos a, original o
    WHERE a.categoria = o.categoria AND a.sku <> 'MB-B550-PLUS'
      AND NOT EXISTS (SELECT 1 FROM componente_ciclo_vida v
                      WHERE v.sku = a.sku AND v.estado = 'DESCONTINUADO')
),
evaluacion AS (
    SELECT c.sku, k.atributo,
           CASE k.regla
             WHEN 'IGUAL'  THEN COALESCE(s.valor_texto, s.valor_numerico::TEXT)
                                = COALESCE(o.valor_texto, o.valor_numerico::TEXT)
             WHEN 'MINIMO' THEN s.valor_numerico >= o.valor_numerico
             WHEN 'MAXIMO' THEN s.valor_numerico <= o.valor_numerico
           END AS cumple
    FROM candidatos c
    CROSS JOIN criterios_compatibilidad k
    JOIN articulo_especificaciones o ON o.sku = 'MB-B550-PLUS' AND o.atributo = k.atributo
    LEFT JOIN articulo_especificaciones s ON s.sku = c.sku AND s.atributo = k.atributo
    WHERE k.categoria = 'TARJETA_MADRE'
)
SELECT sku,
       bool_and(COALESCE(cumple, FALSE)) AS compatible,
       string_agg(atributo, ', ') FILTER (WHERE NOT COALESCE(cumple, FALSE)) AS incumple
FROM evaluacion GROUP BY sku ORDER BY compatible DESC, sku;

-- 3.3 El agente registra su ranking (puntuaciones calculadas por gestor_descontinuados.py).
INSERT INTO recomendaciones_sustitucion (alerta_id, sku_original, sku_sustituto, posicion,
                                         puntuacion, detalle, justificacion, modelo_version)
SELECT (SELECT alerta_id FROM alertas_descontinuacion WHERE sku = 'MB-B550-PLUS'),
       'MB-B550-PLUS', v.sku, v.pos, v.punt, v.det::JSONB, v.just, 'agente-bom-181914/1.0'
FROM (VALUES
 ('MB-B550-PRO',    1, 0.9620, '{"inventario":1,"proveedor":1,"costo":0.935,"tiempo_entrega":0.833,"ciclo_vida":1,"impacto":1}', 'Mismo socket, chipset y factor de forma; stock suficiente.'),
 ('MB-B550-LEGACY', 2, 0.8800, '{"inventario":1,"proveedor":1,"costo":1,"tiempo_entrega":0.667,"ciclo_vida":0.3,"impacto":1}', 'Compatible pero con EOL anunciado: riesgo de repetir la sustitución.'),
 ('MB-X570-ELITE',  3, 0.6578, '{"inventario":0.303,"proveedor":1,"costo":0.435,"tiempo_entrega":0.767,"ciclo_vida":1,"impacto":0.8}', 'Compatible; 56 % más caro y stock insuficiente.')
) AS v(sku, pos, punt, det, just);

-- 3.4 Regla RN-02: el MRP no puede emitir compra ordinaria del descontinuado.
DO $$
BEGIN
    INSERT INTO recomendaciones_compra (corrida_mrp, sku, cantidad) VALUES ('MRP-TEST', 'MB-B550-PLUS', 28);
    RAISE EXCEPTION 'FALLO: se aceptó una compra ordinaria de un descontinuado';
EXCEPTION WHEN raise_exception THEN
    IF SQLERRM LIKE 'FALLO%' THEN RAISE; END IF;
    RAISE NOTICE 'OK RN-02 -> %', SQLERRM;
END $$;

-- 3.5 Regla RN-06: no se puede aplicar una sustitución con autorización rechazada.
INSERT INTO autorizaciones_sustitucion (recomendacion_id, usuario, rol, decision, comentario, fecha)
SELECT recomendacion_id, 'ing.tecnico', 'RESPONSABLE_TECNICO', 'RECHAZADA', 'EOL anunciado', '2026-11-21 09:00+00'
FROM recomendaciones_sustitucion WHERE sku_sustituto = 'MB-B550-LEGACY';

DO $$
BEGIN
    INSERT INTO sustituciones_bom (autorizacion_id, bom_anterior_id, bom_nueva_id, sku_original, sku_sustituto, usuario)
    SELECT a.autorizacion_id, 1, 2, 'MB-B550-PLUS', 'MB-B550-LEGACY', 'resp.bom'
    FROM autorizaciones_sustitucion a WHERE a.decision = 'RECHAZADA';
    RAISE EXCEPTION 'FALLO: se aplicó una sustitución rechazada';
EXCEPTION WHEN raise_exception THEN
    IF SQLERRM LIKE 'FALLO%' THEN RAISE; END IF;
    RAISE NOTICE 'OK RN-06 -> %', SQLERRM;
END $$;

-- 3.6 Autorización del responsable técnico y aplicación por nueva revisión.
INSERT INTO autorizaciones_sustitucion (recomendacion_id, usuario, rol, decision, comentario, fecha)
SELECT recomendacion_id, 'ing.tecnico', 'RESPONSABLE_TECNICO', 'APROBADA',
       'Mismo chipset y socket; validado en banco de pruebas.', '2026-11-21 09:15+00'
FROM recomendaciones_sustitucion WHERE sku_sustituto = 'MB-B550-PRO';

DO $$
DECLARE
    v_aut BIGINT;
    r RECORD;
    v_nueva BIGINT;
    v_sust BIGINT;
BEGIN
    SELECT autorizacion_id INTO v_aut FROM autorizaciones_sustitucion WHERE decision = 'APROBADA';
    FOR r IN SELECT c.* FROM fn_boms_afectadas('MB-B550-PLUS') a
             JOIN bom_cabecera c ON c.bom_id = a.bom_id WHERE a.nivel = 1 LOOP
        -- Cerrar la versión anterior (la estructura no se edita: RN-08).
        UPDATE bom_cabecera SET estado = 'OBSOLETO', fecha_fin = '2026-11-21 10:00+00'
        WHERE bom_id = r.bom_id;
        INSERT INTO bom_cabecera (parent_sku, version_codigo, uom_id, estado, fecha_inicio,
                                  notas_ingenieria, usuario_creacion, usuario_aprobacion, fecha_aprobacion)
        VALUES (r.parent_sku, 'v2', 'PCS', 'ACTIVO', '2026-11-21 10:00+00',
                'Sustitución MB-B550-PLUS -> MB-B550-PRO', 'resp.bom', 'ing.tecnico', '2026-11-21 09:15+00')
        RETURNING bom_id INTO v_nueva;
        INSERT INTO bom_detalle (bom_id, component_sku, cantidad, uom_id, scrap_merma)
        SELECT v_nueva,
               CASE WHEN component_sku = 'MB-B550-PLUS' THEN 'MB-B550-PRO' ELSE component_sku END,
               cantidad, uom_id, scrap_merma
        FROM bom_detalle WHERE bom_id = r.bom_id;
        INSERT INTO sustituciones_bom (autorizacion_id, bom_anterior_id, bom_nueva_id, sku_original,
                                       sku_sustituto, politica, usuario, fecha_efectiva)
        VALUES (v_aut, r.bom_id, v_nueva, 'MB-B550-PLUS', 'MB-B550-PRO', 'AGOTAR_EXISTENCIAS',
                'resp.bom', '2026-11-21 10:00+00')
        RETURNING sustitucion_id INTO v_sust;
        -- RN-07: evaluar órdenes antes de reasignar.
        INSERT INTO sustitucion_evaluacion_ordenes (sustitucion_id, orden_id, decision)
        SELECT v_sust, o.orden_id,
               CASE WHEN o.estado = 'PLANIFICADA' THEN 'REPLANIFICAR' ELSE 'CONSERVAR' END
        FROM ordenes_produccion o
        WHERE o.estado IN ('PLANIFICADA', 'LIBERADA', 'EN_PROCESO')
          -- uso directo o indirecto (BOM superiores que contienen al padre)
          AND (o.bom_id = r.bom_id
               OR o.bom_id IN (SELECT f.bom_id FROM fn_boms_afectadas(r.parent_sku) f));
        UPDATE ordenes_produccion SET bom_id = v_nueva
        WHERE bom_id = r.bom_id AND estado = 'PLANIFICADA';
    END LOOP;
    UPDATE alertas_descontinuacion SET estado = 'RESUELTA', fecha_cierre = '2026-11-21 10:00+00'
    WHERE sku = 'MB-B550-PLUS';
END $$;

\echo '--- Historial de sustituciones ---'
SELECT s.sustitucion_id, a.parent_sku || ' ' || a.version_codigo AS anterior,
       n.parent_sku || ' ' || n.version_codigo AS nueva, s.politica, au.usuario AS autorizo
FROM sustituciones_bom s
JOIN bom_cabecera a ON a.bom_id = s.bom_anterior_id
JOIN bom_cabecera n ON n.bom_id = s.bom_nueva_id
JOIN autorizaciones_sustitucion au USING (autorizacion_id);

\echo '--- Evaluación de órdenes ---'
SELECT o.codigo_orden, o.estado, e.decision
FROM sustitucion_evaluacion_ordenes e JOIN ordenes_produccion o USING (orden_id)
ORDER BY o.codigo_orden;

-- 3.7 Regla RN-08: el historial no se puede modificar.
DO $$
BEGIN
    DELETE FROM sustituciones_bom;
    RAISE EXCEPTION 'FALLO: se borró el historial';
EXCEPTION WHEN raise_exception THEN
    IF SQLERRM LIKE 'FALLO%' THEN RAISE; END IF;
    RAISE NOTICE 'OK RN-08 -> %', SQLERRM;
END $$;

-- 3.8 MRP recalculado: compras ordinarias del pedido (sin descontinuados).
INSERT INTO recomendaciones_compra (corrida_mrp, sku, cantidad) VALUES
 ('MRP-2026-11-21', 'RAM-16-DDR4', 20), ('MRP-2026-11-21', 'SSD-1TB', 30), ('MRP-2026-11-21', 'PSU-650-B', 25);

-- -----------------------------------------------------------------------------
-- 4. KPIs (ver 06_KPIs.md)
-- -----------------------------------------------------------------------------
\echo '--- KPI 1 y 2: tiempo de detección y de sustitución (horas) ---'
SELECT a.sku,
       round(EXTRACT(EPOCH FROM (a.fecha_alerta - a.fecha_registro)) / 3600, 2) AS deteccion_h,
       round(EXTRACT(EPOCH FROM (min(au.fecha) - a.fecha_alerta)) / 3600, 2) AS sustitucion_h
FROM alertas_descontinuacion a
LEFT JOIN recomendaciones_sustitucion r ON r.alerta_id = a.alerta_id
LEFT JOIN autorizaciones_sustitucion au ON au.recomendacion_id = r.recomendacion_id AND au.decision = 'APROBADA'
GROUP BY a.alerta_id, a.sku, a.fecha_alerta, a.fecha_registro;

\echo '--- KPI 3: % de BOM activas afectadas por descontinuados (multinivel) ---'
SELECT round(100.0 * count(DISTINCT f.bom_id)
             / NULLIF((SELECT count(*) FROM bom_cabecera WHERE estado = 'ACTIVO'), 0), 2) AS boms_afectadas_pct
FROM componente_ciclo_vida v
CROSS JOIN LATERAL fn_boms_afectadas(v.sku) f
WHERE v.estado = 'DESCONTINUADO';

\echo '--- KPI 4: % de recomendaciones de compra inválidas ---'
SELECT corrida_mrp,
       round(100.0 * count(*) FILTER (WHERE v.estado = 'DESCONTINUADO') / count(*), 2) AS invalidas_pct
FROM recomendaciones_compra rc
LEFT JOIN componente_ciclo_vida v USING (sku)
GROUP BY corrida_mrp;

\echo '--- KPI 5: % de órdenes de fabricación retrasadas por descontinuados ---'
SELECT round(100.0 * count(*) FILTER (WHERE causa_retraso = 'COMPONENTE_DESCONTINUADO')
             / NULLIF(count(*), 0), 2) AS ordenes_afectadas_pct
FROM ordenes_produccion
WHERE estado <> 'CANCELADA' AND fecha_requerida BETWEEN '2026-11-01' AND '2026-12-31';

\echo '--- KPI 6: tasa de sustitución exitosa ---'
SELECT round(100.0 * count(DISTINCT a.sku) FILTER (WHERE EXISTS (
           SELECT 1 FROM recomendaciones_sustitucion r
           JOIN autorizaciones_sustitucion au ON au.recomendacion_id = r.recomendacion_id
           WHERE r.alerta_id = a.alerta_id AND au.decision = 'APROBADA'))
       / NULLIF(count(DISTINCT a.sku), 0), 2) AS tasa_sustitucion_exitosa_pct
FROM alertas_descontinuacion a
JOIN componente_ciclo_vida v ON v.sku = a.sku AND v.estado = 'DESCONTINUADO'
WHERE EXISTS (SELECT 1 FROM alerta_bom_afectada b WHERE b.alerta_id = a.alerta_id);
