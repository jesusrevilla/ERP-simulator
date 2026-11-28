### Feedback
### schema.sql

#### Lo que está muy bien resuelto:
* **Integridad de Stock:** La restricción UNIQUE (ItemID, Warehouse) evita registros duplicados de un mismo producto en el mismo almacén, y el CHECK (QuantityAvailable >= 0) nos protege de inventarios negativos.
* **Trazabilidad:** Buen manejo de llaves foráneas (Item_Master e Inventory_Movements) y auditoría de tiempo con DEFAULT CURRENT_TIMESTAMP.

#### Puntos de mejora sugeridos:
1. **Normalización de Almacenes (Warehouse / WarehouseAffected):** 
   Actualmente el almacén se guarda como VARCHAR(100). Para evitar errores de captura (ej. *"Almacén Central"* vs *"Almacen Central"*) y facilitar reportes o traslados entre plantas, lo ideal sería tener una tabla catálogo Warehouses (WarehouseID, Name, Location) y referenciarla aquí mediante una llave foránea WarehouseID INT.
2. **Validación en Inventory_Transaction.Quantity:** 
   Falta agregar un CHECK (Quantity > 0) en la tabla de transacciones. Como ya tienen la columna Effect (ADD / SUBTRACT) para definir el sentido del movimiento, la cantidad registrada siempre debería ser estrictamente positiva.
3. **Relación directa con el Ítem en Transacciones:** 
   Aunque `MovementID` conecta con Inventory_Movements, para consultas rápidas de Kardex o historial de movimientos por producto suele ser muy útil tener `ItemID` (o asegurarnos de que Inventory_Movements lo tenga bien indexado) para no depender siempre de múltiples `JOIN`s.
4. **Tipo de dato para cantidades (INT vs DECIMAL):** 
   Si nuestro *Item Master Data* va a manejar materiales por peso, volumen o longitud (ej. kg, litros, metros) y no solo piezas enteras, convendría cambiar QuantityAvailable y Quantity a DECIMAL(12, 4). Si el alcance del simulador será únicamente por unidades enteras, `INT` está perfecto.
5. **Políticas de borrado (ON DELETE):** 
   Consideren definir explícitamente ON DELETE RESTRICT en las llaves foráneas para evitar que por error se elimine un artículo del maestro si ya tiene stock o transacciones históricas asociadas.
