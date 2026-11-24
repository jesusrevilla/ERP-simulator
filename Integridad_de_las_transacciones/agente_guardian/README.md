# Agente Guardián — Conciliación de integridad

**Área:** Integridad de las transacciones del ERP-Simulator.  
**Implementación:** `agente.py` (Python y SQLite).

## Propósito

El agente **detecta inconsistencias después de registrar transacciones**. Complementa al `GestorTransaccionalERP`, que realiza las ventas usando `COMMIT` y `ROLLBACK`; el Agente Guardián **no confirma ventas ni modifica datos**.

## ¿Qué revisa?

- **Inventario:** compara las existencias de cada producto con la suma de sus movimientos (entradas, salidas y ajustes).
- **Ventas:** verifica que los productos de una venta confirmada tengan sus salidas de almacén y que una cancelación incluya los movimientos inversos.
- **Compras:** comprueba que las recepciones coincidan con las cantidades de las compras confirmadas.
- **Auditoría:** identifica confirmaciones y cancelaciones sin el registro de seguimiento esperado, así como documentos con registros repetidos.
- **Relaciones:** detecta movimientos sin su documento de origen y referencias inválidas.

## Resultado

Devuelve un resumen con el número de productos, ventas y compras revisadas, junto con una lista de alertas. Cada alerta indica el problema, el documento o producto involucrado y los valores que no coinciden. **El agente no corrige ni elimina información automáticamente**, para evitar ajustes no autorizados.

## Alcance

Implementa una comprobación práctica del **RF-12: conciliación entre módulos**, y ayuda a revisar la trazabilidad del **RF-07** y la integridad de datos. Trabaja sobre las tablas `commercial_*` del prototipo comercial SQLite ya existente en el repositorio; **no crea tablas propias**. El esquema PostgreSQL/MRP principal es diferente y requerirá una adaptación para integrarse.

La revisión de asientos contables no forma parte de este agente porque el esquema comercial SQLite actual no contiene pólizas contables. No se necesita ningún archivo JSON para esta funcionalidad.
