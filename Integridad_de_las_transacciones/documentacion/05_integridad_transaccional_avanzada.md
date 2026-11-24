# 5. Integridad transaccional avanzada y control de consistencia

## 1. Propiedades ACID
Para proteger la integridad de las operaciones en el ERP-Simulator, se evalúan las cuatro propiedades ACID, las cuales garantizan que los datos sean confiables[cite: 10]:
* **Atomicidad:** Una transacción se completa en su totalidad o se cancelan todos sus cambios (mediante un proceso de Rollback)[cite: 9, 10].
* **Consistencia:** La operación respeta reglas y restricciones, validando integridad referencial, existencias y costos antes de generar asientos contables[cite: 9, 10].
* **Aislamiento:** Las transacciones simultáneas no interfieren entre sí, previniendo que dos entregas consuman las mismas existencias[cite: 10].
* **Durabilidad:** Los cambios confirmados (como la generación de logs inmutables y la actualización de la base de datos) permanecen almacenados[cite: 9, 10].
*(Nota: Actualmente, estas propiedades fungen como propuestas de evaluación y diseño conceptual, ya que no se ha verificado su implementación completa a nivel de código en todos los módulos[cite: 10]).*

## 2. Flujo de pagos y sus 12 eventos
El procesamiento de pagos en el ERP se define mediante una secuencia de integración estructurada en 12 eventos bajo el estándar ISA-95[cite: 11]:
1. **`InvoiceApprovedForPaymentEvent` (EVT-ERP-PAY-001):** Se aprueba la factura (ej. `INV-994812`) por los directores responsables[cite: 11].
2. **`PaymentBatchCreatedEvent` (EVT-ERP-PAY-002):** Se agrupan facturas en un lote de pago (`PBATCH-20261110-88`) en la Tesorería[cite: 11].
3. **`AccountBalanceReserveRequestedEvent` (EVT-ERP-PAY-003):** Se solicita la reserva de fondos en la cuenta de efectivo[cite: 11].
4. **`AccountBalanceReservedEvent` (EVT-ERP-PAY-004):** Se confirma la reserva exitosa de los fondos[cite: 11].
5. **`PaymentInstructionGeneratedEvent` (EVT-ERP-PAY-005):** Se genera la instrucción hacia el banco destino (ej. vía SPEI)[cite: 11].
6. **`BankingGatewayPayloadSignedEvent` (EVT-ERP-PAY-006):** Firma criptográfica (SHA-256) del payload enviada al banco[cite: 11].
7. **`BankTransactionDispatchedEvent` (EVT-ERP-PAY-007):** Envío de la transacción al endpoint bancario externo[cite: 11].
8. **`BankTransactionSettledEvent` (EVT-ERP-PAY-008):** El banco confirma la liquidación de la transferencia mediante un código de autorización[cite: 11].
9. **`GeneralLedgerPostedEvent` (EVT-ERP-PAY-009):** Se registran los movimientos de partida doble (cargo a proveedores, abono a bancos) en el Libro Mayor[cite: 11].
10. **`VendorBalanceUpdatedEvent` (EVT-ERP-PAY-010):** El saldo del proveedor queda en 0.00 y la factura cambia a estado `PAID`[cite: 11].
11. **`MaterialVendorStatusUnblockedEvent` (EVT-ERP-PAY-011):** Se libera el estado crediticio del proveedor para nuevas órdenes de trabajo en el módulo MES[cite: 11].
12. **`PaymentSagaCompletedEvent` (EVT-ERP-PAY-012):** El orquestador finaliza el ciclo confirmando el éxito del flujo[cite: 11].

## 3. Patrón Saga y sus fases
El modelo propuesto implementa el `Saga_Pattern_Two_Phase_Commit_Outbox` orquestado por el componente `ERP_Saga_Orchestrator`[cite: 11]. Este patrón divide la transacción en múltiples pasos locales, cada uno con una fase específica[cite: 11]:
* **Fases iniciales e intermedias:** `PREPARATION` (aprobación), `BATCHING` (agrupación), `LOCKING` y `LOCKED` (reserva de fondos)[cite: 11].
* **Fases de ejecución:** `INSTRUCTION_PREPARATION`, `CRYPTOGRAPHIC_SIGNING`, `EXTERNAL_DISPATCH`, y `SETTLEMENT_CONFIRMED` para lidiar con el banco[cite: 11].
* **Fases de cierre:** `DOUBLE_ENTRY_POSTING`, `LEDGER_UPDATE`, `ISA95_MES_PROPAGATION`, culminando en `COMPLETED`[cite: 11].

