# Integridad de inventarios

## 1. Objetivo de la integridad de inventarios

La integridad de inventarios tiene como objetivo mantener un registro correcto y confiable de las existencias de materiales dentro del ERP. Esto implica asegurar que las cantidades disponibles correspondan con los movimientos realizados y que las operaciones de entrada, salida y transferencia se ejecuten correctamente.

También busca evitar errores como cantidades negativas, registros incorrectos o diferencias entre las existencias registradas y las disponibles físicamente en el almacén.

## 2. Cómo se administra el stock

En el proyecto, el inventario se administra mediante la tabla `inventory`, definida en el archivo `sql/init.sql`. Esta tabla almacena el identificador del material y su cantidad disponible (`stock`). Cada registro está relacionado con un material existente mediante una llave foránea.

Además, el archivo `Inventario/inventario_requerimientos.md` contempla la administración de múltiples almacenes y ubicaciones, conversiones entre unidades de medida y seguimiento de materiales mediante lotes y números de serie.

Otro aspecto importante es el cálculo de disponibilidad (ATP), que permite conocer cuánto material se encuentra disponible considerando las existencias actuales, las cantidades solicitadas a proveedores y las comprometidas en pedidos de clientes.

Por su parte, el archivo `src/check_shortages.py` consulta las órdenes de venta, las listas de materiales y las existencias para calcular los materiales necesarios. Posteriormente, compara las cantidades requeridas con el stock disponible para identificar posibles faltantes.

## 3. Validaciones de existencias y cantidades

Dentro de los archivos revisados se identifican diferentes validaciones relacionadas con el control de inventarios:

- **Validación de stock disponible:** antes de realizar una salida, el flujo de `item/item-master.mmd` establece que se debe comprobar si las existencias actuales son mayores o iguales a la cantidad solicitada.
- **Validación de materiales:** la tabla `inventory` utiliza una llave foránea que garantiza que cada registro corresponda a un material existente.
- **Validación de lotes y series:** los requerimientos establecen que los materiales que utilizan lotes o números de serie deben contar con esta información al registrar entradas, salidas o devoluciones.
- **Validación de faltantes:** el archivo `src/check_shortages.py` calcula la cantidad de materiales necesarios para las órdenes de venta y la compara con las existencias registradas.
- **Validación de almacenes:** el flujo de movimientos contempla comprobar que el almacén de destino esté activo antes de realizar una transferencia.

Estas validaciones ayudan a reducir errores durante la administración de las existencias. Sin embargo, algunas se encuentran descritas en los requerimientos y diagramas, por lo que no todas están implementadas actualmente en el código.

## 4. Cómo evitar inventarios negativos

Para evitar que las existencias de materiales sean menores a cero, el sistema debe comprobar que exista suficiente stock antes de autorizar una salida de inventario.

En el archivo `item/item-master.mmd` se representa este proceso mediante una condición que compara el stock actual con la cantidad solicitada. Si las existencias no son suficientes, la operación debe bloquearse para evitar un inventario negativo.

También se propone utilizar restricciones en la base de datos, como `CHECK (stock >= 0)`, para impedir que se registren cantidades negativas.

Otra medida importante es utilizar transacciones y bloqueos de registros cuando varios usuarios intenten modificar las mismas existencias al mismo tiempo. De esta manera, se evita que dos operaciones descuenten simultáneamente unidades que ya no están disponibles.

Es importante mencionar que actualmente la tabla `inventory` cuenta con una restricción `NOT NULL` para el campo `stock`, pero no tiene una restricción `CHECK` que impida almacenar valores negativos.

## 5. Riesgos de inconsistencias en entradas y salidas

Una administración incorrecta de los movimientos de inventario puede provocar diferentes problemas dentro del ERP. Entre los principales riesgos se encuentran:

- **Inventario negativo:** puede ocurrir cuando se permite retirar una cantidad mayor a la disponible.
- **Diferencias en las existencias:** si una entrada o salida no actualiza correctamente el inventario, las cantidades registradas pueden dejar de coincidir con las existencias reales.
- **Movimientos duplicados:** registrar dos veces una misma entrada o salida puede provocar cantidades incorrectas.
- **Problemas de concurrencia:** cuando varios usuarios modifican el mismo inventario al mismo tiempo, pueden producirse errores en las cantidades disponibles.
- **Transferencias incorrectas:** si no se valida adecuadamente el almacén de origen y destino, los materiales pueden quedar registrados en ubicaciones equivocadas.
- **Falta de trazabilidad:** no registrar correctamente los lotes y números de serie dificulta identificar el origen y seguimiento de los materiales.

Estos problemas pueden afectar otros procesos del ERP, especialmente la producción y el cumplimiento de las órdenes de venta.

## 6. Propuestas para mantener la consistencia de los movimientos de inventario

Para mejorar el control de las existencias y reducir los errores durante las operaciones, se proponen las siguientes medidas:

1. **Agregar restricciones a la base de datos:** implementar una condición `CHECK (stock >= 0)` en la tabla `inventory` para impedir el registro de cantidades negativas.

2. **Utilizar transacciones:** ejecutar las entradas, salidas y transferencias mediante transacciones de base de datos. Si ocurre un error durante el proceso, se debe utilizar `ROLLBACK` para cancelar los cambios y evitar que el inventario quede en un estado inconsistente.

3. **Implementar bloqueos de registros:** utilizar mecanismos como `SELECT FOR UPDATE` en PostgreSQL para evitar que varios usuarios modifiquen simultáneamente las mismas existencias sin control.

4. **Registrar todos los movimientos:** implementar un historial que almacene las entradas, salidas y transferencias realizadas, incluyendo el material, la cantidad, el tipo de movimiento y la fecha.

5. **Validar las transferencias:** comprobar que exista suficiente stock en el almacén de origen y que el almacén de destino esté activo antes de completar el movimiento.

6. **Fortalecer la trazabilidad:** asegurar que los materiales que requieren control por lotes o números de serie tengan esta información registrada en cada movimiento correspondiente.

Con estas mejoras sería posible mantener un control más confiable de las existencias, reducir errores en las operaciones y asegurar que los datos del inventario permanezcan consistentes durante el funcionamiento del ERP.

Este documento, no es de este modulo
