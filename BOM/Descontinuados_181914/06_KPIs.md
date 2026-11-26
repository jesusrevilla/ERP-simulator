# 6. Indicadores de desempeño (KPIs)

Cada KPI tiene descripción, unidad, método de cálculo, fuente de datos, frecuencia y meta. Los métodos están implementados dos veces: en SQL (`sql/escenario_y_consultas.sql`, sección 4) y en Python (`ERP.kpis` en `gestor_descontinuados.py`). Así se pueden verificar entre sí.

## 6.1 Definición

| # | Indicador | Descripción | Unidad | Método de cálculo | Fuente | Frecuencia | Meta |
|---|---|---|---|---|---|---|---|
| 1 | **Tiempo de detección** | Tiempo entre el registro de la descontinuación y la generación de la alerta. | Horas | `promedio(fecha_alerta − fecha_registro)` de las alertas del periodo | `alertas_descontinuacion` | Mensual | ≤ 0.25 h (un ciclo del proceso de detección) |
| 2 | **Tiempo de sustitución** | Tiempo entre la detección (alerta) y la aprobación del sustituto. | Horas o días | `promedio(min(fecha de autorización APROBADA) − fecha_alerta)` por alerta | `alertas_descontinuacion`, `recomendaciones_sustitucion`, `autorizaciones_sustitucion` | Mensual | ≤ 48 h para alertas `CRITICA`; ≤ 5 días para el resto |
| 3 | **BOM afectadas** | Porcentaje de BOM activas que contienen un componente descontinuado en **cualquier nivel**. | % | `BOM activas distintas devueltas por fn_boms_afectadas(sku) para cada sku DESCONTINUADO / total de BOM activas × 100` | `componente_ciclo_vida`, `bom_cabecera`, `bom_detalle` | Diaria (en un tablero) | 0 % al cerrar cada alerta; tendencia a la baja |
| 4 | **Recomendaciones de compra inválidas** | Porcentaje de recomendaciones del MRP que corresponden a componentes descontinuados. | % | `recomendaciones de la corrida cuyo sku está DESCONTINUADO / total de recomendaciones de la corrida × 100` | `recomendaciones_compra`, `componente_ciclo_vida` | Por corrida de MRP | 0 % (lo garantiza el trigger RN-02) |
| 5 | **Órdenes de fabricación afectadas** | Porcentaje de órdenes retrasadas por componentes descontinuados. | % | `órdenes con causa_retraso = 'COMPONENTE_DESCONTINUADO' / órdenes no canceladas del periodo × 100` | `ordenes_produccion` (`fecha_requerida`, `fecha_fin_real`, `causa_retraso`) | Mensual | < 2 % |
| 6 | **Tasa de sustitución exitosa** | Porcentaje de componentes descontinuados con un sustituto validado, respecto a los que requieren sustitución. | % | `componentes DESCONTINUADO con alerta y BOM afectadas que tienen una autorización APROBADA / componentes DESCONTINUADO con alerta y BOM afectadas × 100` | `alertas_descontinuacion`, `alerta_bom_afectada`, `recomendaciones_sustitucion`, `autorizaciones_sustitucion` | Mensual | ≥ 90 % |

**Notas de cálculo**

- **KPI 1.** Si la detección es síncrona (el trigger corre en la misma transacción del cambio de estado), el valor tiende a 0 h. Si las notificaciones se envían por lotes cada 15 min, el máximo es 0.25 h. El escenario usa 0.25 h, el peor caso.
- **KPI 3.** Se cuenta cada BOM una sola vez, aunque contenga varios descontinuados o el mismo componente por varias rutas.
- **KPI 4.** Se evalúa con el estado **vigente** del componente. Una compra emitida antes de conocer la descontinuación también cuenta como inválida, porque representa el riesgo real.
- **KPI 5.** Una orden está retrasada si `fecha_fin_real > fecha_requerida`, o si sigue abierta después de `fecha_requerida`. La causa la registra Producción.
- **KPI 6.** Un componente cuenta en el denominador solo si afecta al menos una BOM activa. Los que no tienen uso no requieren sustitución.

## 6.2 Consultas SQL

