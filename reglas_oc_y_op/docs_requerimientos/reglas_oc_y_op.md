#Documento de Requerimientos - MRP (Órdenes de Compra y Producción)

1. Definición de Requerimientos Funcionales
El sistema MRP debe gestionar los flujos de creación, seguimiento y cierre de Órdenes de Compra 
(OC) y Órdenes de Producción (OP). Flujo de Órdenes de Compra: Generación de OC por 
desabasto, aprobación, recepción de inventario y registro de proveedores. Flujo de Órdenes de 
Producción: Creación de OP, validación/reserva de componentes, ejecución y registro de producto 
terminado.

Datos y entidades requeridas:

• Materia Prima/Componente: ID Material, Descripción, Stock Físico, Stock Reservado, 
Punto de Reorden, Unidad de Medida.
• Producto Terminado: ID Producto, Descripción, Lista de Materiales (BOM).
• Orden de Compra (OC): ID OC, Proveedor, Fecha de Creación, Ítems (Materia Prima, 
Cantidad, Precio Unitario), Estado (Pendiente, Parcialmente Recibida, Recibida, Pagada).
• Orden de Producción (OP): ID OP, ID Producto Terminado, Cantidad a Fabricar, Ítems 
Consumidos (Materiales requeridos), Estado (Planeada, En Proceso, Completada, 
Cancelada).
2. Descripción de las Reglas de Negocio
Restricción de Inventario: El inventario físico de cualquier materia prima o producto terminado 
nunca puede ser negativo.

Validación de Pago: No se permite autorizar o realizar el pago de una Orden de Compra (o sus 
partidas) si los artículos correspondientes no han sido marcados como "Recibidos" en el sistema.

Reserva de Materiales: Una Orden de Producción solo puede pasar a estado "En Proceso" si existe 
stock físico suficiente para cubrir todos los componentes de su Lista de Materiales. Al pasar a "En 
Proceso", dicho stock se mueve a "Stock Reservado".

Generación de Demanda: El sistema debe sugerir una Orden de Compra cuando el inventario 
disponible (Stock Físico - Stock Reservado + Stock en Tránsito) caiga por debajo de su Punto de 
Reorden.

3. Integridad de los Datos
Atomicidad de transacciones: Al confirmar una recepción de OC, se debe actualizar el inventario 
físico y cambiar el estado de la OC en la misma transacción para evitar inconsistencias de datos. Lo 
mismo aplica al completar una OP.

Referencias Obligatorias: Toda OC debe tener asociado un ID de Proveedor activo; toda OP debe 
tener un BOM vigente.

Restricciones de Dominio: Los campos de "Cantidad", "Precio Unitario" y "Stock" deben aceptar 
únicamente valores numéricos mayores o iguales a cero.

Inmutabilidad de Documentos Cerrados: Una vez que una OP está "Completada" o una OC está 
"Pagada", sus líneas de detalle no pueden ser modificadas.

4. Pruebas Unitarias
test_inventario_no_negativo: Verificar que el método descontar_stock(id, cantidad) arroje una 
excepción si cantidad > stock_fisico.

test_validacion_pago_oc: Verificar que el método aprobar_pago_oc(id_oc) retorne un error si el 
estado de la OC es distinto a "Recibida".

test_calculo_reorden: Validar que la función requiere_compra(stock, punto_reorden) retorne 
Verdadero si stock < punto_reorden.

test_validar_tipos_datos: Insertar valores negativos en la función crear_linea_oc() y asegurar que 
el sistema devuelva un error.

test_consumo_forecast: Validar que si el Forecast es de 100 unidades y se reciben pedidos por 40 
unidades, la demanda bruta calculada siga siendo 100 (y no 140).

test_explosion_bom: Verificar que una propuesta de OP por 10 unidades de producto terminado 
multiplique correctamente las cantidades en el BOM para generar las propuestas de OC de 
materia prima correspondientes.

