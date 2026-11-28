# Módulo AR & AP — 3-Way Match y Control de Concurrencia

Este módulo implementa la capa de datos y lógica transaccional para **Cuentas por Pagar (AP)** y **Cuentas por Cobrar (AR)** dentro del simulador de ERP inteligente, con validación de **3-Way Match**, bloqueo pesimista (`FOR UPDATE`), control de estados (`A`, `P`, `C`) y trazabilidad documental en grafo.

## Estructura de archivos

* `01_schema_3way_match.sql`: Definición del tipo compuesto `resultado_operacion`, 11 tablas de AP/AR, restricciones `CHECK`, llaves foráneas e índices.
* `02_funciones_3way_match.sql`: Funciones PL/pgSQL para recepciones, facturación de proveedores, pagos, facturación de clientes y cobros.
* `03_consultas_y_pruebas.sql`: Datos de prueba, consulta de recepciones parciales pendientes de facturar y pruebas del flujo de compra/pago.
* `04_validacion_grafo.cypher`: Script en Cypher para modelar y validar la cadena documental en Neo4j.
* `README.md`: Documentación del módulo, integración con agentes y evidencias de ejecución.

## Integración con agentes del ERP

Las funciones PL/pgSQL están diseñadas para ser invocadas por los agentes operativos del ERP (por ejemplo, agentes de Compras/Recepción, Cuentas por Pagar, Ventas/Cuentas por Cobrar y Auditoría):

* **Recepción de mercancía:** `registrar_recepcion(...)` bloquea la línea de orden de compra con `FOR UPDATE` y evita recibir cantidades mayores a lo ordenado.
* **Validación 3-Way Match en compras:** `registrar_factura_proveedor(...)` verifica que la recepción corresponda a la OC y proveedor, que el precio unitario coincida con la OC y que la cantidad facturada acumulada no supere lo recibido.
* **Pagos a proveedores:** `aplicar_pago_proveedor(...)` bloquea la factura con `FOR UPDATE`, valida el saldo pendiente y actualiza el estatus a `'P'` (parcial) o `'C'` (cerrada cuando el saldo llega a `0`).
* **Facturación y cobros a clientes:** `registrar_factura_cliente(...)` valida el límite de crédito acumulado sobre facturas abiertas (`estatus <> 'C'`) y `aplicar_cobro_cliente(...)` actualiza saldos y estatus `'P'`/`'C'`.

Todas las funciones devuelven el tipo `resultado_operacion` (`exito BOOLEAN`, `mensaje TEXT`, `registro_id BIGINT`) para que el agente pueda tomar decisiones y reportar resultados de forma estructurada.

## Orden de ejecución

1. Ejecutar `01_schema_3way_match.sql` en PostgreSQL.
2. Ejecutar `02_funciones_3way_match.sql` en PostgreSQL.
3. Ejecutar `03_consultas_y_pruebas.sql` para validar el flujo y los casos de rechazo/cierre.
4. Ejecutar `04_validacion_grafo.cypher` en Neo4j para comprobar la trazabilidad del grafo.
