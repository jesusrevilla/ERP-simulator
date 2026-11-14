PLANEACIÓN PRINCIPAL
1. Planificación a Nivel de Negocio y Procesos (Funcional)
Antes de escribir código, se deben definir las reglas estrictas de cómo operará la empresa:
● Mapeo de Flujos de Trabajo (Workflows): Planificar la secuencia lógica de los
procesos. ¿Qué pasa si una factura falla al conectarse con el sistema de impuestos
(ej. SAT)? ¿Se detiene toda la venta o se encola para reintento?
● Definición de Roles y Permisos (Seguridad): Planificar quién tiene la autoridad
para realizar operaciones críticas (ej. aprobar una anulación de factura, modificar
inventarios a mano o forzar el cierre de un periodo contable).
● Políticas de Auditoría: Planificar qué tablas y acciones deben registrar un log
histórico (quién hizo qué, cuándo y desde qué IP) para rastrear errores o fraudes.
2. Desarrollo a Nivel Técnico e Ingeniería (Arquitectura)
Los desarrolladores y arquitectos de software deben construir la infraestructura lógica que
soportará esa integridad:
● Uso de Transacciones de Base de Datos: Programar utilizando bloques
transaccionales (BEGIN TRANSACTION, COMMIT, ROLLBACK) en los procedimientos
almacenados y servicios de backend para asegurar el comportamiento "todo o
nada".
● Gestión de Concurrencia y Bloqueos (Locks): Desarrollar mecanismos de
bloqueo optimista o pesimista en las tablas críticas de inventarios o saldos bancarios
para evitar el fenómeno de condiciones de carrera (race conditions) donde dos
procesos modifican el mismo dato al mismo tiempo corrompiéndolo.
● Manejo Robusto de Excepciones y Compensaciones: Si una transacción
involucra servicios externos (como una pasarela de pago o una API de timbrado
fiscal que no soporta rollbacks directos de base de datos), se deben desarrollar
transacciones compensatorias (por ejemplo, si el pago pasa pero el registro ERP
falla, programar una rutina automática que emita la devolución del dinero).
● Pruebas de Esrés y Casos Límite (Edge Cases): Desarrollar pruebas
automatizadas que simulen fallas en plena transacción (cortar la red a mitad de un
proceso de cobro masivo) para comprobar que el sistema se recupera limpiamente
sin corromper la base de datos.

1. DefiniciÃ³n de Requerimientos
1.1 Requerimientos Funcionales
â RF-01 (Atomicidad de Transacciones Compuestas): El ERP debe asegurar que
los procesos multi-tabla (ej. una factura de venta que afecta inventario, cuentas por
cobrar y contabilidad general) se ejecuten en una sola unidad lÃ³gica. Si falla un
paso, el sistema debe revertir (rollback) toda la operaciÃ³n.
â RF-02 (Bloqueo de Concurrencia): El sistema debe prevenir condiciones de
carrera (race conditions) mediante bloqueo optimista o pesimista al modificar
recursos compartidos (ej. stock de un almacÃ©n o saldos de cuentas bancarias).
â RF-03 (Trazabilidad y AuditorÃ­a): Cada transacciÃ³n debe registrarse en una
bitÃ¡cora (audit log) indicando usuario, timestamp, direcciÃ³n IP y el estado
anterior/posterior de los datos crÃ­ticos.
â RF-04 (Manejo de Excepciones y Reintentos): En caso de fallas de red o
bloqueos temporales en servicios externos (ej. pasarelas de pago o timbrado fiscal),
el ERP debe gestionar colas de reintento (retry queues) seguras sin duplicar cargos.
1.2 Requerimientos No Funcionales
â RNF-01 (Rendimiento): El tiempo de respuesta para una transacciÃ³n transaccional
compleja no debe superar los 2.5 segundos bajo una carga estÃ¡ndar de 500
usuarios concurrentes.
â RNF-02 (Disponibilidad y Tolerancia a Fallos): El motor de base de datos debe
soportar replicaciÃ³n maestro-esclavo con conmutaciÃ³n por error (failover) automÃ¡tica
para evitar pÃ©rdida de datos transaccionales.
2. DescripciÃ³n de Reglas de Negocio
â RN-01 (Partida Doble Contable): Toda transacciÃ³n financiera generada en
cualquier mÃ³dulo (ventas, compras, tesorerÃ­a) debe cumplir estrictamente con la
ecuaciÃ³n contable: ð·Ã©ððð¡ðð  = ð¶ðÃ©ððð¡ðð . Si la diferencia es distinta de cero, la
transacciÃ³n es rechazada automÃ¡ticamente.
â RN-02 (ValidaciÃ³n de Stock Disponible): No se puede confirmar una orden de
venta si el stock fÃ­sico menos el stock comprometido resulta en un valor negativo, a
menos que el parÃ¡metro de configuraciÃ³n del ERP permite inventario en negativo
con autorizaciÃ³n gerencial.
â RN-03 (Cierre de PerÃ­odo Fiscal): Ninguna transacciÃ³n con fecha contable
perteneciente a un perÃ­odo fiscal cerrado puede ser creada, modificada o eliminada,
salvo mediante un asiento de ajuste autorizado por el rol de Auditor/Administrador.
â RN-04 (Consistencia de Moneda y Tipo de Cambio): Las transacciones en
moneda extranjera deben registrarse utilizando la tasa de cambio oficial vigente a la
fecha y hora de la transacciÃ³n, evitando discrepancias en el cÃ¡lculo de diferencias
cambiarias.