5. Pruebas Funcionales
• Flujo Completo de OP Exitoso: Crear una OP, validar que el sistema reserva los 
componentes. Completar la OP y verificar que el stock de materiales disminuye y el del 
producto terminado aumenta.
• Prevención de Producción sin Stock: Intentar iniciar una OP sin material suficiente. Validar 
que el sistema lanza el mensaje de error y no avanza la OP a estado "En Proceso".
• Recepción y Pago de OC: Crear una OC e intentar pagarla (validar rechazo). Registrar la 
recepción, verificar incremento de stock y volver a intentar el pago (validar éxito).
• Manejo de Transacciones Fallidas: Simular un fallo de sistema justo después de marcar 
una OC como "Recibida" pero antes de actualizar el stock, comprobando que se ejecuta un 
rollback manteniendo la integridad.
6. Roles, Permisos y Autorizaciones
• Comprador / Analista de Compras: Tiene permisos para crear, editar (solo en estado 
"Pendiente") y cancelar Órdenes de Compra. No tiene autorización para aprobar pagos ni 
modificar el inventario físico directamente.
• Planeador de Producción: Autorizado para crear Órdenes de Producción, asignarles el 
estado "Planeada" y liberar las órdenes a "En Proceso", lo cual detona la reserva de 
materiales. No puede modificar las Listas de Materiales (BOM).
• Almacenista / Recepcionista de Inventario: Único rol autorizado para confirmar la 
recepción física de mercancía de las OC (cambiando el estado a "Recibida") y para reportar 
la culminación de una OP (cambiando el estado a "Completada" y dando ingreso al 
producto terminado).
• Finanzas / Cuentas por Pagar: Tiene acceso de solo lectura a las OC y al inventario. Es el 
único rol con privilegios para cambiar el estado de una OC a "Pagada" una vez que el 
sistema valida la recepción de los artículos.
7. Gestión de Demanda y Pronósticos (Forecast)
• Ingreso de Pronósticos: El sistema debe permitir la carga de un pronóstico de ventas 
(Forecast) por producto terminado para un periodo de tiempo determinado (ej. semanal o 
mensual).
• Consumo de Pronóstico (Forecast Consumption): Los pedidos de venta reales (Órdenes de 
Cliente) ingresados en el sistema deben "consumir" el forecast del mismo periodo. La 
Demanda Bruta será el mayor valor entre el Forecast total y los Pedidos Reales, evitando 
así duplicar la necesidad de producción.
• Cálculo de Demanda Neta: El sistema debe calcular la Demanda Neta restando el 
inventario disponible actual de la Demanda Bruta.
• Explosión de Materiales (MRP): Si la Demanda Neta de un producto terminado es mayor a 
cero, el sistema debe detonar automáticamente una propuesta de Orden de Producción. 
Simultáneamente, debe realizar la "explosión" de la Lista de Materiales (BOM) para 
calcular la demanda dependiente de las materias primas.

