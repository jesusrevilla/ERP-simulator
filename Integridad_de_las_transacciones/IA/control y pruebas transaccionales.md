# 05. Control ACID, concurrencia y pruebas de transacciones

**Proyecto:** ERP-Simulator  
**Área:** Integridad de las transacciones  
**Tipo de entrega:** Documentación y propuestas de mejora (sin modificaciones al código)

> **Alcance de la revisión:** Se consideran las rutas de archivos asignadas y la información disponible de las entregas anteriores del ERP-Simulator. No se contó con el contenido actual de los seis archivos del repositorio para esta revisión; por ello, no se afirma que existan instrucciones `COMMIT`, `ROLLBACK`, bloqueos, bitácoras o pruebas específicas sin comprobarlas en el código. Las funciones descritas en diagramas y requerimientos se distinguen de las implementaciones verificadas.

## 1. Objetivo

Analizar cómo debe protegerse la integridad de las transacciones del ERP-Simulator para que las operaciones de compras, producción, inventario y entregas mantengan información correcta, incluso cuando ocurran errores o varios usuarios trabajen al mismo tiempo.

Se estudian las propiedades ACID, el manejo de errores y la concurrencia, además de identificar pruebas que permitan comprobar que una operación se completa correctamente o que sus cambios se cancelan cuando falla.

## 2. Archivos relacionados

| Archivo | Función dentro del análisis | Estado de verificación |
|---|---|---|
| `Integridad_de_las_transacciones/OrderDeliveryFlow.md` | Consultar el flujo planteado para pedidos y entregas, e identificar operaciones que deberían ejecutarse de forma coordinada. | Contenido actual no disponible. |
| `Integridad_de_las_transacciones/DiagramaModelo_175456.md` | Revisar el modelo y las relaciones que intervienen en las operaciones. | Contenido actual no disponible. |
| `tests/test_mrp.py` | Identificar casos de prueba existentes sobre el cálculo y funcionamiento del MRP. | Casos específicos no verificados. |
| `.github/workflows/ci.yml` | Comprobar si las pruebas se ejecutan automáticamente y qué resultados se exigen. | Pasos y ejecución no verificados. |
| `src/seed_data.py` | Revisar cómo se insertan los datos iniciales y qué ocurre si una inserción falla. | Manejo transaccional no verificado. |
| `src/create_schema.py` | Revisar cómo se crea el esquema y si se controlan errores durante la inicialización. | Manejo transaccional no verificado. |

La existencia de una ruta en la asignación del equipo no demuestra por sí misma que el mecanismo correspondiente ya esté implementado.

## 3. Descripción del funcionamiento

De acuerdo con el alcance del ERP-Simulator, los distintos módulos participan en un mismo proceso: se recibe una demanda, se consultan materiales, se planifican compras o producción, se registran entradas de inventario y finalmente se realizan entregas. Estas operaciones pueden afectar más de un registro de la base de datos.

Por ejemplo, al registrar una entrega se espera que el ERP relacione el pedido con la salida del producto y actualice las existencias. Si se registra la salida sin actualizar el inventario, los datos dejan de coincidir. Este ejemplo describe una necesidad de integridad del proceso, **no una confirmación de cómo está programada actualmente la entrega**.

Los archivos `OrderDeliveryFlow.md` y `DiagramaModelo_175456.md` sirven como referencia para identificar esas relaciones y el orden previsto de las operaciones. Por otra parte, `seed_data.py` y `create_schema.py` corresponden a la preparación de los datos y la estructura del sistema. El archivo `test_mrp.py` está destinado a las pruebas del MRP y `ci.yml` a la configuración de integración continua, aunque su comportamiento exacto debe revisarse antes de afirmar qué validaciones realizan.

## 4. Mecanismos de integridad

### 4.1. Propiedades ACID

Las propiedades ACID indican las condiciones que debe cumplir una transacción para conservar la confiabilidad de los datos:

| Propiedad | Explicación | Aplicación al ERP-Simulator |
|---|---|---|
| **Atomicidad** | Una transacción se completa en su totalidad o se cancelan sus cambios. | Una entrega no debería descontar inventario si falla el registro que la respalda. |
| **Consistencia** | La operación debe respetar las reglas y restricciones de la base de datos. | No aceptar cantidades inválidas ni referencias a registros inexistentes. |
| **Aislamiento** | Las transacciones simultáneas no deben producir resultados incorrectos por interferir entre sí. | Dos entregas no deberían consumir al mismo tiempo las mismas existencias disponibles. |
| **Durabilidad** | Los cambios confirmados permanecen almacenados aunque el sistema se interrumpa. | Una recepción confirmada debe conservarse después de reiniciar la aplicación. |

**Estado en el proyecto:** Estas propiedades son criterios para evaluar el sistema. No se ha verificado si el código actual las garantiza en cada operación.