3. Pruebas Unitarias
ID
Prueba
Componente / Función Escenario de
Prueba
Resultado
Esperado
TU-01 TransactionManager.Execute() Ejecutar una
transacción con 3
operaciones SQL
exitosas.
La
transacción
realiza un
COMMIT
exitoso y los
datos se
guardan.
TU-02 TransactionManager.Rollback() Simular una
excepción
controlada en la
segunda
operación de un
lote.
El sistema
ejecuta un
ROLLBACK y
la base de
datos
permanece
sin cambios.
TU-03 LedgerValidator.CheckBalance() Enviar un asiento
con Débitos
(1000) y Créditos
(950).
Retorna error
de validación
de partida
doble y
rechaza el
payload.
TU-04 InventoryLock.Acquire() Intentar
lectura/escritura
concurrente
sobre el mismo
ítem de almacén.
El segundo
hilo se pone
en espera
(timeout) o
recibe
excepción de
bloqueo.

4. Pruebas Funcionales
Orientadas a validar flujos de negocio de extremo a extremo (End-to-End):
● TF-01: Ciclo de Venta y Afectación de Stock y Contabilidad
○ Paso 1: Crear una factura de venta por un producto con stock limitado.
○ Paso 2: Simular una interrupción de red en el momento de generar el asiento
contable (post-creación de factura).
○ Verificación: El sistema debe realizar un ROLLBACK completo. La factura no
debe figurar como emitida, el stock no debe haberse descontado y no debe
existir el asiento contable huérfano.
● TF-02: Concurrencia en Órdenes de Compra (Overbooking)
○ Paso 1: Dos usuarios intentan comprar simultáneamente las últimas 5
unidades de un producto.
○ Verificación: El ERP debe procesar con éxito la primera transacción y
rechazar la segunda indicando que el stock es insuficiente, evitando saldos
negativos no autorizados.
5. Integridad de los Datos
● Integridad Referencial: Uso estricto de claves foráneas (Foreign Keys) con
restricciones en cascada controladas entre tablas maestras y transaccionales (ej. no
se puede eliminar un cliente si este cuenta con facturas activas o pendientes de
cobro).
● Restricciones de Dominio (Constraints): Validación a nivel de base de datos de
campos obligatorios, rangos numéricos positivos para precios/cantidades y formatos
estrictos para identificadores fiscales (RFC, NIT, VAT).
● Aislamiento de Transacciones (Isolation Levels): Configuración del nivel de
aislamiento en el motor de base de datos en REPEATABLE READ o SERIALIZABLE
para operaciones financieras críticas, evitando lecturas sucias (dirty reads) y lecturas
fantasma.
● Auditoría de Integridad Periódica: Scripts automáticos de validación nocturna
(checksums y conciliación de saldos) que comparan la suma de los movimientos
diarios con los saldos acumulados en las tablas de resumen contable e inventarios.




-----
codigo:
```mermaid
lowchart TD

  Start([Inicio de Venta]) --> CheckConcurrency[Bloqueo Optimista/Pesimista & Validar Inventario]

  CheckConcurrency --> ExecPayment[Procesar Pago en Pasarela Externa]

  

  ExecPayment --> PayGatewayCheck{¿Pago Exitoso?}

  PayGatewayCheck -- No --> EndFail([Fin: Venta Rechazada])

  PayGatewayCheck -- Sí --> BeginTx["BEGIN TRANSACTION (DB)"]



  BeginTx --> RecordDB[Registrar Datos de Venta & Actualizar Stock]

  RecordDB --> CallSAT[Conectar con API de Impuestos / SAT]



  CallSAT --> SATCheck{¿Timbrado Exitoso?}

  

  SATCheck -- No --> StrategyCheck{¿Política de Error SAT?}

  StrategyCheck -- Detener Venta --> RollbackTx[ROLLBACK TRANSACTION] --> Compensate[Transacción Compensatoria / Reembolso de Pago] --> EndRollback([Fin: Venta Revertida])

  StrategyCheck -- Encolar Reintento --> Enqueue[Encolar para Reintento Asíncrono] --> Audit[Registrar Log de Auditoría]



  SATCheck -- Sí --> CommitTx[COMMIT TRANSACTION] --> Audit



  Audit --> EndSuccess([Fin: Transacción Exitosa])



  %% Subproceso de Seguridad, Permisos y Auditoría

  subgraph Seguridad y Control Operativo

    CritOp[Solicitud de Operación Crítica <br/> Anulación / Modif. Inventario / Cierre] --> AuthCheck{¿Rol Autorizado?}

    AuthCheck -- No --> Deny([Acceso Denegado / Alerta])

    AuthCheck -- Sí --> ExecuteOp[Ejecutar Acción Crítica] --> LogAudit[Registrar Log Histórico <br/> Usuario, Timestamp, IP]

  end
```
