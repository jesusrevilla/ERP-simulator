# Módulo A/P – Cuentas por Pagar y Compras

**Autor:** Diego
**Matrícula:** 183657
**Carril BPMN:** Lane: Compras y Pagos (A/P)

---

## 1. Descripción General

El módulo **A/P (Accounts Payable – Cuentas por Pagar)** forma parte del Mini ERP y es responsable de gestionar el ciclo completo de compras de la empresa: desde que se detecta una necesidad de compra, pasando por la creación de la Orden de Compra (OC), la recepción de la mercancía, el registro de la factura del proveedor, hasta el pago final y el cierre del documento.

### 1.1 Funcionalidades principales

- Crear **órdenes de compra** (`ordenes_compra` y `oc_linea`).
- Registrar la **recepción de mercancía** desde la OC, completa o parcial (`recepciones` y `recepcion_linea`).
- Registrar la **factura de proveedor** desde la recepción, aplicando el **3-way match** (`facturas_proveedor` y `factura_proveedor_linea`).
- Registrar **pagos a proveedores** y aplicarlos a una o varias facturas (`pagos` y `pago_aplicacion`).
- Registrar **notas de crédito de proveedor** por devolución o descuento (`notas_credito_proveedor`).
- Calcular automáticamente **subtotal, IVA, total y fecha de vencimiento**.
- Consultar **cuentas por pagar por vencimiento** y **estado de cuenta por proveedor**.

### 1.2 Integración con otros módulos

| Módulo | Relación |
|---|---|
| **Datos Maestros (Alexis)** | Consume `proveedores` y `condiciones_pago`. Valida que el proveedor esté activo (`estatus = 'A'`). |
| **Inventario** | La recepción de mercancía actualiza el stock (pendiente de integración). |
| **Contabilidad (Miriam)** | Cada documento genera su asiento contable automático (pendiente de integración). |
| **Seguridad / Roles** | Solo el rol `compras` puede crear OC y solo el rol `pagos` puede registrar pagos. |

---

## 2. Estructura de Base de Datos

Todas las tablas se encuentran en el archivo `AR&AP/tablas.sql` del repositorio. A continuación se describen con sus nombres reales.

### 2.1 `ordenes_compra` – Encabezado de Orden de Compra

| Campo | Tipo | Restricción | Descripción |
|---|---|---|---|
| `oc_id` | `SERIAL` | `PRIMARY KEY` | Identificador único interno |
| `folio` | `VARCHAR(20)` | `UNIQUE NOT NULL` | Folio consecutivo (ej. `OC-000001`) |
| `proveedor_id` | `INT` | `NOT NULL REFERENCES proveedores(id_proveedor) ON DELETE RESTRICT` | Proveedor asociado |
| `fecha` | `DATE` | `NOT NULL` | Fecha de emisión |
| `estatus` | `CHAR(1)` | `DEFAULT 'A' CHECK (estatus IN ('A','C','X'))` | A=Abierto, C=Cerrado, X=Cancelado |
| `subtotal` | `NUMERIC(12,2)` | `NOT NULL CHECK (subtotal >= 0)` | Suma de líneas sin IVA |
| `iva` | `NUMERIC(12,2)` | `NOT NULL CHECK (iva >= 0)` | IVA calculado (16 %) |
| `total` | `NUMERIC(12,2)` | `NOT NULL CHECK (total >= 0)` | Total con IVA |
| `creado_por` | `VARCHAR(50)` | — | Usuario que creó el registro (auditoría) |
| `fecha_creacion` | `TIMESTAMP` | `DEFAULT CURRENT_TIMESTAMP` | Marca de tiempo de creación |
| `modificado_por` | `VARCHAR(50)` | — | Último usuario que modificó |

**Restricción de consistencia:**

```sql
CHECK (total = subtotal + iva)
```

### 2.2 `oc_linea` – Líneas de Orden de Compra

