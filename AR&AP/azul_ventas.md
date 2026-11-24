# Módulo de Cuentas por Cobrar (A/R) y Ventas

## 1. Descripción del módulo
En este módulo se encargó de diseñar las tablas y reglas de negocio correspondientes al área de **Cuentas por Cobrar (A/R) y Ventas** dentro de PostgreSQL. 
El objetivo de esta estructura es llevar el control completo del flujo comercial: desde que un cliente realiza un pedido, se genera su factura, se registran sus pagos (ya sean totales o en parcialidades) y, en caso de requerirse, se aplica una nota de crédito por devolución o descuento.

Toda esta estructura se relaciona directamente con la tabla `clientes` desarrollada previamente en el módulo de Datos Maestros.

---

## 2. Tablas implementadas en PostgreSQL
Para cubrir el ciclo de ventas completo, se crearon 7 tablas principales dentro del archivo `azul_ventas.sql`:

### `pedidos_venta` y `pedido_linea`
* **`pedidos_venta`:** Almacena los datos generales del pedido del cliente. Incluye la llave primaria `pedido_id`, un `folio` único, la llave foránea `cliente_id`, la `fecha`, el `estatus` (`A` = Abierto, `C` = Cerrado, `X` = Cancelado) y los importes (`subtotal`, `iva`, `total`). También integra campos de auditoría (`creado_por`, `fecha_creacion`, `modificado_por`).
* **`pedido_linea`:** Registra el detalle de cada artículo solicitado en el pedido (`linea_id`, `pedido_id`, `articulo`, `cantidad`, `precio_unitario`). Cuenta además con el campo `cantidad_facturada` para controlar si el pedido ya se facturó por completo o de manera parcial.

### `facturas_cliente` y `factura_cliente_linea`
* **`facturas_cliente`:** Representa la factura generada a partir de un pedido. Almacena `factura_id`, `folio` único, `cliente_id`, `pedido_id` (referencia al pedido origen), `fecha`, `fecha_vencimiento`, `estatus`, `subtotal`, `iva`, `total` y el `saldo` pendiente por cobrar.
* **`factura_cliente_linea`:** Detalla los artículos específicos que se cobran en cada factura, enlazados a `pedido_linea` mediante `pedido_linea_id`.

### `cobros` y `cobro_aplicacion`
* **`cobros`:** Registra los ingresos recibidos por pagos de los clientes (`cobro_id`, `folio`, `cliente_id`, `fecha`, `monto`, `metodo_pago`).
* **`cobro_aplicacion`:** Tabla intermedia que permite relacionar un mismo pago con una o varias facturas, o bien registrar pagos parciales, indicando el `monto_aplicado` a cada documento.

### `notas_credito_cliente`
* Permite registrar descuentos o devoluciones aplicados sobre una factura emitida. Contiene `nota_id`, `folio`, `factura_id`, `cliente_id`, `fecha`, el `motivo` de la operación y sus montos (`subtotal`, `iva`, `total`).

---

## 3. Reglas de negocio e integridad transaccional

Para evitar inconsistencias en los datos y asegurar la integridad de las operaciones, se establecieron las siguientes restricciones directamente en la base de datos:

* **Protección de historial (`ON DELETE RESTRICT`):** Todas las llaves foráneas (`cliente_id`, `pedido_id`, `factura_id`, `cobro_id`) cuentan con la regla `ON DELETE RESTRICT`. De este modo, si un cliente ya tiene pedidos o facturas asociadas, el sistema impide su eliminación; en su lugar, se inactiva su registro en el catálogo.
* **Validaciones de cantidades y montos (`CHECK`):** 
  * No se permiten cantidades en cero o negativas (`CHECK (cantidad > 0)`) ni precios negativos (`CHECK (precio_unitario >= 0)`).
  * El total siempre debe coincidir con la suma del subtotal más el IVA (`CHECK (total = subtotal + iva)`).
  * El saldo pendiente no puede superar el total de la factura (`CHECK (saldo <= total)`).
  * La fecha de vencimiento no puede ser anterior a la fecha de emisión (`CHECK (fecha_vencimiento >= fecha)`).
* **Precisión monetaria:** Todos los campos relacionados con dinero se definieron con `NUMERIC(12,2)` en lugar de `FLOAT` para evitar pérdidas de precisión decimal en los cálculos.
* **Prevención de aplicaciones duplicadas:** En `cobro_aplicacion` se incluyó la restricción `UNIQUE(cobro_id, factura_id)` para evitar que un mismo cobro se aplique dos veces a la misma factura.
* **Optimización de consultas (Índices):** Se crearon índices en los campos de consulta frecuente (`cliente_id`, `fecha`, `estatus` y `fecha_vencimiento`) para agilizar la generación de estados de cuenta y reportes de antigüedad de saldos.

### Ejemplo de validación en código (`facturas_cliente`)
```sql
CREATE TABLE facturas_cliente (
    factura_id SERIAL PRIMARY KEY,
    folio VARCHAR(20) UNIQUE NOT NULL,
    cliente_id INT NOT NULL REFERENCES clientes(id_cliente) ON DELETE RESTRICT,
    pedido_id INT REFERENCES pedidos_venta(pedido_id) ON DELETE RESTRICT,
    fecha DATE NOT NULL,
    fecha_vencimiento DATE NOT NULL CHECK (fecha_vencimiento >= fecha),
    estatus CHAR(1) DEFAULT 'A' CHECK (estatus IN ('A','C','X')),
    subtotal NUMERIC(12,2) NOT NULL CHECK (subtotal >= 0),
    iva NUMERIC(12,2) NOT NULL CHECK (iva >= 0),
    total NUMERIC(12,2) NOT NULL CHECK (total >= 0),
    saldo NUMERIC(12,2) NOT NULL CHECK (saldo >= 0),
    creado_por VARCHAR(50),
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modificado_por VARCHAR(50),
    CHECK (total = subtotal + iva),
    CHECK (saldo <= total)
);
