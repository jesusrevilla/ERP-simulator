# Comentarios a los SQL – A/R y A/P

| Matrícula | Archivo original |
|---|---|
| 181585 | Comentarios_SQL_181585.md |
| 181779 | Recomendaciones Farfan (para DB).md |
| 182028 | Retroalimentación - 182028 |

---

## 181585

### tablas.sql (OrdenesCompra)
- La coma de ProveedorID quedó dentro del comentario y la tabla no se crea.
- A Estatus y CreadoPor les falta NOT NULL.
- Falta IF NOT EXISTS.

### azul_ventas.sql (pedidos_venta)
- Falta CHECK (total = subtotal + iva).
- A estatus le falta NOT NULL.
- La tabla clientes debe existir antes.

### Tablas-Alexis.sql (condiciones_pago e impuestos)
- A nombre le falta UNIQUE.
- Faltan los datos iniciales: contado, 15, 30 y 60 días; IVA 16 %, 0 % y exento.
- Falta IF NOT EXISTS.

### miriam_contabilidad.sql (CuentasContables)
- Está completa.

### General
- Usar un solo estilo de nombres: snake_case o PascalCase.
- Usar DECIMAL o NUMERIC, no los dos.
- El folio debe medir lo mismo en todas las tablas.
- Orden de ejecución: catálogos → clientes y proveedores → pedidos y órdenes de compra.

---

## 181779

Comentarios enfocados en algunos datos que puede que hagan falta para el módulo del MRP.

### Tablas con las que debemos relacionarnos (por si ya existen en módulos de otros equipos)
- proveedores
- clientes
- monedas y tipo de cambio
- métodos de pago
- bancos y cuentas bancarias
- materials

### Tablas que también sería apropiado tener para el módulo
- Facturas del proveedor
- Facturas del cliente

### Notas
- Hay algunos errores de sintaxis en algunos códigos (OrdenesCompra); también sería bueno estandarizar los nombres.
- Las tablas deben tener relaciones entre sí y eso se debe empezar desde el inicio para que la estructura quede bien hecha. Por ejemplo: condiciones_pago debería vincularse a proveedores y clientes.

---

## 182028

### 1. Catálogos (condiciones de pago e impuestos)
- **Cumple:** nos dan los días de crédito y el IVA.
- **Ajuste:** que el IVA se pueda cambiar y que se puedan desactivar en vez de borrar.

### 2. Pedidos de venta
- **Cumple a medias:** es la base para facturar a clientes.
- **Falta:** que indique los días de crédito del pedido, que el total cuadre con subtotal + IVA, y la tabla de clientes.

### 3. Contabilidad (Miriam)
- **Cumple a medias:** tiene las cuentas, pero no hay dónde registrar los movimientos de cobros y pagos.
- **Falta:** los asientos contables y la bitácora de cambios (que pedimos para cancelaciones y ajustes).

### 4. Órdenes de compra
- **Cumple a medias:** es la base para facturas de proveedores.
- **Falta:** conectarla con la tabla de proveedores y que indique los días de crédito.
