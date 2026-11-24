# Modelo de datos para integridad de inventario, ventas y finanzas

## Propósito

El siguiente modelo resume las entidades que aparecen en los scripts y las relaciones necesarias para analizar la intergidad de inventario y de ventas y finanzas. Es un modelo de referencia: el repositorio contiene más de una propuesta de esquema.

## Archivos de referencia

- `sql/Item_Batch`
- `sql/Inventory_Stock.sql`
- `sql/Inventory_Movements.sql`
- `sql/Inventory_transsction.sql`
- `sql/Warehouse.sql`
- `AR&AP/azul_ventas.sql`

## Diagrama entidad-relación

~~~mermaid
erDiagram
    ITEM_MASTER ||--o{ INVENTORY_STOCK : "tiene existencias"
    WAREHOUSE ||--o{ INVENTORY_STOCK : "guarda"
    ITEM_BATCH o|--o{ INVENTORY_STOCK : "identifica lote"
    ITEM_MASTER ||--o{ ITEM_BATCH : "se controla por lote"
    ITEM_MASTER ||--o{ INVENTORY_TRANSACTION : "se mueve"
    WAREHOUSE o|--o{ INVENTORY_TRANSACTION : "origen o destino"
    ITEM_BATCH o|--o{ INVENTORY_TRANSACTION : "se rastrea"
    CLIENTES ||--o{ PEDIDOS_VENTA : "realiza"
    PEDIDOS_VENTA ||--|{ PEDIDO_LINEA : "contiene"
    CLIENTES ||--o{ FACTURAS_CLIENTE : "recibe"
    PEDIDOS_VENTA o|--o{ FACTURAS_CLIENTE : "se factura"
    FACTURAS_CLIENTE ||--|{ FACTURA_CLIENTE_LINEA : "detalla"
    CLIENTES ||--o{ COBROS : "realiza"
    COBROS ||--o{ COBRO_APLICACION : "se aplica"
    FACTURAS_CLIENTE ||--o{ COBRO_APLICACION : "recibe pagos"
~~~

## Entidades consideradas

- **Item_Master:** catálogo de artículos que identifica cada producto.
- **Inventory_Stock:** existencias físicas y reservadas por artículo, almacén y lote.
- **Warehouse:** almacenes disponibles y su estado.
- **Item_Batch:** lotes asociados a un artículo, con estado y fechas.
- **Inventory_Transaction:** entrada, salida, transferencia o ajuste de inventario.
- **clientes:** clientes relacionados con pedidos, facturas y cobros.
- **pedidos_venta** y **pedido_linea:** encabezado y renglones de un pedido.
- **facturas_cliente** y **factura_cliente_linea:** factura y sus renglones.
- **cobros** y **cobro_aplicacion:** pagos recibidos y su asignación a facturas.

## Relaciones y límites observados

Las relaciones de inventario se basan en las llaves foráneas definidas en los scripts de `sql/`. La tabla `Inventory_Movements` aparece en otro script y almacena los almacenes como texto; por ello no se agrega al diagrama relacional principal, que representa la estructura de `Inventory_Transaction`.

Las tablas comerciales se definen en `AR&AP/azul_ventas.sql` y referencian `clientes`, cuya definición se encuentra en otro archivo del repositorio. Este diagrama muestra relaciones conceptuales entre las definiciones disponibles; no afirma que los distintos scripts alternativos ya estén instalados juntos en una base de datos.

## Consulta de eventos de MongoDB

La carga del workflow manual guarda los eventos de integridad en `erpdb.integridad_transacciones`. Para consultarlos desde `mongosh`:

~~~javascript
use erpdb
db.integridad_transacciones.find(
  { topic: "integridad_de_las_transacciones" },
  { _id: 1, source_file: 1, event_id: 1, event_type: 1 }
).limit(10)
~~~
