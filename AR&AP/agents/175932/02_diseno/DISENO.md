# Diseño - APReceiptCapacityAgent

## Identificación y alcance
Matrícula 175932; módulo A/R y A/P, especialización cuentas por pagar.
Sistema experto determinista: observa documentos y estado, evalúa reglas,
reserva/libera capacidad y genera un reporte. No utiliza un LLM.

Problema: dos facturas de 6 piezas pueden pasar una comparación individual con
una recepción de 10, pero juntas exceden la recepción. La solución decide sobre
el acumulado y lo protege mediante bloqueo transaccional.

Referencias consultadas en el repositorio del profesor:
AR&AP/Requerimientos_y_Diagramas.md (no facturar más de lo pendiente y RN-04),
AR&AP/tablas.sql y AR&AP/funciones.sql. No se reemplazan esos esquemas.
El prototipo usa un adaptador aislado ap_capacity_175932 para evitar afectar
trabajos de compañeros. La conexión a los documentos productivos reales queda pendiente.

## Regla central
consumido = suma(facturas aceptadas) - suma(créditos de cantidad aceptados)
disponible = recibido - consumido
Invariante: 0 <= consumido <= recibido.

Una factura consume capacidad si cantidad <= disponible.
Un crédito CREDIT_QUANTITY libera capacidad si cantidad <= saldo de cantidad
de la factura original y pertenece a la misma recepción.
Un descuento monetario no libera piezas; no se acepta como CREDIT_QUANTITY.

## Contrato
Cada evento incluye event_id, receipt_id, kind (INVOICE o CREDIT_QUANTITY),
document_id y quantity (texto decimal positivo con hasta 3 decimales).
CREDIT_QUANTITY agrega invoice_id, que identifica una factura aceptada.
No se admiten campos desconocidos. Las cantidades usan NUMERIC(18,3)/Decimal,
no FLOAT. Un document_id es único por tipo en el esquema de esta contribución.

La recepción contiene receipt_id, supplier_id, item_id, received y active.
Se registra previamente como recepción ya validada por el ERP.
El prototipo no valida precio, IVA, moneda ni coincidencia con la OC; esas
validaciones corresponden a los módulos existentes antes de invocar al agente.

## Decisiones
ACCEPTED: reserva/libera capacidad.
REJECTED: RECEIPT_NOT_FOUND, INACTIVE_RECEIPT, CAPACITY_EXCEEDED,
INVOICE_NOT_FOUND, CREDIT_EXCEEDED, DOCUMENT_EXISTS o INVALID_EVENT.
EVENT_KEY_CONFLICT indica reutilizar event_id con otro contenido.
Reintentar exactamente el mismo evento devuelve su decisión anterior
con replay=true y no modifica cantidades ni crea otro reporte.
Un evento rechazado debe reenviarse con una clave nueva si cambia el contexto.

## Transacción y concurrencia
1. Bloqueo advisory por event_id: serializa reintentos de la misma clave.
2. Comprobar idempotencia y contrato.
3. Bloquear la recepción con SELECT FOR UPDATE.
4. Evaluar y registrar documento, saldo, decisión y outbox en la misma transacción.
5. COMMIT; ante excepción se revierte todo.
6. Un exportador lee outbox con FOR UPDATE SKIP LOCKED y proyecta por event_id
en Neo4j y MongoDB. Solo confirma el envío cuando ambas escrituras terminaron.

No hay transacción distribuida entre tres bases: consistencia eventual.
Si falla una proyección, el outbox conserva el pendiente. MERGE/upsert permiten
reintentar sin duplicar. Un conflicto de clave o un evento sin identificador
válido se devuelve al solicitante sin reemplazar la evidencia original.

## Grafo y bitácora
Receipt175932 <- REPORTS_ON - Decision175932 - ABOUT -> Document175932.
Receipt175932 - RECEIVED_FROM -> Supplier175932.
Un crédito se enlaza a la factura original con CREDITS.
El grafo almacena instantáneas antes/después por evento; no sobrescribe un saldo
actual con eventos atrasados. PostgreSQL es la fuente de verdad.

MongoDB conserva un documento inmutable lógicamente por event_id mediante
$setOnInsert. No se presenta como almacenamiento inviolable: un administrador
con permisos todavía puede modificarlo.

## Límites y pendientes
No realiza pagos ni asientos, no modifica inventario ni autoriza el merge.
active se aplica a la recepción del adaptador; el proveedor debe haber sido
validado previamente por el ERP. Créditos de devoluciones físicas requieren
otra política porque pueden reducir recibido en vez de liberar facturación.
Adaptación a esquemas compartidos, roles DB de mínimos privilegios, monitoreo,
pruebas y validación de despliegue quedan para la siguiente fase.
