# Documentación: Gestor de Compensación Contable y Reversión ERP

## 1. Descripción General

La clase `GestorCompensacionERP` implementa un controlador transaccional diseñado para ejecutar operaciones de **reversión y compensación (Patrón Saga)** directamente en el motor principal de **PostgreSQL**.

Este componente cierra el ciclo de vida de las operaciones del `GestorTransaccionalERP` original. Mientras que el gestor base procesa altas de ventas e ingresos, este nuevo gestor procesa las **cancelaciones y devoluciones**, garantizando que el inventario se reintegre, la cuenta por cobrar se cancele y, lo más importante, se genere la **contra-póliza contable** para mantener la integridad financiera del ERP.

## 2. Requerimientos y Reglas de Negocio Cubiertas

* **RF-02 / RN-01 (Atomicidad Todo o Nada):** Uso de transacciones manuales (`BEGIN`, `COMMIT`, `ROLLBACK`) para garantizar que la devolución de inventario y la cancelación contable ocurran como una unidad indivisible.
* **RF-05 / RN-02 (Partida Doble y Reversión):** Cumplimiento estricto de las reglas contables mediante la generación de un asiento de reverso (cargo a Ventas/IVA, abono a Clientes), sin eliminar registros históricos.
* **RN-12 (Integridad Financiera en Memoria):** Validación estricta `total == subtotal + iva` antes de interactuar con la base de datos, protegiendo al sistema de peticiones corruptas o descuadradas desde el frontend.
* **RF-06 (Control de Concurrencia Avanzado):** Implementación de un algoritmo **Anti-Deadlock** (prevención de abrazos mortales) mediante el ordenamiento léxico de los identificadores de productos antes de solicitar bloqueos pesimistas múltiples.
* **RF-07 / RN-11 (Trazabilidad en Bitácora):** Registro inmutable del evento `CANCELAR_VENTA` asociado al usuario y documento original.

## 3. Arquitectura y Métodos Principales

### Clase: `GestorCompensacionERP`

**Constructor:** `__init__(self, db_connection)`

* Inicializa el gestor recibiendo la conexión activa a PostgreSQL (`psycopg2`), manteniendo la compatibilidad con la arquitectura del gestor original.

**Método:** `ejecutar_cancelacion_venta(folio_venta, id_cliente, carrito_devuelto, total, subtotal, iva, usuario)`

* **Propósito:** Orquesta la cancelación completa de un ticket o factura.
* **Parámetros Clave:** A diferencia de las implementaciones anteriores de un solo artículo, este método recibe un `carrito_devuelto` (lista de diccionarios con múltiples productos y cantidades), lo que lo hace escalable para operaciones de retail reales.
* **Retorno:** Diccionario con estado (`"exito"` / `"error"`) y mensaje detallado de la ejecución o del motivo del `ROLLBACK`.

## 4. Flujo de Ejecución (Paso a Paso)

1. **Validación Pre-Commit (Guardrail):** Se verifica matemáticamente que los montos financieros cuadren al centavo. Si el `total` no coincide con el `subtotal + iva`, se aborta inmediatamente.
2. **Apertura (`BEGIN`):** Se inicia la transacción en la base de datos.
3. **Algoritmo Anti-Deadlock:** Se ordena la lista de `carrito_devuelto` por `id_producto` de menor a mayor. Esto garantiza que si dos o más hilos intentan cancelar ventas concurrentes con productos cruzados, siempre soliciten los bloqueos en el mismo orden, eliminando matemáticamente el riesgo de *deadlocks* en PostgreSQL.
4. **Bloqueo Pesimista y Reintegración:** Se itera sobre los productos ordenados. Se bloquea cada fila específica (`SELECT ... FOR UPDATE`) y se ejecuta el `UPDATE` sumando la cantidad devuelta al inventario.
5. **Cancelación de Pasivo:** Se actualiza la `cuenta_por_cobrar` original cambiando su estatus a `'CANCELADO'`.
6. **Asiento Contable de Reverso:** Se inserta el detalle en `poliza_detalle` invirtiendo la naturaleza de las cuentas originales (los abonos originales ahora son cargos y viceversa) usando el prefijo `REV-[folio]`.
7. **Auditoría:** Inserción del movimiento en la tabla `bitacora`.
8. **Cierre (`COMMIT` / `ROLLBACK`):** Confirmación a disco o reversión total en caso de cualquier excepción (ej. violación de constraints, producto inexistente o caída de red).

## 5. Aportación al Ecosistema del Proyecto

Este PR se diferencia y complementa el trabajo del equipo al abordar la capa **Contable y de PostgreSQL**:

* Mientras que el *Agente Guardián* y el *Agente de Integridad* operan analizando y compensando datos en el prototipo de **SQLite** enfocándose en los movimientos comerciales, este gestor resuelve la **compensación contable real en PostgreSQL**.
* Introduce la capacidad de procesar **múltiples partidas simultáneas** (carritos de compra/devolución) de forma segura a nivel de concurrencia, resolviendo una limitación arquitectónica del módulo de ventas original.