| Campo | Tipo | Restricción | Descripción |
|---|---|---|---|
| `linea_id` | `SERIAL` | `PRIMARY KEY` | Identificador único |
| `oc_id` | `INT` | `NOT NULL REFERENCES ordenes_compra(oc_id) ON DELETE RESTRICT` | OC asociada |
| `articulo` | `VARCHAR(100)` | `NOT NULL` | Nombre del artículo |
| `cantidad` | `NUMERIC(10,2)` | `NOT NULL CHECK (cantidad > 0)` | Cantidad solicitada |
| `precio_unitario` | `NUMERIC(10,2)` | `NOT NULL CHECK (precio_unitario >= 0)` | Precio pactado |
| `cantidad_recibida` | `NUMERIC(10,2)` | `DEFAULT 0 CHECK (cantidad_recibida >= 0)` | Cantidad ya recibida |
| `cantidad_facturada` | `NUMERIC(10,2)` | `DEFAULT 0 CHECK (cantidad_facturada >= 0)` | Cantidad ya facturada |

**Reglas de negocio en CHECK:**

```sql
CHECK (cantidad_recibida <= cantidad)          -- No recibir más de lo pedido
CHECK (cantidad_facturada <= cantidad)         -- No facturar más de lo pedido
CHECK (cantidad_facturada <= cantidad_recibida) -- No facturar más de lo recibido
```

### 2.3 `recepciones` – Encabezado de Recepción

| Campo | Tipo | Restricción | Descripción |
|---|---|---|---|
| `recepcion_id` | `SERIAL` | `PRIMARY KEY` | Identificador único |
| `folio` | `VARCHAR(20)` | `UNIQUE NOT NULL` | Folio consecutivo (`REC-000001`) |
| `oc_id` | `INT` | `NOT NULL REFERENCES ordenes_compra(oc_id) ON DELETE RESTRICT` | OC asociada |
| `fecha` | `DATE` | `NOT NULL` | Fecha de recepción |
| `estatus` | `CHAR(1)` | `DEFAULT 'A' CHECK (estatus IN ('A','C','X'))` | Estatus |

### 2.4 `recepcion_linea` – Líneas de Recepción

| Campo | Tipo | Restricción | Descripción |
|---|---|---|---|
| `linea_id` | `SERIAL` | `PRIMARY KEY` | Identificador único |
| `recepcion_id` | `INT` | `NOT NULL REFERENCES recepciones(recepcion_id) ON DELETE RESTRICT` | Recepción asociada |
| `oc_linea_id` | `INT` | `NOT NULL REFERENCES oc_linea(linea_id) ON DELETE RESTRICT` | Línea de OC asociada |
| `articulo` | `VARCHAR(100)` | `NOT NULL` | Artículo recibido |
| `cantidad_recibida` | `NUMERIC(10,2)` | `NOT NULL CHECK (cantidad_recibida > 0)` | Cantidad recibida |

### 2.5 `facturas_proveedor` – Encabezado de Factura de Proveedor

| Campo | Tipo | Restricción | Descripción |
|---|---|---|---|
| `factura_id` | `SERIAL` | `PRIMARY KEY` | Identificador único |
| `folio` | `VARCHAR(20)` | `UNIQUE NOT NULL` | Folio consecutivo (`FP-000001`) |
| `proveedor_id` | `INT` | `NOT NULL REFERENCES proveedores(id_proveedor) ON DELETE RESTRICT` | Proveedor |
| `recepcion_id` | `INT` | `REFERENCES recepciones(recepcion_id) ON DELETE RESTRICT` | Recepción base |
| `oc_id` | `INT` | `REFERENCES ordenes_compra(oc_id) ON DELETE RESTRICT` | OC base |
| `fecha` | `DATE` | `NOT NULL` | Fecha de la factura |
| `fecha_vencimiento` | `DATE` | `NOT NULL CHECK (fecha_vencimiento >= fecha)` | Fecha de vencimiento |
| `estatus` | `CHAR(1)` | `DEFAULT 'A' CHECK (estatus IN ('A','C','X'))` | Estatus |
| `subtotal` | `NUMERIC(12,2)` | `NOT NULL CHECK (subtotal >= 0)` | Subtotal |
| `iva` | `NUMERIC(12,2)` | `NOT NULL CHECK (iva >= 0)` | IVA acreditable |
| `total` | `NUMERIC(12,2)` | `NOT NULL CHECK (total >= 0)` | Total |
| `saldo` | `NUMERIC(12,2)` | `NOT NULL CHECK (saldo >= 0)` | Saldo pendiente |

