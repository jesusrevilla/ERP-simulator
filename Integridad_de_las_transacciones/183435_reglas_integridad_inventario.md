# Reglas de negocio para la integridad del inventario

## 1. Objetivo y alcance

Este documento reúne las reglas que protegen las existencias durante entradas, salidas y transferencias. 

## 2. Reglas para entradas, salidas y transferencias

El flujo de `item/item-master.mmd` distingue tres tipos: **Entrada**, **Salida** y **Transferencia**.

| Operación | Regla de negocio | Estado en los archivos revisados |
| --- | --- | --- |
| Entrada | Verificar la mercancía y su lote o serie antes de procesarla; después registrar el movimiento. | El diagrama lo representa. `Inventory_Movements` acepta `ENTRADA`, requiere `Quantity > 0` y permite guardar `LotOrSerial`, pero no exige su captura ni aplica el alta al stock por sí sola. |
| Salida | Seleccionar el artículo y comprobar que el stock del almacén de origen cubra la cantidad solicitada. Si no alcanza, bloquear la operación. | El diagrama representa la validación. El SQL de `Inventory_Movements` no contiene una consulta o restricción que compare `Quantity` contra las existencias. |
| Transferencia | Validar origen y destino; descontar del origen y sumar al destino. | El diagrama representa el descuento, la validación del destino activo y el incremento. No se encontró esa lógica implementada en el SQL revisado. |

En `sql/Inventory_Movements.sql`, la tabla `Inventory_Movements` guarda `MovementID`, `ItemID`, `MovementType`, `Quantity`, `SourceWarehouse`, `DestinationWarehouse`, `LotOrSerial`, `Status` y `CreatedAt`. Las restricciones actuales limitan `MovementType` a `ENTRADA`, `SALIDA` o `TRANSFERENCIA`, exigen una cantidad positiva y relacionan `ItemID` con `Item_Master(ItemID)`.

## 3. Validación de stock y prevención de existencias negativas

Antes de una salida, la cantidad disponible en el almacén de origen debe ser mayor o igual a la cantidad solicitada:

```text
stock_origen >= cantidad_solicitada
```

Si la condición no se cumple, el flujo de `item/item-master.mmd` bloquea la operación con la regla de cero inventario negativo. La transferencia también debe superar esta validación antes de descontar unidades del origen.

**Limitación de implementación:** la tabla `Inventory_Movements` valida que `Quantity > 0`, pero no verifica el saldo. En `sql/item_master.sql`, `Inventory_Stock.QuantityAvailable` sí tiene `CHECK (QuantityAvailable >= 0)`. Sin embargo, esa tabla no está enlazada con `Inventory_Movements` mediante una operación que aplique los cambios. En `sql/init.sql`, la tabla `inventory` tiene `stock INTEGER NOT NULL`, sin `CHECK (stock >= 0)`. Por tanto,la protección contra stock negativo está cubierta por todos los esquemas.

**Mejora propuesta:** validar y actualizar el saldo de forma atómica en una transacción de base de datos. Si el saldo ya no alcanza al momento de actualizar, se rechaza la salida; no basta con leerlo antes y actualizarlo después, porque dos operaciones simultáneas podrían consumir las mismas unidades.

## 4. Validación de almacenes en transferencias

La transferencia necesita almacenes de origen y destino correctos para no descontar de una ubicación equivocada ni acreditar una ubicación inválida. El diagrama indica validar que el destino esté activo antes de sumar las existencias. También debe comprobarse que ambos almacenes sean distintos y que el origen tenga stock suficiente.

**Representado:** `SourceWarehouse` y `DestinationWarehouse` están definidos en `Inventory_Movements`; el diagrama contempla revisar el destino activo.

**Pendiente:** los campos de almacén son texto (`VARCHAR(100)`) y no tienen `NOT NULL` condicional, llave foránea a un catálogo de almacenes ni validación de estado activo. Tampoco se ve en el SQL que una transferencia genere conjuntamente el descuento del origen y el incremento del destino. Se propone usar identificadores de almacén relacionados con un catálogo y confirmar ambos cambios dentro de la misma transacción; ante un fallo debe revertirse el conjunto.

## 5. Validación de lotes y números de serie

El diagrama solicita verificar lotes/series al recibir mercancía. Los requerimientos de `Inventario/inventario_requerimientos.md` también piden trazabilidad según el tipo de artículo: lote y caducidad para artículos gestionados por lote, o número de serie para artículos seriados, en los movimientos aplicables.

En `Inventory_Movements`, el campo disponible para este dato es `LotOrSerial VARCHAR(50)`. Es nullable y el esquema no muestra campos separados para indicar si representa lote o serie, su caducidad, una tabla de lotes/series ni una regla que obligue a capturarlo de acuerdo con el artículo. Por ello, el campo permite almacenar el dato, pero no garantiza la trazabilidad exigida.

