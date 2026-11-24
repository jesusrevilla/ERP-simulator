# Reglas de negocio para la integridad del inventario

## Objetivo

Este documento reúne las reglas que ayudan a conservar cantidades confiables durante las entradas, salidas y transferencias de inventario. También señala qué controles existen en los archivos revisados y cuáles se proponen como mejora.

## Archivos relacionados

- `Integridad_de_las_transacciones/IntegridadDiego.md`
- `Inventario/inventario_requerimientos.md`
- `item/item-master.mmd`
- `sql/Inventory_Stock.sql`
- `sql/Inventory_Movements.sql`
- `sql/Inventory_transsction.sql`
- `sql/Warehouse.sql`
- `sql/Item_Batch`

## Descripción del funcionamiento actual

Los requerimientos describen el uso de varios almacenes, el registro de movimientos, el seguimiento por lote o número de serie y el cálculo de cantidades disponibles. El diagrama de artículo representa la comprobación de existencias antes de aceptar una salida.

En los scripts SQL aparecen tablas para existencias, movimientos, transacciones, almacenes y lotes. Hay dos definiciones de movimientos con estructuras distintas: una guarda los almacenes como texto y otra utiliza identificadores relacionados con la tabla de almacenes. Por eso, antes de conectar nuevas reglas, se debe confirmar cuál estructura utiliza cada flujo.

## Mecanismos de integridad existentes

- Las cantidades de las tablas de movimientos y transacciones deben ser mayores que cero.
- `Inventory_Stock` limita las existencias físicas y reservadas para que no sean negativas.
- `Inventory_Stock` tiene llaves foráneas hacia el artículo, el almacén y el lote.
- `Inventory_Transaction` relaciona el artículo, los almacenes de origen y destino, y el lote mediante llaves foráneas.
- `Warehouse` identifica almacenes y permite registrar si están activos.
- `Item_Batch` relaciona cada lote con un artículo y registra su estado y fecha de vencimiento.

Estos controles ayudan a conservar referencias válidas, pero no todas las reglas operativas quedan cubiertas por las tablas. Por ejemplo, las definiciones no muestran una regla que exija que una transferencia tenga dos almacenes diferentes ni una llave que permita reconocer con certeza el reenvío duplicado de una operación.

## Reglas de integridad

### Entradas

Una entrada debe identificar el artículo, la cantidad recibida y el almacén que la recibe. Si el artículo requiere lote o número de serie, esa información debe registrarse antes de aceptar el movimiento. La cantidad debe ser mayor que cero.

### Salidas

Antes de una salida, el sistema debe revisar que la cantidad disponible alcance para cubrirla. La disponibilidad debe considerar las unidades reservadas, para no comprometer las mismas existencias en más de una operación. Si no hay suficiente stock, la salida debe detenerse sin reducir el inventario.

### Transferencias

Una transferencia debe tener un almacén de origen y otro de destino válidos y activos. El origen y el destino deben ser distintos. El origen debe contar con la cantidad solicitada; el movimiento debe descontar esa cantidad del origen y sumarla al destino como una sola operación.

### Lotes y números de serie

Cuando un artículo requiere trazabilidad, cada movimiento debe conservar su lote o número de serie. El lote debe pertenecer al artículo y no debe estar vencido ni bloqueado para una operación de salida. Los archivos revisados contienen una relación para lotes; la obligatoriedad de los números de serie y su validación no se encuentra cubierta de forma uniforme en todos los scripts.

### Movimientos duplicados y cantidades incorrectas

Cada movimiento debe conservar una referencia que permita rastrear el documento que lo originó. Si llega de nuevo la misma solicitud, el sistema debe reconocerla y evitar aplicar el descuento o la entrada por segunda vez. Para evitar diferencias, los cambios de existencias en una transferencia deben confirmarse juntos o revertirse juntos.

## Riesgos de inconsistencia

- Una salida mayor que el stock disponible puede generar existencias negativas.
- Un artículo reservado puede ser utilizado por otra salida si no se considera la cantidad reservada.
- Una transferencia puede quedar descontada del origen sin reflejarse en el destino.
- Un almacén inactivo o incorrecto puede recibir o entregar mercancía.
- Un lote vencido, bloqueado o de otro artículo puede usarse por error.
- Repetir un mensaje o documento puede duplicar un movimiento.
- Las dos estructuras distintas de movimientos pueden generar consultas o registros incompatibles si se mezclan.

## Propuestas de mejora

- Confirmar cuál tabla de transacciones es la estructura oficial de cada flujo y documentar su uso.
- Validar stock disponible antes de aprobar una salida.
- Exigir almacenes válidos y distintos para una transferencia.
- Usar una transacción de base de datos para aplicar los dos lados de la transferencia; revertirla si alguna actualización falla.
- Conservar una referencia única de operación para identificar reintentos y evitar duplicados.
- Exigir lote o serie solo para los artículos que así lo requieran y verificar su estado antes de una salida.
- Registrar el motivo y la referencia de los ajustes y cancelaciones para mantener trazabilidad.


## Conclusión

Las llaves foráneas y las restricciones de cantidad de los scripts ofrecen una base para cuidar el inventario. Para conservar la misma cantidad en todos los almacenes, además es necesario validar disponibilidad, trazabilidad, duplicados y transferencias completas antes de confirmar cada movimiento.
