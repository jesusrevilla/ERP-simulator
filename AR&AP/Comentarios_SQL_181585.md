# Comentarios a los SQL

## tablas.sql (OrdenesCompra)
- La coma de ProveedorID quedó dentro del comentario y la tabla no se crea.
- A Estatus y CreadoPor les falta NOT NULL.
- Falta IF NOT EXISTS.

## azul_ventas.sql (pedidos_venta)
- Falta CHECK (total = subtotal + iva).
- A estatus le falta NOT NULL.
- La tabla clientes debe existir antes.

## Tablas-Alexis.sql (condiciones_pago e impuestos)
- A nombre le falta UNIQUE.
- Faltan los datos iniciales: contado, 15, 30 y 60 días; IVA 16 %, 0 % y exento.
- Falta IF NOT EXISTS.

## miriam_contabilidad.sql (CuentasContables)
- Está completa.

## General
- Usar un solo estilo de nombres: snake_case o PascalCase.
- Usar DECIMAL o NUMERIC, no los dos.
- El folio debe medir lo mismo en todas las tablas.
- Orden de ejecución: catálogos → clientes y proveedores → pedidos y órdenes de compra.