```mermaid
flowchart TD
%% Definición de Carriles (Swimlanes) a través de subgrafos
subgraph Produccion [Planeación y Producción]
E_Inicio((Inicio: Ingreso de Demanda o Pronóstico))
T_AprobarProd[Revisar y Aprobar Órdenes de Producción]
E_Fin((Fin: Órdenes Liberadas para Ejecución))
end
subgraph Sistema [Sistema MRP]
T_Explosion[Ejecutar Explosión de Lista de Materiales - BOM]
T_Calculo[Evaluar Inventario y Requerimientos Netos]
G_Materiales{¿Se requiere material de proveedores?}
T_GenCompra[Generar Propuestas de Órdenes de Compra]
T_GenProd[Generar Propuestas de Órdenes de Producción]
end
subgraph Compras [Departamento de Compras]
T_AprobarCompra[Revisar y Autorizar Órdenes de Compra]
end
%% Flujo de Secuencia (Sequence Flow)
E_Inicio --> T_Explosion
T_Explosion --> T_Calculo
T_Calculo --> G_Materiales
%% Bifurcación (Compuerta)
G_Materiales -- Sí --> T_GenCompra
G_Materiales -- No --> T_GenProd
%% Interacciones interdepartamentales
T_GenCompra --> T_AprobarCompra
T_AprobarCompra --> T_GenProd
T_GenProd --> T_AprobarProd
T_AprobarProd --> E_Fin
%% Estilos visuales para cumplir con la notación estándar BPMN
classDef eventoInicio fill:#d4edda,stroke:#28a745,stroke-width:2px;
classDef eventoFin fill:#f8d7da,stroke:#dc3545,stroke-width:3px;
classDef compuerta fill:#fff3cd,stroke:#ffc107,stroke-width:2px,shape:diamond;
classDef tarea fill:#e2e3e5,stroke:#6c757d,stroke-width:1px,rx:5px,ry:5px;
class E_Inicio eventoInicio;
class E_Fin eventoFin;
class G_Materiales compuerta;
class T_AprobarProd,T_Explosion,T_Calculo,T_GenCompra,T_GenProd,T_AprobarCompra tarea;
```
### Rafael Sánchez Saucedo
# Documento de Requerimientos - MRP (Trazabilidad, Caducidad y Merma)
**Módulo:** Gestión Avanzada de Órdenes de Compra (OC) y Órdenes de Producción (OP)

---

## 1. Definición de Requerimientos Funcionales

El módulo gestiona el ciclo operativo de aprovisionamiento y manufactura bajo esquemas de control por lotes, caducidad, merma técnica y costos indirectos de fabricación.

### Datos y Entidades Requeridas

* **Lote de Materia Prima / Componente:** ID Lote, ID Material, Cantidad Disponible, Cantidad Reservada, Fecha de Fabricación, Fecha de Caducidad, Ubicación en Almacén, Costo Unitario Real.
* **Lista de Materiales y Operaciones (BOM/Routing):** ID BOM, ID Producto Terminado, Componentes requeridos, Porcentaje de Scrap/Merma Nominal, Tiempo Estándar de Operación (minutos/horas máquina), Costo Indirecto Estimado.
* **Orden de Compra con Inspección (OC):** ID OC, ID Proveedor, Incoterm/Condición de Entrega, Líneas de Detalle (ID Material, Cantidad Solicitada, Cantidad Aceptada, Cantidad Rechazada, Precio Unitario, Lote Proveedor), Estado (`Emitida`, `En Aduana/Tránsito`, `Inspección de Calidad`, `Cerrada Conforme`, `Devuelta`).
* **Orden de Producción con Consumo Real (OP):** ID OP, ID Producto Terminado, Cantidad Programada, Cantidad Real Producida, Cantidad Desperdiciada (Scrap Real), Asignación de Lotes Consumidos (FIFO/FEFO), Centro de Trabajo, Estado (`Liberada`, `En Preparación`, `Paro de Línea`, `Finalizada con Desvío`, `Cerrada`).

---

## 2. Descripción de las Reglas de Negocio

* **Asignación de Materiales por FEFO (First Expired, First Out):** Al reservar componentes para una OP, el sistema debe asignar automáticamente aquellos lotes cuya fecha de caducidad sea más próxima, bloqueando lotes con vida útil menor al tiempo estimado de manufactura y distribución.
* **Ajuste por Merma Estándar:** Toda explosión de materiales para una OP debe calcular la materia prima bruta sumando el porcentaje de scrap inherente al proceso:
  $$\text{Cantidad Bruta} = \frac{\text{Cantidad Neta}}{1 - \% \text{Merma Nominal}}$$
