# Integridad de ventas y finanzas

## Objetivo

La integridad de ventas y finanzas busca que cada operación comercial tenga información correcta y relacionada con los documentos que le corresponden. Por ejemplo, un pedido debe pertenecer a un cliente y, cuando se completa este pedido, relacionarse con su entrega, factura, saldo y pagos.

Esto ayuda a evitar errores como vender a un cliente bloqueado, entregar productos que no hay o registrar un pago en una factura equivocada.

## Archivos relacionados

- `Integridad_de_las_transacciones/DiagramaModelo_175456.md`
- `Integridad_de_las_transacciones/OrderDeliveryFlow.md`
- `AR&AP/AR&AP.md`
- `Business-Partner/BusinessPartner.md`
- `Recibos y las entregas/Primera entrega.md`
- `requirements/requerimientos_y_diagrama_bpmn.md`
- `sql/init.sql`
- `src/seed_data.py`
- `src/check_shortages.py`

## Cómo funciona actualmente el proyecto

En `sql/init.sql` se crean tablas para productos, materiales, inventario, listas de materiales y pedidos de venta. El pedido de venta guarda el producto, la cantidad y la fecha.

`src/seed_data.py` agrega un pedido de venta de ejemplo. Después, `src/check_shortages.py` compara los materiales que necesita ese pedido con las existencias y muestra si hay faltantes.

El código trabaja principalmente con productos, materiales, inventario y pedidos básicos. Los documentos describen cómo se podrían manejar los clientes, el crédito, las facturas y los pagos.

## 1. Validación de clientes y proveedores

Se propone guardar los datos principales de cada cliente y proveedor, como su código, nombre fiscal e identificación fiscal. También se indica que el código no debe repetirse y que el cliente o proveedor debe estar activo para poder realizar operaciones.

Antes de aceptar un pedido, se debe revisar que el cliente no esté bloqueado. Para recibir mercancía, se debe confirmar que el proveedor esté activo.

Estas validaciones ayudan a evitar pedidos, facturas o recibos relacionados con personas o empresas incorrectas. 

## 2. Integridad de los pedidos de venta

En los diagramas se propone revisar el cliente y su crédito antes de confirmar un pedido. Después se debe comprobar que haya suficiente inventario para atenderlo.

Si el pedido no cumple alguna regla, debe detenerse. Si durante el proceso ocurre un error, se deben cancelar los cambios realizados para que no quede, por ejemplo, el inventario descontado sin que se haya registrado la factura.

La tabla `sales_orders` registra el producto, la cantidad y la fecha, pero no guarda al cliente ni el estado de aprobación o pago del pedido.

## 3. Relación entre pedidos, facturas y cuentas por cobrar

En los archvios se propone que una factura de venta debe corresponder a un cliente activo y a una operación válida. También se propone que el pedido, la entrega, la factura y la cuenta por cobrar queden relacionados para poder seguir el proceso completo.

En `AR&AP/AR&AP.md` se indica que las facturas deben tener un folio único para cada cliente o proveedor, y una fecha de vencimiento. También se plantea permitir pagos completos o parciales, siempre que el pago no sea mayor al saldo pendiente.

Hace falta tablas que registren facturas, cuentas por cobrar o pagos. 

## 4. Validación del crédito y del inventario

Antes de aceptar un pedido, los documentos proponen revisar si el cliente tiene crédito suficiente. Si supera su límite, la operación puede bloquearse o requerir autorización.

Para preparar una entrega, también se debe comprobar que haya suficientes productos físicamente disponibles. El pedido no debería enviarse si el almacén no puede cubrir la cantidad solicitada.

En `src/check_shortages.py` se revisa faltantes de materiales para el proceso de producción. Esa revisión no confirma pedidos de clientes ni valida su crédito; tampoco descuenta el inventario.

## 5. Riesgos de inconsistencias

Algunos problemas que podrían ocurrir son:

- Aceptar pedidos de clientes inexistentes o bloqueados.
- Confirmar pedidos sin revisar el crédito.
- Entregar más productos de los que hay disponibles.
- Descontar inventario sin guardar correctamente la entrega o la factura.
- Crear facturas sin relación con el pedido o el cliente.
- Repetir el folio de una factura.
- Registrar un pago mayor al saldo pendiente.
- Aplicar un pago a la factura de otro cliente.
- Dejar información distinta entre el inventario, las facturas y los pagos cuando ocurre un error.

## 6. Propuestas de mejora

Para reducir estos riesgos, se propone lo siguiente:

- Registrar clientes y proveedores en tablas propias y relacionarlos con los pedidos y las facturas.
- Evitar códigos de clientes y folios de facturas duplicados.
- Revisar que el cliente o proveedor esté activo antes de aceptar una operación.
- Comprobar el crédito antes de confirmar un pedido.
- Comprobar las existencias antes de preparar una entrega.
- Guardar juntos los cambios del inventario, la entrega y la factura. Si algo falla, cancelar todos los cambios de esa operación.
- Evitar que dos operaciones descuenten al mismo tiempo las mismas existencias.
- Revisar que un pago no exceda el saldo de la factura.
- Guardar quién hizo una cancelación o ajuste y por qué.
- Agregar pruebas para casos como cliente bloqueado, crédito insuficiente, inventario faltante, folio repetido o pago mayor al saldo.


Para que las ventas y las finanzas sean confiables, el pedido, el inventario, la entrega, la factura y los pagos deben conservar una relación clara. Agregar las validaciones y relaciones propuestas ayudaría a evitar errores y mantener la información comercial ordenada.