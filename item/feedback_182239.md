# Feedback

---

## 1. Aspectos Positivos del Esquema

* **Separación de responsabilidades:** Dividir el estado actual del inventario (`Inventory_Stock`) del historial de movimientos (`Inventory_Transaction`) es la práctica estándar correcta para garantizar la trazabilidad y el cálculo histórico en un ERP.
* **Restricción de unicidad compuesta:** La regla `UNIQUE (ItemID, Warehouse)` en `Inventory_Stock` evita duplicidad de registros para un mismo artículo dentro de un mismo almacén.
* **Validación de no negatividad:** El uso de `CHECK (QuantityAvailable >= 0)` protege la integridad física del inventario a nivel de motor de base de datos, impidiendo saldos negativos por errores en la capa de aplicación.

---

## 2. Observaciones sobre Integridad de Datos y Tipos

### A. Normalización de Almacenes (Integridad Referencial)
* **Situación actual:** Los campos `Warehouse` y `WarehouseAffected` están definidos como `VARCHAR(100)`.
* **Riesgo:** Esto permite inconsistencias de captura (por ejemplo, registrar "Almacen Central", "Almacén Central" y "ALM-01" como entidades distintas) y viola el principio de integridad referencial absoluta.
* **Solución propuesta:** Crear una tabla maestra `Warehouses` (`WarehouseID`, `Code`, `Name`, `IsActive`) y sustituir los campos de texto por llaves foráneas (`WarehouseID INT NOT NULL`).

### B. Precisión Numérica en Cantidades
* **Situación actual:** `QuantityAvailable` y `Quantity` están definidos como `INT`.
* **Riesgo:** Aunque para el ensamblaje de computadoras (piezas) los enteros funcionan, el Item Master soporta múltiples Unidades de Medida (UoM) y factores de conversión que pueden generar decimales (por ejemplo, rollos de cable, pasta térmica en gramos o insumos por peso/volumen).
* **Solución propuesta:** Cambiar el tipo de dato de todas las cantidades de inventario a `NUMERIC(14, 4)` o `DECIMAL(14, 4)`.

### C. Validación de Cantidades en Transacciones
* **Situación actual:** En `Inventory_Transaction`, la columna `Quantity` no tiene restricción de valor.
* **Riesgo:** Se podrían insertar transacciones con cantidad `0` o valores negativos que, combinados con el campo `Effect ('ADD', 'SUBTRACT')`, provocarían una doble negación lógica y corromperían el saldo.
* **Solución propuesta:** Agregar `CHECK (Quantity > 0)` en la tabla `Inventory_Transaction`.

---

## 3. Alineación con los Requerimientos del MRP y Item Master

### A. Parámetros de Planificación Multialmacén
El requerimiento de *Planificación Multialmacén* exige que cada artículo tenga políticas de reposición independientes por almacén. La tabla `Inventory_Stock` (o una tabla anexa de configuración) debe incluir:
* `SafetyStock NUMERIC(14, 4) DEFAULT 0 CHECK (SafetyStock >= 0)` (Stock de seguridad)
* `ReorderPoint NUMERIC(14, 4) DEFAULT 0 CHECK (ReorderPoint >= 0)` (Punto de reorden)
* `MinStock NUMERIC(14, 4) DEFAULT 0 CHECK (MinStock >= 0)` (Stock mínimo)
* `MaxStock NUMERIC(14, 4) CHECK (MaxStock >= MinStock)` (Stock máximo)

### B. Diferenciación de Estados del Stock para el MRP
Para que el MRP calcule correctamente los requerimientos netos de materiales (por ejemplo, al ensamblar una Gaming PC), no basta con conocer la cantidad física total. Necesitamos distinguir entre:
* `QuantityOnHand`: Existencia física real en el almacén.
* `QuantityReserved`: Cantidad comprometida o asignada a órdenes de producción o venta abiertas.
* `QuantityAvailable`: Calculado o persistido como (`QuantityOnHand - QuantityReserved`).

### C. Trazabilidad del Artículo en la Transacción
* **Observación:** En `Inventory_Transaction` existe una llave foránea hacia `Inventory_Movements(MovementID)`, pero no se observa `ItemID` ni la Unidad de Medida utilizada.
* **Consulta:** Si `Inventory_Movements` funciona como cabecera del documento (ejemplo: una recepción de compra con varios componentes distintos), el `ItemID` debe residir en `Inventory_Transaction` (el detalle). Asimismo, se debe garantizar que toda cantidad registrada en `Inventory_Transaction` esté expresada en la **Unidad de Medida Base** del artículo, o bien incluir el `UoMID` y el factor de conversión aplicado en el momento de la transacción para mantener la inmutabilidad histórica.

---

## 4. Requerimientos para la Tabla `Item_Master`

1. **Identificador de negocio:** `SKU VARCHAR(50) UNIQUE NOT NULL` (adicional a la llave primaria subrogada `ItemID`).
2. **Clasificación y Ciclo de Vida:** Campos `ItemType` (Materia Prima, Producto Terminado, Servicio, etc.) y `Status` (`ACTIVE`, `OBSOLETE`, `IN_DEVELOPMENT`, `SUSPENDED`) para bloquear transacciones en artículos no activos y evitar el borrado físico.
3. **Unidad de Medida Base:** `BaseUoMID INT NOT NULL` (inmutable si existe stock mayor a cero).
4. **Control de Concurrencia:** Un campo `RowVersion INT DEFAULT 1 NOT NULL` para implementar bloqueo optimista cuando dos usuarios editen el mismo artículo simultáneamente.
5. **Auditoría:** La creación de una tabla `Item_Master_Audit_Log` (o integración con MongoDB según la arquitectura del proyecto) que registre usuario, fecha, valor anterior y valor nuevo ante cambios en campos críticos.