* **Cuarentena e Inspección Previa al Stock Físico:** Las recepciones de OC no ingresan directamente a stock disponible; deben ingresar a un almacén lógico de `Inspección/Calidad`. Solo las partidas marcadas como "Aprobadas" se trasladan a inventario disponible; las unidades con defecto deben generar un folio de devolución o nota de crédito.
* **Tolerancia en Sobredelivery de Proveedores:** El sistema permite variaciones en la recepción física contra la OC de un máximo de $\pm 5\%$ en productos a granel/líquidos, recalculando la factura automáticamente sin permitir recepciones fuera de dicha tolerancia sin autorización gerencial.
* **Cierre de OP con Desvío:** Si la producción real difiere de la cantidad programada por variaciones de scrap, la OP solo puede cerrarse si el supervisor documenta la justificación del desvío cuando supere el umbral del $\pm 3\%$.

---

## 3. Integridad de los Datos

* **Trazabilidad Bidireccional Estricta:** Todo registro de producto terminado generado en una OP debe almacenar la relación matricial de los IDs de lote de materias primas exactos que se consumieron durante su corrida de producción (genealogía de lote).
* **Inmutabilidad de Lotes Cerrados:** Los registros de lotes asociados a una OP `Cerrada` o una OC `Cerrada Conforme` pasan a modo solo lectura; cualquier corrección posterior debe ejecutarse mediante movimientos de ajuste contable auditados.
* **Consistencia de Fechas Operativas:** La fecha de entrega prometida en una OC no puede ser anterior a la fecha de emisión; la fecha de caducidad asignada a un lote no puede ser anterior ni igual a su fecha de recepción/fabricación.
* **Balance de Masa en Producción:** En cada OP, la suma de la masa/cantidad del producto terminado obtenido más el scrap registrado debe cuadrar con la cantidad total de insumos consumidos dentro de la tolerancia de merma configurada.

---

## 4. Pruebas Unitarias

* `test_prioridad_fefo_lotes`: Validar que el algoritmo de reserva asigne primero el lote que caduca en 10 días antes que el lote que caduca en 30 días, independientemente de la fecha de recepción en almacén.
* `test_bloqueo_lote_vencido`: Verificar que la función `reservar_componente()` lance una excepción de tipo `ExpiredBatchException` si el lote seleccionado ha superado su fecha de caducidad.
* `test_calculo_merma_scrap`: Comprobar que para una necesidad de 100 unidades con una merma configurada del 10%, el sistema calcule una demanda de insumo de 111.11 unidades (o el redondeo superior establecido).
* `test_recepcion_excede_tolerancia`: Insertar una recepción física con un 10% por encima de lo solicitado en la OC y verificar que el método lance un error de validación de exceso de tolerancia.
* `test_cuarentena_aislada`: Asegurar que el método `obtener_stock_disponible_mrp(id_material)` no contabilice las existencias en almacén de `Inspección/Calidad`.

---

## 5. Pruebas Funcionales

* **Ciclo de Aprobación de Calidad y Devolución Parcial en OC:** Generar una OC de 1000 unidades. Registrar la llegada al área de inspección, aprobar 900 unidades y rechazar 100 por no conformidad. Verificar que el inventario disponible aumente únicamente en 900 unidades y que el estado de la OC se actualice a `Cerrada con Discrepancia`.
* **Trazabilidad de Retiro de Mercado (Recall):** Seleccionar un lote de materia prima defectuoso, ejecutar la consulta de genealogía inversa y validar que el sistema devuelva de inmediato todos los folios de OP donde se utilizó dicho lote, junto con los lotes de producto terminado resultantes y sus clientes asignados.
* **Paro de Línea por Insumo Degradado:** Iniciar una OP en estado `En Proceso`. Simular la invalidación de un lote de insumo en planta por daño físico; comprobar que el sistema bloquea el avance de la orden a `Completada`, emite la alerta al supervisor y permite la requisición de un lote sustituto sin reiniciar la orden desde cero.