**Restricciones de consistencia:**

```sql
CHECK (total = subtotal + iva)
CHECK (saldo <= total)
```

### 2.6 `factura_proveedor_linea` – Líneas de Factura de Proveedor

| Campo | Tipo | Restricción | Descripción |
|---|---|---|---|
| `linea_id` | `SERIAL` | `PRIMARY KEY` | Identificador único |
| `factura_id` | `INT` | `NOT NULL REFERENCES facturas_proveedor(factura_id) ON DELETE RESTRICT` | Factura asociada |
| `oc_linea_id` | `INT` | `REFERENCES oc_linea(linea_id) ON DELETE RESTRICT` | Línea de OC asociada |
| `articulo` | `VARCHAR(100)` | `NOT NULL` | Artículo |
| `cantidad` | `NUMERIC(10,2)` | `NOT NULL CHECK (cantidad > 0)` | Cantidad facturada |
| `precio_unitario` | `NUMERIC(10,2)` | `NOT NULL CHECK (precio_unitario >= 0)` | Precio unitario |

### 2.7 `pagos` – Encabezado de Pago a Proveedor

| Campo | Tipo | Restricción | Descripción |
|---|---|---|---|
| `pago_id` | `SERIAL` | `PRIMARY KEY` | Identificador único |
| `folio` | `VARCHAR(20)` | `UNIQUE NOT NULL` | Folio consecutivo (`PG-000001`) |
| `proveedor_id` | `INT` | `NOT NULL REFERENCES proveedores(id_proveedor) ON DELETE RESTRICT` | Proveedor |
| `fecha` | `DATE` | `NOT NULL` | Fecha del pago |
| `monto` | `NUMERIC(12,2)` | `NOT NULL CHECK (monto > 0)` | Monto del pago |
| `metodo_pago` | `VARCHAR(20)` | `NOT NULL` | Transferencia / Cheque / Efectivo |

### 2.8 `pago_aplicacion` – Aplicación de Pagos a Facturas

| Campo | Tipo | Restricción | Descripción |
|---|---|---|---|
| `aplicacion_id` | `SERIAL` | `PRIMARY KEY` | Identificador único |
| `pago_id` | `INT` | `NOT NULL REFERENCES pagos(pago_id) ON DELETE RESTRICT` | Pago asociado |
| `factura_id` | `INT` | `NOT NULL REFERENCES facturas_proveedor(factura_id) ON DELETE RESTRICT` | Factura asociada |
| `monto_aplicado` | `NUMERIC(12,2)` | `NOT NULL CHECK (monto_aplicado > 0)` | Monto aplicado |

**Restricción única:**

```sql
UNIQUE(pago_id, factura_id)  -- No se puede aplicar el mismo pago dos veces a la misma factura
```

### 2.9 `notas_credito_proveedor` – Notas de Crédito de Proveedor

| Campo | Tipo | Restricción | Descripción |
|---|---|---|---|
| `nota_id` | `SERIAL` | `PRIMARY KEY` | Identificador único |
| `folio` | `VARCHAR(20)` | `UNIQUE NOT NULL` | Folio consecutivo (`NC-000001`) |
| `factura_id` | `INT` | `REFERENCES facturas_proveedor(factura_id) ON DELETE RESTRICT` | Factura asociada |
| `proveedor_id` | `INT` | `NOT NULL REFERENCES proveedores(id_proveedor) ON DELETE RESTRICT` | Proveedor |
| `fecha` | `DATE` | `NOT NULL` | Fecha |
| `motivo` | `VARCHAR(200)` | `NOT NULL` | Motivo de la nota |
| `subtotal`, `iva`, `total` | `NUMERIC(12,2)` | `CHECK (total = subtotal + iva)` | Importes |

### 2.10 Índices de rendimiento

