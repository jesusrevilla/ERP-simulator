# Integridad de los datos, contabilidad y pruebas unitarias

**Integrante:** Miriam (183800)

---

## 1. Integridad de los datos

**Integridad de entidad**
Implementado: cada registro es único porque cada tabla tiene una llave primaria (`PRIMARY KEY`). Mi tabla `asientos_contables` además usa `UNIQUE (tipo_doc, folio)` para que no se repita el mismo folio en el mismo tipo de documento.

**Integridad referencial**
Implementado: las tablas se conectan con llaves foráneas y `ON DELETE RESTRICT`, así no se puede borrar algo que ya se está usando. En `detalle_asiento`, `asiento_id` apunta a `asientos_contables` y `cuenta_id` apunta a `cuentas_contables`.

**Integridad de dominio**
Implementado: se controlan los valores permitidos con `NOT NULL` y `CHECK`. Por ejemplo, el estatus solo puede ser A, C o X, el tipo de cuenta solo puede ser A, P, C, I o G, y una línea tiene cargo o abono, pero no los dos. El dinero se guarda en `NUMERIC(12,2)` y no en `FLOAT`.

**Consistencia**
Implementado: las facturas ya revisan que los números cuadren con `CHECK (total = subtotal + iva)` y `CHECK (saldo <= total)`.

**Auditoría**
Implementado: la tabla `bitacora` guarda quién cambió qué y cuándo.
Propuesta: triggers que llenen la bitácora solos.

**Transacciones y concurrencia**
Propuesta: una transacción guarda todo junto o no guarda nada (`ROLLBACK`). Para que dos personas no usen la misma factura al mismo tiempo se usaría `SELECT ... FOR UPDATE`, que bloquea la fila.

**Respaldos**
Propuesta: hacer copias de seguridad con `pg_dump` y probar que se pueden restaurar.

---

## 2. Contabilidad

Cada documento genera un asiento. La regla es que la suma de los cargos sea igual a la suma de los abonos.

Implementado: mis tablas `cuentas_contables`, `asientos_contables`, `detalle_asiento` y `bitacora`.

| Documento | Cargo | Abono |
|---|---|---|
| Factura de cliente | Clientes | Ventas e IVA trasladado |
| Cobro | Bancos | Clientes |
| Factura de proveedor | Inventario e IVA acreditable | Proveedores |
| Pago | Proveedores | Bancos |

Un documento no se borra, se cancela y se crea un asiento al revés.

Propuesta: triggers que creen los asientos y las cancelaciones automáticamente.

---

## 3. Pruebas unitarias

| Función | Entrada | Resultado esperado |
|---|---|---|
| `calcularTotal` | 10 × $100 con IVA 16 % | Total $1,160 |
| `calcularVencimiento` | 03/11/2026 a 30 días | 03/12/2026 |
| `aplicarPago` | Saldo $1,160, pago $500 | Saldo $660 |
| `aplicarPago` | Saldo $660, pago $700 | Error: pago mayor al saldo |
| `validarLimiteCredito` | Límite $5,000, saldo $4,500, factura $1,160 | Rechaza |
| `validarCantidad` | Cantidad 0 | Rechaza |

---

## 4. Resumen

| Tema | Estado |
|---|---|
| Llaves, `CHECK`, `NOT NULL` | Implementado |
| Mis 4 tablas | Implementado |
| Triggers de asientos y bitácora | Propuesta |
| Transacciones y `FOR UPDATE` | Propuesta |
| Respaldos | Propuesta |