```mermaid
%%{init: {'flowchart': {'curve': 'stepBefore', 'nodeSpacing': 50, 'rankSpacing': 70}}}%%
flowchart LR
%% Nodos principales
Start(("✉️"))
Timer((("#")))
Task1("<b>Verificar el estado<br/>del grupo de trabajo</b>")
Gateway{"<b>¿Grupo de<br/>trabajo<br/>continúa<br/>activo?</b>"}
Task2("<b>[Enviar]<br/>Enviar lista<br/>actual de<br/>asuntos</b>")
%% Nodos inferiores
EndNode((" "))
DataObj[/"#<br/><b>Lista de<br/>asuntos</b>"\]
%% Etiquetas externas debajo de los círculos
StartLabel["<b>Grupo de<br/>trabajo activo</b>"]
TimerLabel["<b>Viernes<br/>6 PM</b>"]
%% 1. Bucle declarado primero para que pase por ARRIBA
Task2 --> Timer
%% 2. Flujo central recto
Start --> Timer
Timer --> Task1
Task1 --> Gateway
Gateway -- "<b>/ &nbsp; Sí</b>" --> Task2
%% 3. Flujo "No" hacia ABAJO
Gateway -- "<b>No</b>" --> EndNode
%% 4. Alineaciones invisibles y asociación de datos
Start ~~~ StartLabel
Timer ~~~ TimerLabel
EndNode ~~~ DataObj
DataObj -.-> Task2
%% Estilos exactos al diagrama original
classDef startStyle fill:#38cc00,stroke:#000,stroke-width:2px,color:#000
classDef timerStyle fill:#f5c281,stroke:#000,stroke-width:2px,color:#000
classDef taskStyle fill:#ffcd00,stroke:#000,stroke-width:2px,color:#000,rx:8px,ry:8px
classDef gwStyle fill:#38cc00,stroke:#000,stroke-width:2px,color:#000
classDef endStyle fill:#f27979,stroke:#000,stroke-width:2px,color:#000
classDef docStyle fill:#ffffff,stroke:#000,stroke-width:1.5px,color:#000
classDef labelStyle fill:none,stroke:none
class Start startStyle
class Timer timerStyle
class Task1,Task2 taskStyle
class Gateway gwStyle
class EndNode endStyle
class DataObj docStyle
class StartLabel,TimerLabel labelStyle
```
# Modelo de Procesos de Negocio (BPMN) - Módulo MRP: Reglas de Orden de Compra y Producción
# Documento de requerimientos iniciales

## Simulador ERP, sistema MRP

### Módulo: Reglas de orden de compra y de orden de producción

**Autor/a:** Yazmin Guerrero Guevara - 182483

\---

# 1\) Definición de requerimientos funcionales

* **Límites de Stock:** El sistema debe permitir registrar y actualizar los límites de stock (stock mínimo, stock máximo y punto de reorden) para cada material o componente en el inventario.
* **Generación de Órdenes de Compra:** El motor MRP debe ser capaz de respetar estrictamente los límites de stock definidos al calcular las necesidades, generando propuestas o registros automáticos de Órdenes de Compra (OC) solo cuando el inventario disponible esté por debajo del punto de reorden.
* **Generación de Órdenes de Producción:** El sistema debe detonar automáticamente Órdenes de Producción (OP) basadas en la explosión de materiales (BOM) cuando exista demanda de productos terminados y se valide la disponibilidad de componentes necesarios.

\---

# 2\) Descripción de las reglas de negocio que aplican

* **Validación de Stock Mínimo para Compras:** Ninguna Orden de Compra de materia prima puede ser procesada por debajo de la cantidad necesaria para alcanzar el stock óptimo o para cubrir el faltante calculado por el MRP, evitando compras innecesarias.
* **Restricción de Lotes de Producción:** Las Órdenes de Producción deben ajustarse a los múltiplos o tamaños de lote establecidos en el catálogo de manufactura (no se pueden lanzar fracciones de productos).
* **Disponibilidad de Materiales para Producción:** El sistema debe verificar que los componentes de la Lista de Materiales (BOM) estén disponibles en inventario antes de liberar una Orden de Producción; de lo contrario, el MRP debe frenar la orden o sugerir de manera simultánea la Orden de Compra del componente faltante.

\---

# 3\) Pruebas unitarias