```sql
CREATE INDEX idx_oc_proveedor        ON ordenes_compra(proveedor_id);
CREATE INDEX idx_oc_fecha            ON ordenes_compra(fecha);
CREATE INDEX idx_oc_estatus          ON ordenes_compra(estatus);
CREATE INDEX idx_oclinea_oc          ON oc_linea(oc_id);
CREATE INDEX idx_recepcion_oc        ON recepciones(oc_id);
CREATE INDEX idx_factura_proveedor   ON facturas_proveedor(proveedor_id);
CREATE INDEX idx_factura_vencimiento ON facturas_proveedor(fecha_vencimiento);
CREATE INDEX idx_factura_estatus     ON facturas_proveedor(estatus);
CREATE INDEX idx_pago_proveedor      ON pagos(proveedor_id);
CREATE INDEX idx_pagoaplicacion_factura ON pago_aplicacion(factura_id);
```

**Justificación:** estos índices aceleran los reportes de *cuentas por pagar por vencimiento* y *estado de cuenta por proveedor*, cumpliendo el requisito no funcional de **respuesta en menos de 2 s**.

---

## 3. Reglas de Negocio Implementadas

Todas las reglas se encuentran en el archivo `AR&AP/funciones.sql`.

### 3.1 3-Way Match (conciliación de tres vías)

**Requisito (AR&AP-Req.md §2):**

> La factura de proveedor debe coincidir con la OC y la recepción en artículo, cantidad y precio.

**Implementación:** función `registrar_factura_proveedor()`.

```sql
-- 1) Precio de factura = precio de OC
IF p_precio_unitario <> v_oc_precio THEN
    v_res.exito := FALSE;
    v_res.mensaje := 'Error 3-way match: precio factura (' || p_precio_unitario ||
                     ') != OC (' || v_oc_precio || ')';
    RETURN v_res;
END IF;

-- 2) Cantidad facturada <= cantidad pendiente en OC
IF p_cantidad > v_pendiente_oc THEN
    v_res.exito := FALSE;
    v_res.mensaje := 'Error: cantidad facturada excede pendiente OC';
    RETURN v_res;
END IF;

-- 3) Cantidad facturada <= cantidad recibida
SELECT COALESCE(SUM(cantidad_recibida),0) INTO v_recibido
FROM recepcion_linea WHERE oc_linea_id = v_oc_linea_id;

IF p_cantidad > v_recibido THEN
    v_res.exito := FALSE;
    v_res.mensaje := 'Error: cantidad facturada excede recibida';
    RETURN v_res;
END IF;
```

**Ejemplo de rechazo:**

```sql
SELECT * FROM registrar_factura_proveedor(
    1, 1, 1, '2026-11-11', '30',
    'Articulo A', 10, 120.00, 'diego'
);
-- Resultado: Error 3-way match: precio factura (120.00) != OC (100.00)
```

### 3.2 No facturar más de lo pendiente en el documento base

**Requisito (AR&AP-Req.md §2):**

> No se puede facturar más de lo que queda pendiente en el documento base.

**Implementación:** los `CHECK` de `oc_linea` y la validación dentro de `registrar_factura_proveedor()`:

```sql
CHECK (cantidad_facturada <= cantidad)
CHECK (cantidad_facturada <= cantidad_recibida)
```

Cada vez que se registra una factura, se actualiza `cantidad_facturada` en `oc_linea`; si el valor excede `cantidad` o `cantidad_recibida`, la transacción se revierte.

### 3.3 Un pago no puede exceder el saldo de la factura

**Requisito (AR&AP-Req.md §2):**

> Un pago no puede aplicarse por más del saldo de la factura.

**Implementación:** función `aplicar_pago_proveedor()`.

```sql
-- Bloqueo de fila para concurrencia
SELECT saldo INTO v_saldo
FROM facturas_proveedor
WHERE factura_id = p_factura_id
FOR UPDATE;

IF p_monto > v_saldo THEN
    v_res.exito := FALSE;
    v_res.mensaje := 'Error: pago (' || p_monto || 
                     ') mayor al saldo (' || v_saldo || ')';
    RETURN v_res;
END IF;
```

### 3.4 Cálculo automático de fecha de vencimiento