## 4. Patrón Outbox
Para evitar la pérdida de mensajes entre los servicios internos, la arquitectura exige que la generación de eventos financieros utilice el patrón Outbox (`outbox_pattern_applied: true`)[cite: 11]. Esto se evidencia en el paso 5, donde se crea un identificador de mensaje de salida (`outbox_message_id: OUTBOX-PAY-88192`) que asegura que el evento se publique en el bus de mensajes solo si la transacción en la base de datos local fue exitosa[cite: 11].

## 5. Uso de claves de idempotencia
Para evitar que un mismo pago o evento se procese más de una vez (especialmente en reintentos de red), se exige el uso de claves únicas de idempotencia (`idempotency_enforced: true`) en todos los pasos[cite: 11].
* **Ejemplos implementados conceptualmente:** `IDEMP-INV-994812-20261110-01` al aprobar la factura, o `IDEMP-DISP-INS-2026-0001882` al despachar el pago al banco[cite: 11].

## 6. Niveles de aislamiento
El flujo combina dos niveles de aislamiento de base de datos dependiendo de la criticidad de la operación, lo cual es una mejora propuesta para evitar inconsistencias[cite: 10, 11]:
* **`SERIALIZABLE`:** Nivel más estricto, utilizado en operaciones críticas del Libro Mayor (General Ledger) para evitar lecturas fantasma. Se aplica en los eventos 3 (reserva de balance) y 9 (asiento de partida doble)[cite: 11].
* **`READ_COMMITTED`:** Nivel estándar utilizado en la mayoría de los eventos (preparación, firma, liquidación y actualizaciones de estado del proveedor) para balancear la integridad y el rendimiento[cite: 11].

## 7. Mecanismos de concurrencia y riesgos
Si varias operaciones intentan modificar los mismos datos simultáneamente (ej. dos entregas consumiendo el mismo inventario), pueden registrarse sobreventas o cálculos erróneos[cite: 10]. 
* **Prevención propuesta:** El diagrama de operaciones estipula el paso "Aplicar Bloqueos Concurrencia" tras verificar la integridad referencial[cite: 9]. 
* En el flujo de pagos (JSON), esto se implementa mediante un bloqueo pesimista explícito (`lock_type: PESSIMISTIC_OUTBOUND_PAYMENT`) de 300 segundos sobre la cuenta bancaria, para garantizar que los fondos no sean utilizados por otro lote mientras se procesa la transferencia[cite: 11].

## 8. Acciones compensatorias
En el patrón Saga, si un paso falla, no se puede hacer un simple `ROLLBACK` global porque interactúan múltiples microservicios o sistemas externos. Se definen acciones compensatorias automáticas[cite: 11]:
* **Fallo en paso 7 (Despacho bancario):** Se ejecuta la acción `Release Account Balance Reservation (EVT-ERP-PAY-003-COMPENSATE)` para liberar los fondos bloqueados[cite: 11].
* **Fallo en paso 8 (Liquidación):** Si el banco no liquida exitosamente, se detona el flujo de conciliación manual y disputa bancaria[cite: 11].

## 9. Relación para mantener la integridad general
Estos mecanismos actúan en conjunto como una red de seguridad. El nivel de aislamiento **SERIALIZABLE** y los **bloqueos de concurrencia** previenen que la información se corrompa en el instante exacto de la operación[cite: 11]. Si ocurre un error, el **Patrón Saga** y las **acciones compensatorias** actúan como el `ROLLBACK` distribuido[cite: 11]. Finalmente, las **claves de idempotencia** y el **Patrón Outbox** garantizan que ante una caída del sistema (Durabilidad ACID), la recuperación no duplique transferencias reales[cite: 10, 11].

## 10. Ejemplos de fallos, recuperación y resultados
* **Ejemplo 1 (Fallo de validación local):** Según el diagrama de negocio, si durante la generación de un pedido el sistema evalúa `¿Existencias y Costos OK?` y la respuesta es `Error`, la transacción pasa a validación de fallos, se ejecuta un `ROLLBACK` automático y finaliza como `Transacción Rechazada / Bloqueada` sin afectar la base de datos[cite: 9].
* **Ejemplo 2 (Recuperación Distribuida):** Si se autoriza un pago, se bloquean los fondos en el ERP (Paso 4) pero la API bancaria se cae (Paso 7), el orquestador intercepta el fallo y emite un evento de compensación que libera la cuenta bloqueada, asegurando que la empresa siga teniendo su efectivo contable disponible para otras operaciones[cite: 11].