* **Cálculo de punto de reorden:** Verificar que la función lógica devuelva `true` para la generación de una Orden de Compra únicamente cuando $\\text{Stock Actual} \\le \\text{Stock Mínimo}$.
* **Validación de lotes de producción:** Comprobar que el algoritmo de cálculo de órdenes de producción redondee correctamente hacia arriba o aplique el múltiplo de lote configurado para el producto ensamblado.
* **Detección de faltantes en BOM:** Evaluar de forma aislada que el método de desglose de materiales identifique correctamente qué componentes faltan en el inventario al simular una orden de producción.

\---

# 4\) Pruebas funcionales

* **Flujo completo de Orden de Compra:** Simular una reducción de inventario por debajo del mínimo establecido y comprobar que el sistema genera exitosamente el registro de la Orden de Compra con los datos correctos del proveedor y la cantidad faltante.
* **Flujo completo de Orden de Producción:** Ingresar un pedido de venta de producto terminado, ejecutar el MRP y verificar que se genera la Orden de Producción junto con el bloqueo o descuento correcto de los insumos en el almacén.
* **Restricción por falta de insumos:** Validar que, si se intenta liberar una Orden de Producción sin tener la materia prima necesaria, el sistema impida el flujo y emita la alerta correspondiente o sugiera la compra.

\---

# 5\) Integridad de los datos (Enfoque de integración en Git/GitHub)

Para garantizar la consistencia, calidad y confiabilidad de la información dentro del módulo de órdenes de compra y producción, se establecen las siguientes reglas de integridad:

* **Validación de tipos de datos y restricciones de nulos:** Todos los campos monetarios, cantidades de materiales, fechas de entrega y folios deben contar con validaciones estrictas en el modelo y base de datos que impidan valores nulos (`NOT NULL`) y me aseguren el tipo de dato correcto (por ejemplo, enteros positivos para cantidades y flotantes con precisión para costos).
* **Prevención estricta de stock negativo:** Ninguna transacción derivada de una orden de compra (entradas) o de una orden de producción (salidas/consumo de insumos) podrá permitir que el inventario disponible de un material caiga en números negativos. El sistema debe rechazar la operación si el stock es insuficiente.
* **Valores lógicos y rangos permitidos:** Los estados de las órdenes (ej. *Pendiente*, *Aprobada*, *En Proceso*, *Cancelada*, *Finalizada*) deben estar restringidos a un catálogo o enumeración fija (`Enum`), evitando la inserción de cadenas de texto erróneas, vacías o valores atípicos.
* **Consistencia referencial - Llaves foráneas:** Las órdenes de compra y de producción deben mantener una relación de integridad referencial estricta con las tablas de catálogo de materiales, proveedores y almacenes, evitando la creación de registros huérfanos o asociados a elementos inexistentes en el sistema.


Este documento traslada los requerimientos funcionales, reglas de negocio y validaciones del **Simulador ERP - Módulo MRP** a una representación de diagrama de proceso bajo el estándar **Business Process Model and Notation (BPMN)**, utilizando la sintaxis gráfica de **Mermaid**.

---

## 1. Mapeo de Elementos BPMN

De acuerdo con la especificación de BPMN, el diagrama se estructuró utilizando los siguientes elementos básicos:

* **Carriles de Nado (Swimlanes / Pools):**
  * **Ventas / Cliente:** Detonador inicial de demanda.
  * **Motor MRP (Sistema):** Evaluación de inventarios, explosión de materiales (BOM) y toma de decisiones.
  * **Almacén / Inventario:** Gestión e inspección de stock y límites de reorden.
  * **Compras / Proveedores:** Generación y procesamiento de Órdenes de Compra (OC).
  * **Producción:** Liberación de Órdenes de Producción (OP) ajustadas a lotes.

* **Eventos:**
  * **Iniciales:** Ingreso de pedido de venta / Reducción de stock.
  * **Intermedios:** Alertas por insumos faltantes o validaciones.
  * **Finales:** OC procesada, OP liberada, Proceso bloqueado/frenado.