**Requisito (AR&AP-Req.md §2):**

> Vencimiento = fecha del documento + días de la condición de pago.

```sql
SELECT dias INTO v_dias
FROM condiciones_pago
WHERE codigo = p_condicion_pago;

v_fecha_venc := p_fecha + (v_dias || ' days')::INTERVAL;
```

**Ejemplo:** factura del `2026-11-11` con condición `30` → vencimiento `2026-12-11`.

### 3.5 Cálculo de totales e IVA

**Requisito (AR&AP-Req.md §2):**

> IVA = subtotal × tasa. Total = subtotal + IVA.

```sql
v_subtotal := p_cantidad * p_precio_unitario;
v_iva      := v_subtotal * 0.16;
v_total    := v_subtotal + v_iva;
```

**Prueba unitaria (AR&AP-Req.md §3):**

| Función | Entrada | Resultado esperado |
|---|---|---|
| `calcularTotal` | 10 × $100 con IVA 16 % | Total $1,160 |

### 3.6 Proveedor activo

**Requisito (AR&AP-Req.md §2):**

> Un cliente o proveedor inactivo no puede usarse en documentos nuevos.

```sql
SELECT estatus INTO v_estatus_prov
FROM proveedores
WHERE id_proveedor = p_proveedor_id;

IF v_estatus_prov IS NULL OR v_estatus_prov <> 'A' THEN
    v_res.exito := FALSE;
    v_res.mensaje := 'Error: proveedor inactivo o inexistente';
    RETURN v_res;
END IF;
```

### 3.7 Folio consecutivo y único

**Requisito (AR&AP-Req.md §2):**

> El folio es consecutivo y único para cada tipo de documento.

```sql
v_folio := 'OC-'  || LPAD((SELECT COUNT(*)+1 FROM ordenes_compra)::TEXT, 6, '0');
v_folio := 'REC-' || LPAD((SELECT COUNT(*)+1 FROM recepciones)::TEXT, 6, '0');
v_folio := 'FP-'  || LPAD((SELECT COUNT(*)+1 FROM facturas_proveedor)::TEXT, 6, '0');
v_folio := 'PG-'  || LPAD((SELECT COUNT(*)+1 FROM pagos)::TEXT, 6, '0');
v_folio := 'NC-' || LPAD((SELECT COUNT(*)+1 FROM notas_credito_proveedor)::TEXT, 6, '0');
```

Además, cada tabla declara `folio VARCHAR(20) UNIQUE NOT NULL`.

### 3.8 Cierre automático de factura

**Requisito (AR&AP-Req.md §2):**

> Cuando el saldo llega a 0, la factura se cierra.

```sql
UPDATE facturas_proveedor
SET saldo  = saldo - p_monto,
    estatus = CASE WHEN (saldo - p_monto) = 0 THEN 'C' ELSE 'A' END
WHERE factura_id = p_factura_id;
```

---

## 4. Pruebas Funcionales

Los escenarios se ejecutan con el script `AR&AP/pruebas.sql`.

### 4.1 Ciclo de compra: OC → recepción → factura → pago

**Requisito (AR&AP-Req.md §4):**

> Factura cerrada e inventario actualizado.

```sql
-- 1. OC
SELECT * FROM crear_orden_compra(1, '2026-11-11',
    ARRAY['Articulo A'], ARRAY[10], ARRAY[100.00], 'diego');
-- → OC registrada. Folio: OC-000001

-- 2. Recepción
SELECT * FROM registrar_recepcion(1, '2026-11-11', 'Articulo A', 10, 'diego');
-- → Recepción registrada. Folio: REC-000001

-- 3. Factura (3-way match válido)
SELECT * FROM registrar_factura_proveedor(1, 1, 1, '2026-11-11', '30',
    'Articulo A', 10, 100.00, 'diego');
-- → Factura registrada (3-way match OK). Folio: FP-000001

-- 4. Pago total
SELECT * FROM aplicar_pago_proveedor(1, 1, 1160.00, '2026-11-11',
    'Transferencia', 'diego');
-- → Pago aplicado. Folio: PG-000001

-- 5. Verificación
SELECT folio, estatus, saldo FROM facturas_proveedor WHERE folio = 'FP-000001';
-- → FP-000001 | C | 0.00
```

