# Reporte de Revisión y Alineación: Módulo de Reglas de Órdenes de Compra (OC) y Órdenes de Producción (OP)

## 1. Validación de Correspondencia Documental

Tras revisar el archivo [`Integridad_de_las_transacciones/documentacion/04_integridad_ordenes.md`](Integridad_de_las_transacciones/documentacion/04_integridad_ordenes.md), se confirma que **sí corresponde directamente al módulo de "Reglas de orden de compra y orden de producción"**. 

En dicho documento se abordan explícitamente:
- El objetivo del MRP respecto al rastreo, explosión de materiales y gestión de **Órdenes de Compra (OC)** y **Órdenes de Producción (OP)**.
- La referencia directa al archivo maestro del módulo (`reglas_oc_y_op/reglas_oc_y_op.md`) junto con los scripts `src/mrp.py`, `src/check_shortages.py` y `sql/init.sql`.
- Los mecanismos de integridad propios del módulo, tales como la asignación de lotes por caducidad (**FEFO**), el cálculo de porcentajes de merma/scrap, la validación de puntos de reorden, la prevención de stock negativo y el bloqueo de pagos de OC sin recepción previa.

---

## 2. Solicitud de Integración en la Carpeta `reglas_oc_y_op/`

Dado que el contenido de `04_integridad_ordenes.md` documenta la arquitectura, riesgos de concurrencia y reglas de integridad de este módulo, **es necesario agregar e integrar esta información específica dentro del directorio [`reglas_oc_y_op/`](reglas_oc_y_op/)**. 

Esto permitirá centralizar en una sola ubicación:
1. Los requerimientos funcionales y reglas de negocio (`reglas_oc_y_op.md`).
2. La base de conocimiento y eventos de integridad bajo el estándar ISA-95 (`.json`).
3. El análisis de integridad transaccional y estructural de las órdenes (`04_integridad_ordenes.md`).

---

## 3. Observación Crítica: Falta de Tablas SQL Específicas del Módulo OC y OP

Durante la revisión de los scripts SQL del repositorio (principalmente `sql/init.sql`), se identificó que actualmente solo existen las tablas base de catálogos y demanda (`products`, `materials`, `inventory`, `bill_of_materials` y `sales_orders`), pero **hacen falta los scripts SQL con las tablas específicas del módulo de Reglas de Órdenes de Compra y Órdenes de Producción**.

Para cumplir con las reglas de negocio e integridad definidas en el módulo, se requiere crear e incorporar en `reglas_oc_y_op/` el esquema SQL que contemple las siguientes tablas y restricciones:

1. **Tabla de Órdenes de Producción (`ordenes_produccion`):**
   - Campos para `id_op`, `product_id`, `cantidad_programada`, `cantidad_real_producida`, `scrap_real`, `centro_trabajo`, fechas de ejecución y restricción `CHECK` de estados (`Planeada`/`Liberada`, `En Preparación`/`En Proceso`, `Paro de Línea`, `Finalizada con Desvío`/`Completada`, `Cerrada`/`Cancelada`).
2. **Tabla de Órdenes de Compra y Líneas de Detalle (`ordenes_compra` y `ordenes_compra_detalle`):**
   - Soporte para el flujo completo de aprovisionamiento e inspección: `id_oc`, `id_proveedor`, `id_material`, `cantidad_solicitada`, `cantidad_aceptada`, `cantidad_rechazada`, `precio_unitario` (`CHECK >= 0`), tolerancia de entrega ($\pm 5\%$) y control de estados (`Pendiente`/`Emitida`, `En Aduana/Tránsito`, `Inspección de Calidad`, `Recibida`, `Cerrada Conforme`/`Pagada`, `Devuelta`).
3. **Tabla de Lotes y Límites de Inventario (`lotes_inventario` / ampliación de `inventory`):**
   - Atributos necesarios para ejecutar las reglas del MRP y **FEFO**: `id_lote`, `stock_fisico` (`CHECK >= 0`), `stock_reservado`, `stock_en_transito`, `stock_minimo`, `stock_maximo`, `punto_reorden`, `fecha_fabricacion`, `fecha_caducidad` (`CHECK > fecha_fabricacion`) y `ubicacion_almacen` (para aislar el almacén lógico de `Inspección/Calidad`).
4. **Tabla de Trazabilidad y Consumo de Lotes por OP (`op_lotes_consumidos`):**
   - Relación matricial entre la Orden de Producción (`id_op`), los lotes de materia prima consumidos (`id_lote_mp`) y el lote de producto terminado generado, indispensable para garantizar la genealogía de lote y el balance de masa en producción.
