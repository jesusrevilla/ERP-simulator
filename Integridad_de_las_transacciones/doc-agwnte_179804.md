# Documentación: Agente de Integridad Transaccional

## 1. Descripción General
La clase `AgenteIntegridadTransaccional` se encarga de ejecutar de forma segura las operaciones de **confirmación de compras** y **cancelación de ventas** dentro del esquema comercial SQLite (`commercial_*`) del *ERP Simulator*.

Su función es asegurar que cada operación cumpla con las reglas de integridad ACID (todo o nada): si algún paso falla, se ejecuta un `ROLLBACK` automático para no dejar el inventario desfasado ni registros incompletos.

## 2. Cómo complementa el trabajo del equipo
- **`GestorTransaccionalERP`:** Se enfoca en registrar ventas nuevas.
- **`AgenteIntegridadTransaccional` (este PR):** Ejecuta compras y cancelaciones de venta sobre el esquema comercial SQLite, verificando reglas antes de guardar.
- **`AgenteGuardian`:** Revisa después que no existan inconsistencias en la base de datos.

## 3. Reglas de Seguridad e IA Aplicada
- **Atomicidad (`BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK`):** Bloquea la escritura durante la operación y revierte todo ante cualquier fallo (RF-02 / RN-01).
- **Verificación de reglas antes de guardar:** Antes de confirmar la transacción, el agente comprueba que ningún producto quede con stock negativo (RN-03) y que los movimientos generados coincidan exactamente con las líneas del documento.
- **Evita duplicados (Idempotencia):** Si se intenta confirmar una compra ya confirmada o cancelar una venta ya cancelada, el agente omite la operación para no sumar stock dos veces.
- **Reintentos ante bloqueos:** Si la base de datos está ocupada por otro proceso al mismo tiempo, el agente espera un tiempo creciente y vuelve a intentar automáticamente (RF-06).
- **Auditoría:** Registra cada acción en la tabla `commercial_audit` (RF-07 / RN-11).

## 4. Métodos Principales

### `AgenteIntegridadTransaccional(base_datos, max_reintentos=3)`
Recibe la ruta al archivo SQLite (o una conexión abierta) y el número máximo de reintentos en caso de que la base esté ocupada.

### `confirmar_compra(purchase_id)`
1. Verifica que la compra exista y esté en estado `'Borrador'`.
2. Suma las cantidades al `stock` en `commercial_products`.
3. Crea los registros `'RECEPCION'` en `commercial_movements`.
4. Cambia el estado de la compra a `'Confirmada'` y guarda `'CONFIRMAR_COMPRA'` en `commercial_audit`.
5. Valida que los números cuadren y aplica `COMMIT`.

### `cancelar_venta(sale_id)`
1. Verifica que la venta esté en estado `'Confirmada'` y tenga su movimiento de salida previo.
2. Devuelve las unidades al `stock` de cada producto.
3. Registra el movimiento inverso `'CANCELACION'` en `commercial_movements`.
4. Cambia el estado de la venta a `'Cancelada'` y guarda `'CANCELAR_VENTA'` en `commercial_audit`.
5. Comprueba que la suma entre la salida original y la devolución sea `0` antes de hacer `COMMIT`.