### 4.2 Factura de proveedor con precio distinto a la OC

**Requisito (AR&AP-Req.md §4):**

> No deja guardarla.

```sql
SELECT * FROM registrar_factura_proveedor(1, 1, 1, '2026-11-11', '30',
    'Articulo B', 10, 120.00, 'diego');
-- → Error 3-way match: precio factura (120.00) != OC (100.00)
```

### 4.3 Pago mayor al saldo

**Requisito (AR&AP-Req.md §3 y §4):**

| Función | Entrada | Resultado esperado |
|---|---|---|
| `aplicarPago` | Saldo $660, pago $700 | Error: pago mayor al saldo |

```sql
SELECT * FROM aplicar_pago_proveedor(1, 1, 700.00, '2026-11-11',
    'Transferencia', 'diego');
-- → Error: pago (700.00) mayor al saldo (660.00)
```

### 4.4 Pago parcial

**Requisito (AR&AP-Req.md §4):**

> La factura sigue abierta con el saldo restante.

```sql
-- Factura de 1,160.00, pago de 500.00
SELECT * FROM aplicar_pago_proveedor(1, 1, 500.00, '2026-11-11',
    'Transferencia', 'diego');

SELECT saldo, estatus FROM facturas_proveedor WHERE factura_id = 1;
-- → saldo 660.00, estatus 'A'
```

### 4.5 Nota de crédito reduce el saldo

```sql
SELECT * FROM registrar_nota_credito_proveedor(
    1, 1, '2026-11-11', 'Devolución de mercancía', 160.00, 'diego');
-- → Nota de crédito registrada. Folio: NC-000001

SELECT saldo FROM facturas_proveedor WHERE factura_id = 1;
-- → saldo 1,000.00
```

---

## 5. Diagrama BPMN – Lane: Compras y Pagos (A/P)

A continuación se describe el flujo del carril central del *Pool: Mini ERP – A/R y A/P*, tal como está definido en `AR&AP-Req.md`.

```
P0(("Necesidad de compra"))
  ↓
P1("Crear orden de compra")
  ↓
P2("Registrar recepción y subir inventario")
  ↓
P3("Registrar factura de proveedor")
  ↓
PG1{"3-way match: ¿OC, recepción y factura coinciden?"}
  ├── No → PE1((("Factura rechazada")))
  └── Sí → P4("Registrar pago y asiento")
              ↓
        PG2{"¿Saldo = 0?"}
              ├── No → P4  (regresa para más pagos)
              └── Sí → P5("Cerrar factura")
                          ↓
                   PE2((("Factura pagada")))
```

### 5.1 Descripción de nodos

| Nodo | Tipo | Descripción |
|---|---|---|
| **P0** | Inicio | Evento inicial: se detecta una necesidad de compra |
| **P1** | Tarea | Se crea la OC con artículos, cantidades y precios pactados |
| **P2** | Tarea | Almacén registra la recepción; se actualiza `cantidad_recibida` en `oc_linea` |
| **P3** | Tarea | Contabilidad captura la factura fiscal del proveedor |
| **PG1** | Compuerta | Valida el **3-way match** (artículo, cantidad y precio) |
| **PE1** | Fin | Factura rechazada por no cumplir 3-way match |
| **P4** | Tarea | Tesorería registra el pago y se genera el asiento contable |
| **PG2** | Compuerta | Verifica si el saldo de la factura llegó a 0 |
| **P5** | Tarea | Se cambia el estatus a `C` (Cerrado) |
| **PE2** | Fin | Factura pagada completamente |

### 5.2 Reglas de negocio asociadas a cada nodo

- **P1:** el proveedor debe estar activo (`estatus = 'A'`); se genera folio consecutivo único; se calculan totales automáticamente.
- **P2:** no se puede recibir más de lo pendiente en la OC (`cantidad_recibida <= cantidad`).
- **P3 / PG1:** se aplica el 3-way match; no se puede facturar más de lo recibido ni más de lo pendiente.
- **P4:** el pago no puede exceder el saldo; se usa bloqueo de fila (`FOR UPDATE`) para concurrencia.
- **PG2 / P5:** cuando `saldo = 0`, la factura pasa a estatus `C` y ya no puede modificarse.