```sql
-- KPI 1 y 2: tiempo de detección y de sustitución (horas)
SELECT a.sku,
       round(EXTRACT(EPOCH FROM (a.fecha_alerta - a.fecha_registro)) / 3600, 2) AS deteccion_h,
       round(EXTRACT(EPOCH FROM (min(au.fecha) - a.fecha_alerta)) / 3600, 2)    AS sustitucion_h
FROM alertas_descontinuacion a
LEFT JOIN recomendaciones_sustitucion r ON r.alerta_id = a.alerta_id
LEFT JOIN autorizaciones_sustitucion au ON au.recomendacion_id = r.recomendacion_id
                                       AND au.decision = 'APROBADA'
GROUP BY a.alerta_id, a.sku, a.fecha_alerta, a.fecha_registro;

-- KPI 3: % de BOM activas afectadas (multinivel)
SELECT round(100.0 * count(DISTINCT f.bom_id)
       / NULLIF((SELECT count(*) FROM bom_cabecera WHERE estado = 'ACTIVO'), 0), 2) AS boms_afectadas_pct
FROM componente_ciclo_vida v
CROSS JOIN LATERAL fn_boms_afectadas(v.sku) f
WHERE v.estado = 'DESCONTINUADO';

-- KPI 4: % de recomendaciones de compra inválidas por corrida
SELECT corrida_mrp,
       round(100.0 * count(*) FILTER (WHERE v.estado = 'DESCONTINUADO') / count(*), 2) AS invalidas_pct
FROM recomendaciones_compra rc
LEFT JOIN componente_ciclo_vida v USING (sku)
GROUP BY corrida_mrp;

-- KPI 5: % de órdenes retrasadas por descontinuados
SELECT round(100.0 * count(*) FILTER (WHERE causa_retraso = 'COMPONENTE_DESCONTINUADO')
       / NULLIF(count(*), 0), 2) AS ordenes_afectadas_pct
FROM ordenes_produccion
WHERE estado <> 'CANCELADA' AND fecha_requerida BETWEEN :inicio AND :fin;

-- KPI 6: tasa de sustitución exitosa
SELECT round(100.0 * count(DISTINCT a.sku) FILTER (WHERE EXISTS (
           SELECT 1 FROM recomendaciones_sustitucion r
           JOIN autorizaciones_sustitucion au ON au.recomendacion_id = r.recomendacion_id
           WHERE r.alerta_id = a.alerta_id AND au.decision = 'APROBADA'))
       / NULLIF(count(DISTINCT a.sku), 0), 2) AS tasa_sustitucion_exitosa_pct
FROM alertas_descontinuacion a
JOIN componente_ciclo_vida v ON v.sku = a.sku AND v.estado = 'DESCONTINUADO'
WHERE EXISTS (SELECT 1 FROM alerta_bom_afectada b WHERE b.alerta_id = a.alerta_id);
```

## 6.3 Resultados en el escenario hipotético

Valores obtenidos al ejecutar `gestor_descontinuados.py` y `sql/escenario_y_consultas.sql` (ver [evidencias](evidencias/)):

| # | KPI | AS-IS | TO-BE al detectar | TO-BE tras la sustitución | Meta | ¿Cumple? |
|---|---|---|---|---|---|---|
| 1 | Tiempo de detección | ≈ 72 h¹ | **0.25 h** | 0.25 h | ≤ 0.25 h | ✅ |
| 2 | Tiempo de sustitución | ≈ 120 h¹ | — (pendiente) | **24 h** | ≤ 48 h (CRITICA) | ✅ |
| 3 | BOM afectadas | 80 % (no medido)² | 80 % | **0 %** | 0 % al cierre | ✅ |
| 4 | Recomendaciones de compra inválidas | **25 %** (1 de 4) | 0 % | **0 %** | 0 % | ✅ |
| 5 | Órdenes de fabricación afectadas | **50 %** (2 de 4)³ | 0 % | **0 %** | < 2 % | ✅ |
| 6 | Tasa de sustitución exitosa | 0 % | 0 % | **100 %** | ≥ 90 % | ✅ |

¹ **Estimación hipotética del AS-IS.** El proveedor descontinúa la pieza el 20/11 a las 09:00. El comprador lo descubre al consultar al proveedor después de la corrida de MRP del 23/11, unas 72 h después. La investigación manual, la validación y la edición de la BOM toman unos 5 días. El AS-IS no genera alertas, así que estos valores no se pueden calcular desde el sistema. Esa imposibilidad es, en sí misma, uno de los problemas detectados.

² El valor existe, pero nadie lo conoce. En el AS-IS no hay consulta where-used multinivel, así que el responsable solo encontraría 2 de las 4 BOM (las de uso directo).

³ Las órdenes OF-1001 y OF-1002 se detienen hasta que se resuelve la sustitución.
