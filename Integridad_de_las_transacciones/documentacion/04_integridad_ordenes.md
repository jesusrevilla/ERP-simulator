# 4. Integridad de órdenes de compra y producción

## 1. Objetivo
El objetivo del módulo MRP (Material Requirements Planning) es garantizar la correcta gestión y el rastreo de las órdenes de compra (OC) y producción (OP), asegurando que el cálculo de componentes y explosión de materiales se realice sin errores, respetando los límites de inventario y los requerimientos netos del producto terminado. Se busca asegurar la trazabilidad, prevenir sobrecostos por faltantes y mantener la consistencia operativa entre las listas de materiales y el stock físico disponible.

## 2. Archivos relacionados
- `reglas_oc_y_op/reglas_oc_y_op.md`
- `BOM/BOM_Requirements.md`
- `src/mrp.py`
- `src/check_shortages.py`
- `sql/init.sql` (tablas `bill_of_materials` y `sales_orders`)

## 3. Descripción del funcionamiento
* **Gestión de Órdenes (OC y OP):** El proceso está diseñado para generar automáticamente sugerencias de órdenes de compra cuando el stock de un material cae por debajo del punto de reorden. Las órdenes de producción se detonan cuando existe una demanda registrada de un producto terminado.
* **Cálculo de Requerimientos (MRP):** El archivo `src/mrp.py` contiene una función `calculate_mrp` que multiplica la cantidad de producto solicitada por los insumos definidos en un diccionario estático en el código.
* **Identificación de Faltantes:** El script `src/check_shortages.py` evalúa la demanda bruta conectándose a la base de datos `erpdb`. Multiplica la cantidad requerida en la tabla `bill_of_materials` por la cantidad vendida en `sales_orders`, comparando el resultado contra las existencias en `inventory` para calcular e imprimir los faltantes.

## 4. Mecanismos de integridad
* **Integridad Referencial en Base de Datos:** El archivo `sql/init.sql` protege las relaciones asignando llaves primarias y foráneas; `bill_of_materials` exige que los IDs existan previamente en las tablas `products` y `materials`, y evita campos nulos en las cantidades.
* **Reglas Estructurales del BOM:** A nivel lógico, las listas de materiales exigen que no existan ciclos jerárquicos (Grafo Acíclico Dirigido), impiden que un artículo tipo Materia Prima sea padre de un ensamble y bloquean ediciones directas sobre versiones en estado Activo.
* **Trazabilidad y Control Lógico de OC/OP:** Las políticas operativas obligan a despachar los lotes por caducidad (FEFO), exigen que los materiales reservables contemplen porcentajes de merma, e impiden autorizar pagos si la recepción de materiales no se ha completado en el sistema.

## 5. Riesgos de inconsistencia
* **Desconexión entre lógica y base de datos:** El script `src/mrp.py` calcula requerimientos basándose en un diccionario de memoria (`BOM = {"Gaming PC": {...}}`) en lugar de extraer las dependencias reales de la tabla `bill_of_materials` construida en `sql/init.sql`. Esto genera un riesgo inminente de discrepancia de datos.
* **Ausencia de restricciones de dominio numérico (Stock Negativo):** Aunque los diagramas y requerimientos especifican que el inventario no puede ser negativo y que las cantidades base del BOM deben ser mayores a cero, el archivo `sql/init.sql` omite las restricciones tipo `CHECK (stock >= 0)` o `CHECK (quantity > 0)`.
* **Condiciones de carrera por concurrencia:** El script `src/check_shortages.py` lee el inventario y calcula faltantes sin implementar bloqueos transaccionales sobre la tabla `inventory`. Si múltiples órdenes se procesan simultáneamente, el sistema podría sobrevender o asignar materiales a una OP con inventario fantasma.

## 6. Propuestas de mejora
* **Refactorizar el motor MRP:** Modificar `src/mrp.py` para eliminar el diccionario duro en el código e implementar consultas SQL directamente a `bill_of_materials`, permitiendo que el cálculo sea dinámico y dependa de la base de datos transaccional.
* **Fortalecer la base de datos (Restricciones CHECK):** Agregar restricciones de nivel de motor de base de datos en `sql/init.sql`. Por ejemplo, añadir `CHECK (quantity_required > 0)` en `bill_of_materials` y `CHECK (stock >= 0)` en la tabla `inventory`.
* **Implementar control de concurrencia:** Actualizar las consultas del sistema en Python (`check_shortages.py` y futuros módulos de reserva) usando bloqueos a nivel de fila (por ejemplo, `SELECT ... FOR UPDATE`) para aislar los cálculos de reservas e impedir que otra transacción asigne el mismo material.

## 7. Conclusión
El correcto funcionamiento del modelo MRP depende de la sincronización perfecta entre las reglas de negocio planificadas y la arquitectura técnica de la base de datos. Implementar las validaciones físicas y lógicas sobre órdenes y listas de materiales es fundamental para evitar disrupciones en la línea de producción por quiebres de stock y para mantener la integridad contable del ERP.