---

## 6. Integridad Transaccional

Esta sección documenta los mecanismos de integridad implementados en el módulo A/P, conforme a la sección 5 de `AR&AP-Req.md`.

### 6.1 Integridad de entidad

- Cada tabla tiene su **llave primaria** (`SERIAL PRIMARY KEY`).
- El **folio es único** por tipo de documento: `folio VARCHAR(20) UNIQUE NOT NULL`.
- Ejemplo: no pueden existir dos órdenes de compra con folio `OC-000001`.

### 6.2 Integridad referencial

- Todas las llaves foráneas usan `ON DELETE RESTRICT`: no se puede borrar un proveedor que tenga órdenes de compra, facturas o pagos asociados.
- Ejemplo:

```sql
proveedor_id INT NOT NULL
    REFERENCES proveedores(id_proveedor)
    ON DELETE RESTRICT
```

- Si un proveedor deja de usarse, se **inactiva** (`estatus = 'I'`) en lugar de eliminarse, cumpliendo el requisito: *un cliente o proveedor inactivo no se elimina si ya tiene documentos.*

### 6.3 Integridad de dominio

- `NOT NULL` en campos obligatorios (`folio`, `fecha`, `total`, etc.).
- `CHECK` para validar dominios:
  - `CHECK (cantidad > 0)`
  - `CHECK (precio_unitario >= 0)`
  - `CHECK (estatus IN ('A','C','X'))`
  - `CHECK (fecha_vencimiento >= fecha)`
  - `CHECK (total = subtotal + iva)`
  - `CHECK (saldo <= total)`
- El dinero se guarda en `NUMERIC(12,2)` (equivalente a `DECIMAL`), nunca en `FLOAT`, evitando errores de redondeo.

### 6.4 Consistencia

- **Total = suma de líneas:** garantizado por `CHECK (total = subtotal + iva)` y por el cálculo dentro de las funciones.
- **Saldo = total − pagos aplicados − notas de crédito:** se mantiene actualizado en `facturas_proveedor.saldo` cada vez que se ejecuta `aplicar_pago_proveedor()` o `registrar_nota_credito_proveedor()`.
- **Las aplicaciones suman el monto del pago:** garantizado por la lógica de `aplicar_pago_proveedor()` y la restricción `UNIQUE(pago_id, factura_id)`.

### 6.5 Transacciones ACID

**Requisito (AR&AP-Req.md §5):**

> La factura, el movimiento de inventario y el asiento se guardan juntos. Si uno falla, se hace rollback de todo.

**Implementación:** cada función (`registrar_factura_proveedor`, `aplicar_pago_proveedor`, etc.) ejecuta múltiples `INSERT`/`UPDATE` dentro de una misma transacción implícita de PostgreSQL. Si alguna instrucción falla (por ejemplo, una violación de `CHECK`), PostgreSQL revierte automáticamente toda la operación.

**Ejemplo en `registrar_factura_proveedor()`:**

```sql
INSERT INTO facturas_proveedor (...);
INSERT INTO factura_proveedor_linea (...);
UPDATE oc_linea SET cantidad_facturada = cantidad_facturada + p_cantidad ...;
```

Si el `UPDATE` falla, los dos `INSERT` se revierten, manteniendo la consistencia.

### 6.6 Concurrencia

**Requisito (AR&AP-Req.md §5):**

> Si dos usuarios cobran la misma factura al mismo tiempo, se usa bloqueo de fila (`SELECT … FOR UPDATE`) para que no se aplique dos veces.

**Implementación:** en `aplicar_pago_proveedor()`:

```sql
SELECT saldo INTO v_saldo
FROM facturas_proveedor
WHERE factura_id = p_factura_id
FOR UPDATE;   -- Bloquea la fila hasta que termine la transacción
```