### 4.2. Uso de COMMIT y ROLLBACK

`COMMIT` confirma definitivamente los cambios de una transacción. `ROLLBACK` cancela los cambios que todavía no se han confirmado.

**Ejemplo conceptual de una entrega:**

1. Iniciar una transacción.
2. Comprobar que el pedido sea válido y que exista inventario suficiente.
3. Registrar la entrega y descontar las existencias.
4. Si todos los pasos terminan correctamente, ejecutar `COMMIT`.
5. Si cualquier paso falla antes de confirmar, ejecutar `ROLLBACK`.

De esta forma se evita que solo una parte de la operación quede guardada. La sintaxis exacta depende de la base de datos y de cómo la aplicación maneje las conexiones. **Este procedimiento es una propuesta de control; no se ha confirmado la presencia de estas instrucciones en los archivos revisables.**

### 4.3. Manejo de errores

Las operaciones del ERP deben detectar situaciones como cantidades no válidas, inventario insuficiente, registros inexistentes o fallas durante la escritura de datos.

Una forma adecuada de atender estos casos consiste en validar los datos antes de realizar cambios, capturar los errores de la operación y cancelar la transacción cuando no pueda completarse. También es importante devolver un mensaje claro al usuario y registrar información del error para facilitar su revisión, sin exponer datos sensibles.

**Estado en el proyecto:** Las validaciones de negocio aparecen en el alcance general de los módulos, pero falta comprobar cómo se manejan las excepciones y si las operaciones fallidas revierten realmente sus cambios.

### 4.4. Control de concurrencia y bloqueos

La concurrencia aparece cuando varias operaciones intentan consultar o modificar los mismos datos al mismo tiempo.

Por ejemplo, si hay 10 piezas disponibles y dos usuarios intentan entregar 7 piezas cada uno, ambos podrían leer inicialmente la misma cantidad. Sin un control adecuado, se pueden aprobar entregas que en conjunto superen el inventario real.

Para reducir este riesgo se propone utilizar transacciones con aislamiento adecuado, actualizaciones condicionadas a la existencia disponible y, cuando corresponda, bloqueos de registros o mecanismos de control de versiones. La elección debe adaptarse al motor de base de datos y probarse con operaciones simultáneas.

**Estado en el proyecto:** No se cuenta con evidencia suficiente para afirmar que actualmente se utilicen bloqueos, niveles de aislamiento específicos o control de concurrencia.

### 4.5. Auditoría y trazabilidad

La trazabilidad permite conocer qué operación se realizó, cuándo ocurrió, quién la autorizó y qué registros fueron afectados.

El ERP debería conservar información como el identificador de la operación, su tipo, el usuario responsable, la fecha, el resultado y la referencia al pedido, recepción o entrega correspondiente. Esto facilita investigar movimientos duplicados, errores o cambios no autorizados.

**Estado en el proyecto:** La necesidad de seguimiento se identifica en los procesos del ERP, pero no se ha confirmado la implementación de una tabla o registro de auditoría transaccional.

### 4.6. Pruebas automatizadas existentes

Los archivos asignados permiten identificar dos puntos de interés:

- `tests/test_mrp.py`: archivo que debe inspeccionarse para determinar qué pruebas del MRP existen, qué condiciones verifican y si contemplan errores o cambios en la base de datos.
- `.github/workflows/ci.yml`: archivo que debe inspeccionarse para determinar si las pruebas se ejecutan automáticamente durante el desarrollo y si un fallo impide dar por correcta la ejecución del flujo.

**No es posible confirmar, sin leer estos archivos, el número de pruebas, sus resultados, el uso de una base de datos de prueba ni la ejecución efectiva del flujo de integración continua.** Tampoco debe asumirse que probar el cálculo del MRP equivale a probar la atomicidad o la concurrencia de la base de datos.

## 5. Riesgos de inconsistencia

| Riesgo | Posible consecuencia |
|---|---|
| Una operación falla después de modificar solo algunos registros. | Una entrega o recepción queda registrada de forma incompleta. |
| No se revierte una operación fallida. | Permanecen movimientos o cantidades incorrectas. |
| Dos usuarios actualizan la misma existencia al mismo tiempo. | Se pierden actualizaciones o se asigna más inventario del disponible. |
| Se ejecuta una inserción de datos iniciales más de una vez. | Aparecen registros duplicados si no existen controles adecuados. |
| Una inicialización falla después de crear parte del esquema. | La base de datos queda parcialmente preparada; la reversión depende del motor y de las instrucciones ejecutadas. |
| No se registra quién modificó los datos. | Resulta difícil encontrar el origen de un error o movimiento incorrecto. |
| Las pruebas solo revisan cálculos correctos. | Los errores transaccionales pueden pasar desapercibidos. |

## 6. Propuestas de mejora

Las siguientes acciones son **propuestas**, no funcionalidades confirmadas del ERP-Simulator:

1. **Definir límites claros para cada transacción.** Identificar qué cambios de un pedido, recepción o entrega deben confirmarse juntos, evitando registros parciales.
2. **Aplicar confirmación o reversión de cambios.** Utilizar transacciones y el manejo apropiado de `COMMIT` y `ROLLBACK` en las operaciones que escriben varios registros.
3. **Validar datos antes de modificar existencias.** Comprobar identificadores, cantidades positivas, estados permitidos y disponibilidad real de materiales o productos.
4. **Proteger operaciones simultáneas.** Utilizar actualizaciones condicionadas, bloqueos o control de versiones según las características de la base de datos.
5. **Evitar movimientos repetidos.** Asociar cada operación con un identificador único y validar que una recepción o entrega ya procesada no vuelva a aplicarse por error.
6. **Incorporar registros de auditoría.** Conservar el historial de operaciones, incluyendo resultado, fecha, usuario y documento relacionado.
7. **Ampliar las pruebas automatizadas.** Incluir escenarios con errores, datos inválidos y transacciones simultáneas, además de las pruebas de cálculo del MRP.
8. **Revisar las ejecuciones de integración continua.** Configurar o comprobar que `ci.yml` ejecute las pruebas relevantes y reporte los fallos antes de integrar cambios.

### 6.1. Pruebas adicionales propuestas

| Prueba | Procedimiento general | Resultado esperado |
|---|---|---|
| **Confirmación correcta** | Realizar una operación válida que afecte varios registros. | Todos los cambios quedan guardados y relacionados correctamente. |
| **Reversión por error** | Provocar una falla después del primer cambio, pero antes de terminar la operación. | No queda ningún cambio parcial de esa transacción. |
| **Inventario insuficiente** | Solicitar una salida mayor a las existencias disponibles. | La salida se rechaza y el inventario permanece igual. |
| **Operaciones simultáneas** | Ejecutar dos salidas concurrentes que, sumadas, superen la existencia inicial. | No se confirma una cantidad total mayor que la disponible. |
| **Operación repetida** | Procesar dos veces la misma confirmación de entrega. | El movimiento se aplica una sola vez. |
| **Datos inválidos** | Enviar una cantidad negativa o una referencia inexistente. | Se rechaza la operación sin modificar datos válidos. |
| **Inicialización repetida** | Ejecutar nuevamente la carga inicial en un entorno de prueba. | No se crean duplicados indebidos; si el proceso no admite repetición, falla de forma controlada. |
| **Interrupción del proceso** | Simular una falla antes de confirmar una transacción. | Se conserva el último estado válido de la base de datos. |
| **Auditoría** | Confirmar una operación y consultar su registro de seguimiento. | Se identifica la operación, su resultado y su relación con el documento correspondiente. |
| **Integración continua** | Ejecutar las pruebas desde el flujo de CI e introducir un caso de prueba que falle de manera controlada. | El flujo informa el fallo y no presenta la ejecución como exitosa. |

Las pruebas deben ejecutarse en un entorno aislado con datos controlados. Para confirmar que funcionan, es necesario observar sus resultados reales, no solo documentar el resultado esperado.

### 6.2. Comprobaciones pendientes en los archivos del repositorio

Para completar una revisión técnica con evidencia, se recomienda comprobar lo siguiente sin modificar el código:

- En `OrderDeliveryFlow.md`, identificar exactamente qué pasos se consideran una sola operación y cuáles son independientes.
- En `DiagramaModelo_175456.md`, identificar las relaciones y restricciones descritas para los datos afectados por cada transacción.
- En `tests/test_mrp.py`, registrar los nombres de las pruebas y distinguir si prueban solo cálculos o también cambios persistentes.
- En `.github/workflows/ci.yml`, confirmar los eventos que ejecutan el flujo, los comandos de prueba y el comportamiento ante fallas.
- En `src/seed_data.py`, buscar inserciones repetibles, validaciones, manejo de excepciones y confirmación de cambios.
- En `src/create_schema.py`, revisar cómo se crea el esquema, qué pasa ante errores y si la inicialización puede repetirse de manera segura.

## 7. Conclusión

El control de integridad transaccional es importante porque las operaciones del ERP-Simulator están relacionadas: un error en el registro de una entrega, una recepción o una actualización de inventario puede afectar otros procesos. Las propiedades ACID ayudan a definir cómo deben guardarse los cambios, mientras que el control de concurrencia, la auditoría y las pruebas permiten detectar y prevenir inconsistencias.

La documentación y los requerimientos disponibles permiten identificar qué controles son necesarios, pero **no bastan para demostrar que todos ya estén programados y probados**. Por esta razón, las mejoras propuestas se enfocan en confirmar o revertir operaciones completas, proteger los datos frente a accesos simultáneos y ampliar las pruebas automatizadas, sin modificar el código como parte de esta entrega.