**Mejora propuesta:** identificar en el maestro si el artículo se controla por lote, por serie o sin trazabilidad; exigir el dato correspondiente antes de guardar el movimiento y validar que exista y tenga saldo disponible para una salida. Para lotes, validar también la caducidad cuando aplique. Para artículos seriados, evitar reutilizar un mismo número de serie en más de una unidad disponible.

## 6. Movimientos duplicados y cantidades incorrectas

Los riesgos principales que pueden alterar el inventario son:

- Registrar dos veces una misma solicitud de entrada o salida.
- Reintentar una petición después de un tiempo de espera y crear otro movimiento, aunque el primero sí se haya guardado.
- Actualizar el saldo y fallar antes de guardar el movimiento, o guardar el movimiento y fallar antes de actualizar el saldo.
- Ejecutar dos salidas concurrentes con base en la misma lectura de stock.
- Capturar una cantidad incorrecta, cero o negativa. `Inventory_Movements.Quantity > 0` rechaza cero y negativos, pero no detecta un número positivo equivocado.
- Confundir el artículo, el almacén de origen/destino o el lote/serie.
- Aplicar una conversión de unidad incorrecta; los requerimientos contemplan conversiones UoM, pero el esquema de movimientos revisado no muestra unidad ni factor de conversión.

El `MovementID` identifica cada fila, pero por sí solo no evita que la misma operación de negocio se inserte dos veces con dos identificadores distintos. Se recomienda asociar una clave única de solicitud/documento externo y rechazar reintentos duplicados.

## 7. Ejemplos de aceptación y rechazo

Los siguientes ejemplos ilustran las reglas; son escenarios esperados, no pruebas de que ya exista un servicio que los ejecute.

| Caso | Datos | Resultado esperado |
| --- | --- | --- |
| Entrada válida | `MovementType = 'ENTRADA'`, `Quantity = 8`, artículo existente y lote/serie capturado cuando aplique. | Aceptar el movimiento y aumentar el stock una sola vez. |
| Salida válida | Stock del origen = 12; `MovementType = 'SALIDA'`; `Quantity = 5`. | Aceptar y dejar 7 unidades en el origen. |
| Salida sin stock suficiente | Stock del origen = 4; cantidad solicitada = 6. | Rechazar sin modificar el saldo ni dejar un movimiento como procesado. |
| Transferencia válida | Origen activo con 10 unidades; destino activo y distinto; cantidad = 3. | Descontar 3 del origen y sumar 3 al destino como una sola operación. |
| Transferencia inválida | Destino inexistente/inactivo, origen igual al destino o stock insuficiente. | Rechazar y mantener sin cambios ambos saldos. |
| Trazabilidad incompleta | Artículo gestionado por lote o serie y `LotOrSerial` vacío o inválido. | Rechazar según la política de trazabilidad del artículo. |
| Cantidad inválida | `Quantity = 0` o negativa. | Rechazar; el `CHECK (Quantity > 0)` de `Inventory_Movements` ya lo impide al insertar en esa tabla. |
| Artículo inexistente | `ItemID` no presente en `Item_Master`. | Rechazar; la llave foránea `fk_item_master` ya protege esta relación en `Inventory_Movements`. |

## 8. Mejoras para mantener la consistencia

1. **Unificar el flujo de movimientos y existencias:** definir cuál modelo es el oficial y enlazar el registro del movimiento con la actualización de stock por artículo y almacén.
2. **Aplicar transacciones ACID:** en una transferencia, actualizar origen, destino y movimiento dentro de la misma transacción; usar `ROLLBACK` si falla cualquier paso.
3. **Controlar concurrencia:** bloquear o actualizar condicionalmente el registro de stock para que dos salidas simultáneas no consuman el mismo saldo.
4. **Agregar restricciones de almacén:** crear catálogo de almacenes y referenciarlo desde origen/destino; validar almacenes activos y exigir ambos campos para transferencias.
5. **Completar reglas de lote/serie:** hacer obligatoria la trazabilidad según la configuración del artículo y validar existencia, caducidad, disponibilidad y unicidad del número de serie.
6. **Evitar duplicados:** agregar una clave de idempotencia o referencia de documento única para que un reintento no aplique dos veces el movimiento.
7. **Fortalecer las cantidades:** exigir cantidad positiva en todos los esquemas de existencias y movimientos, impedir saldos negativos y registrar unidad/factor cuando se permitan conversiones.
8. **Conservar auditoría:** no editar o borrar movimientos ya aplicados; corregirlos mediante una reversa vinculada al movimiento original, manteniendo usuario, fecha y motivo.