1. Usuario A inicia el pago de la factura `FP-000001`.
2. Usuario B intenta pagar la misma factura al mismo tiempo.
3. La consulta de Usuario B queda **bloqueada** hasta que Usuario A haga `COMMIT` o `ROLLBACK`.
4. Esto evita que el saldo se descuente dos veces o quede negativo.

### 6.7 Auditoría

**Requisito (AR&AP-Req.md §5):**

> Cada registro guarda `CreadoPor`, `FechaCreacion` y `ModificadoPor`, y hay una tabla de bitácora. Los documentos nunca se borran.

**Implementación:**

- Cada tabla incluye los campos `creado_por`, `fecha_creacion` y `modificado_por`.
- Los documentos no se eliminan: para cancelar se usa un **documento inverso** (nota de crédito) que queda registrado en `notas_credito_proveedor` con su motivo.
- Pendiente de implementar: tabla de bitácora general (`bitacora`) que registre todos los cambios (propuesto como mejora).

### 6.8 Respaldos

**Requisito (AR&AP-Req.md §5):**

> Se hacen respaldos periódicos y se prueba que la restauración funcione.

**Propuesto como mejora:** configurar `pg_dump` automático diario y pruebas mensuales de restauración.

---

## 7. Estado de Implementación

### Ya implementado

| # | Elemento | Archivo |
|---|---|---|
| 1 | Tablas `ordenes_compra`, `oc_linea`, `recepciones`, `recepcion_linea`, `facturas_proveedor`, `factura_proveedor_linea`, `pagos`, `pago_aplicacion`, `notas_credito_proveedor` | `AR&AP/tablas.sql` |
| 2 | Índices de rendimiento | `AR&AP/tablas.sql` |
| 3 | Función `crear_orden_compra()` | `AR&AP/funciones.sql` |
| 4 | Función `registrar_recepcion()` | `AR&AP/funciones.sql` |
| 5 | Función `registrar_factura_proveedor()` con **3-way match** | `AR&AP/funciones.sql` |
| 6 | Función `aplicar_pago_proveedor()` con **bloqueo de fila (FOR UPDATE)** | `AR&AP/funciones.sql` |
| 7 | Función `registrar_nota_credito_proveedor()` | `AR&AP/funciones.sql` |
| 8 | Pruebas funcionales (5 escenarios) | `AR&AP/pruebas.sql` |
| 9 | Restricciones `CHECK`, `UNIQUE`, `NOT NULL`, `ON DELETE RESTRICT` | `AR&AP/tablas.sql` |

### Propuesto como mejora

| # | Mejora | Justificación |
|---|---|---|
| 1 | Integración automática con módulo de **Inventario** para actualizar stock en `P2` | Completar el flujo OC → recepción → inventario |
| 2 | Generación automática de **asientos contables** (cargo a Inventario + IVA acreditable; abono a Proveedores) | Cumplir requisito de contabilidad automática |
| 3 | Tabla de **bitácora** (`bitacora`) para auditoría detallada | Trazabilidad completa de cambios |
| 4 | Reporte de **antigüedad de saldos** y **cuentas por pagar por vencimiento** | Requerimiento funcional de consulta |
| 5 | Validación de **RFC de proveedor contra el SAT** | Validación fiscal |
| 6 | Soporte para **múltiples monedas** y tipo de cambio | Internacionalización |
| 7 | **Notificaciones automáticas** de facturas por vencer | Mejora operativa |
| 8 | Interfaz **web** para captura de documentos | Usabilidad |
| 9 | Configuración de **respaldos automáticos** con `pg_dump` | Cumplir requisito de respaldos |

---

## 8. Referencias

- `AR&AP-Req.md` – Requerimientos funcionales, reglas de negocio, pruebas e integridad de datos del Mini ERP.
- `AR&AP.md` – Descripción técnica del módulo A/R y A/P.
- `AR&AP/tablas.sql` – Esquema de base de datos PostgreSQL del módulo A/P.
- `AR&AP/funciones.sql` – Funciones y reglas de negocio del módulo A/P.
- `AR&AP/pruebas.sql` – Pruebas funcionales del módulo A/P.

---

*Fin del documento.*