* **Compuertas de Control (Gateways):**
  * Evaluaciones condicionales para:
    * $\text{Stock Actual} \le \text{Punto de Reorden}$
    * Disponibilidad completa de insumos según Lista de Materiales (BOM).

---

## 2. Diagrama de Proceso BPMN (Mermaid)

```mermaid
graph TD
    %% Evento de Inicio
    SubGraph1[Ventas] -->|1. Ingreso de Pedido de Venta / Demanda PT| StartEvent(("● Evento Inicial:<br>Demanda Registrada"))

    subgraph MRP_Engine [" Motor MRP (Sistema) "]
        StartEvent --> Activity1["Explosión de Materiales (BOM)"]
        Activity1 --> Activity2["Consultar Stock Disponible de Componentes"]
        
        %% Compuerta 1: Disponibilidad de BOM
        Activity2 --> Gateway1{"¿Componentes BOM<br>Disponibles?"}
        
        %% Ruta No Disponible
        Gateway1 -- No --> IntermediateAlert["Emite Alerta de Insuficiencia"]
        IntermediateAlert --> Activity3["Calcular Faltante según Stock Óptimo"]
        
        %% Ruta Disponible
        Gateway1 -- Sí --> Activity4["Ajustar Lote a Múltiplos de Manufactura"]
        Activity4 --> Activity5["Bloquear/Reservar Insumos en Almacén"]
        Activity5 --> EndProduction(("● Evento Final:<br>Liberar Orden de Producción (OP)"))
    end

    subgraph Almacen_Compras [" Almacén / Compras "]
        Activity3 --> Gateway2{"¿Stock Actual <=<br>Punto de Reorden?"}
        
        Gateway2 -- Sí --> Activity6["Generar Propuesta/Registro de Orden de Compra (OC)"]
        Gateway2 -- No --> CancelEvent(("● Evento Final:<br>Frenar Orden (Sin Recompra)"))
        
        Activity6 --> Activity7["Validar Datos de Proveedor y Cantidad Mínima"]
        Activity7 --> Activity8["Procesar Entrada de Materia Prima"]
        Activity8 --> Activity9["Actualizar Stock (Evitar Stock Negativo)"]
        Activity9 --> Activity2
    end

    %% Estilos de Nodos
    style StartEvent fill:#2ecc71,stroke:#27ae60,stroke-width:2px,color:#fff
    style EndProduction fill:#e74c3c,stroke:#c0392b,stroke-width:2px,color:#fff
    style CancelEvent fill:#e74c3c,stroke:#c0392b,stroke-width:2px,color:#fff
    style Gateway1 fill:#f1c40f,stroke:#f39c12,stroke-width:2px
    style Gateway2 fill:#f1c40f,stroke:#f39c12,stroke-width:2px
```

---

## 3. Especificación de Reglas e Integridad de Datos

### Reglas de Negocio Incorporadas
1. **Límites de Stock:** Se valida que la Orden de Compra sólo sea generada si $\text{Stock Actual} \le \text{Punto de Reorden}$.
2. **Restricción de Lotes:** La actividad de ajuste de lote aplica redondeo hacia arriba / múltiplos configurados para evitar fracciones.
3. **Disponibilidad BOM:** Antes de liberar una Orden de Producción, se verifica el stock de insumos. Si faltan componentes, se emite una alerta y se sugiere/genera la Orden de Compra correspondiente.

### Reglas de Integridad (Git/Base de Datos)
* **Prevención de Stock Negativo:** Toda salida/consumo de insumos exige validación previa de disponibilidad suficiente antes de proceder.
* **Tipos de Datos y Enum:** Campos monetarios, folios y cantidades con restricciones estrictas `NOT NULL` y estados de las órdenes acotados a enumeraciones fijas (`Pendiente`, `Aprobada`, `En Proceso`, `Cancelada`, `Finalizada`).
* **Integridad Referencial:** Claves foráneas asociadas a catálogos existentes de materiales, proveedores y almacenes.
