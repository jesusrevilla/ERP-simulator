
# ERP-Simulator
## Primera Entrega de Proyecto

**Alumno:** Juan Pablo Moreno Rivera - 181549  
**Materia:** Sistemas ERP  
**Institución:** Universidad Politécnica de San Luis Potosí  
**Profesor:** Jesús Alberto Revilla

---

# 1. Especificación de Requerimientos y Diseño Funcional ERP

## 1.1 Definición de Requerimientos Funcionales

Los requerimientos funcionales especifican el comportamiento esperado del sistema para administrar y controlar los inventarios físicos y lógicos en los almacenes.

| ID | Requerimiento | Descripción |
|---|---|---|
| RF-01 | Gestión Master de Almacenes | Permitir la creación, actualización y parametrización de almacenes de distintos tipos: general, respaldo, consignación, inspección/calidad y Drop Shipment. |
| RF-02 | Control de Ubicaciones (Bin Locations) | Permitir activar y estructurar ubicaciones físicas dentro de un almacén mediante subniveles como almacén, zona, pasillo, estante y nivel, para rastrear la posición exacta del stock. |
| RF-03 | Entradas por Recepción (Goods Receipt PO) | Registrar entradas de mercancía vinculadas o independientes a órdenes de compra, permitiendo recepciones parciales, cancelaciones, reapertura automática y asignación a ubicaciones. |
| RF-04 | Transferencias Internas de Inventario | Permitir trasladar artículos entre almacenes o entre ubicaciones dentro del mismo almacén. |
| RF-05 | Trazabilidad por Series y Lotes | Gestionar el rastreo obligatorio u opcional de artículos mediante números de serie o lotes desde la entrada hasta la entrega final o procesos de garantías y servicios. |
| RF-06 | Drop Shipment | Permitir despachar mercancía directamente del proveedor al cliente final, registrando la parte financiera y logística sin afectar el stock físico del almacén local. |
| RF-07 | Valoración de Inventario Continuo | Administrar el costo del inventario a nivel global o por almacén utilizando métodos como Promedio Ponderado, FIFO o Costo Estándar. |

## 1.2 Descripción de las Reglas de Negocio

Las reglas de negocio establecen las restricciones y la lógica bajo la cual debe operar el módulo de almacenes dentro del ERP.

- **RN-01. Reapertura Documental por Cancelación:** Si una entrada de mercancías (Goods Receipt PO) es cancelada, la Orden de Compra (Purchase Order) debe reabrir automáticamente su cantidad pendiente, siempre que la opción correspondiente esté habilitada.

- **RN-02. Transferencia a Ubicaciones de Inspección:** Todo producto que sufra daño físico o requiera control de calidad debe trasladarse a un almacén o ubicación bloqueada/de inspección, impidiendo su reserva o venta mientras permanezca en ese estado.

- **RN-03. Consistencia en Almacenes Drop Ship:** Los artículos asignados a un almacén Drop Shipment no generan contabilización en cuentas de stock físico local. Se vincula directamente la Orden de Compra al proveedor con el Pedido de Venta y la dirección de entrega del cliente.

- **RN-04. Inmutabilidad del Método de Valoración:** En un esquema de Inventario Permanente, una vez realizada la primera transacción contabilizada para un artículo o grupo, el método de valoración asignado no puede modificarse si existen registros vinculados.

- **RN-05. Reserva y Selección de Series:** No se puede completar la entrega o despacho de un artículo gestionado por número de serie si la cantidad seleccionada no coincide exactamente con las series asignadas o reservadas en la orden.

## 1.3 Pruebas Unitarias

Las pruebas unitarias verifican el funcionamiento correcto de componentes y funciones individuales dentro del sistema.

| ID | Módulo / Función | Descripción de la Prueba | Resultado Esperado |
|---|---|---|---|
| PU-01 | Master Data de Artículos | Crear un artículo asignando grupo de unidad de medida (UoM) Paper (Caja = 5 Packs) y definiendo almacén por defecto. | El artículo se guarda correctamente con la conversión de unidades y almacenes asignados sin errores de esquema. |
| PU-02 | Form Settings | Habilitar la visibilidad de las columnas Whse, From Bin Location y To Bin Location en la ventana de transferencias. | Las columnas aparecen disponibles para seleccionar ubicaciones de origen y destino. |
| PU-03 | Asignación de Serie | Seleccionar cuatro números de serie mediante Ctrl + Tab o menú contextual. | La ventana de Selección de Números de Serie valida que la cantidad seleccionada coincida con la cantidad requerida. |
| PU-04 | Registro de Ubicación | Probar la entrada de un artículo directamente a la ubicación física 05-A1-S1-L2. | El sistema asigna el código de ubicación al registro del artículo en el almacén 05. |

## 1.4 Pruebas Funcionales

Las pruebas funcionales evalúan flujos de trabajo completos de extremo a extremo (End-to-End), simulando procesos reales de la empresa.

### PF-01. Recepción, Cancelación y Corrección de Mercancía

**Pasos de ejecución:**

1. Crear una Orden de Compra (PO) por 50 unidades de A00001, 100 de A00002 y 25 de A00003.
2. Copiar la PO a una Entrada de Mercancías (Goods Receipt PO).
3. Cancelar la Entrada de Mercancías mediante clic derecho → Cancelar.
4. Verificar el estado de la PO original.
5. Generar una nueva entrada con cantidades reales: 30, 70 y 20 unidades respectivamente.

**Resultado esperado:** La entrada original queda cancelada, la PO se reabre automáticamente a estado Abierto y la nueva entrada registra únicamente el stock corregido en el Almacén 01.

### PF-02. Reubicación por Inspección y Retorno a Almacén

**Pasos de ejecución:**

1. Crear una Transferencia de Inventario del artículo A00002 (cantidad: 1) del Almacén 01 al Almacén 05, ubicación 05-A1-S1-L2.
2. Verificar el informe de auditoría o stock por ubicaciones.
3. Generar una segunda transferencia de retorno del Almacén 05 / Ubicación 05-A1-S1-L2 al Almacén 01.

**Resultado esperado:** El stock disminuye del Almacén 01 y se refleja temporalmente en la ubicación 05-A1-S1-L2 del Almacén 05. Posterior a la inspección, el stock regresa al Almacén 01 sin discrepancias.

### PF-03. Flujo Completo de Drop Shipment

**Pasos de ejecución:**

1. Registrar un Pedido de Venta para el cliente C40000 del artículo I00010 (cantidad: 4), seleccionando el almacén Drop Ship.
2. Ejecutar el Asistente de Confirmación de Aprovisionamiento para generar la PO al proveedor.
3. Facturar al proveedor (A/P Invoice) y facturar al cliente (A/R Invoice).

**Resultado esperado:** La dirección de envío en la PO toma automáticamente la dirección del cliente C40000. Los inventarios físicos locales no sufren entradas ni salidas y el Mapa de Relaciones vincula todo el proceso comercial y financiero.

## 1.5 Integridad de los Datos

La integridad de los datos garantiza la consistencia, exactitud y validez de la información a lo largo de todas las operaciones del ERP.

- **Integridad Referencial de Tablas Base:** Todos los registros de movimientos en el almacén (entradas, salidas y transferencias) deben vincularse a un código de artículo válido existente en los datos maestros (OITM) y a un código de almacén registrado (OWHS).

- **Consistencia de Inventario Físico vs. Disponible:** El sistema mantiene el cálculo en tiempo real de la ecuación:

  `Disponible = En Stock + Solicitado (PO) - Comprometido (Sales Order)`

  Ninguna transacción de salida puede dejar el inventario físico en valores negativos si la configuración global del ERP prohíbe el stock negativo.

- **Trazabilidad en el Mapa de Relaciones:** Toda transacción derivada de otra conserva la clave primaria/foránea del documento origen, garantizando la trazabilidad histórica de los movimientos.

- **Balance de Cuentas Contables (Perpetual Inventory Audit Trail):** Por cada movimiento físico de entrada o salida de almacén, el ERP genera automáticamente el asiento contable correspondiente en el libro mayor, asegurando que el valor monetario en finanzas coincida con la valoración física del inventario.

## 1.6 Matriz de Trazabilidad de Requerimientos (RTM)

Relaciona los requerimientos funcionales directamente con sus casos de prueba y reglas de negocio asociadas.

| ID Requerimiento | Descripción | Regla de Negocio | Caso de Prueba |
|---|---|---|---|
| RF-02 | Control de Ubicaciones (Bin Locations) | RN-02 | PU-04, PF-02 |
| RF-03 | Entrada por Recepción de Compras | RN-01 | PU-02, PF-01 |
| RF-06 | Proceso de Drop Shipment | RN-03 | PF-03 |
| RF-07 | Valoración de Inventario Continuo | RN-04 | PU-01 |

## 1.7 Arquitectura de Integración con el Módulo MRP

El módulo de almacenes interactúa directamente con el motor de planificación MRP (Material Requirements Planning).

- **Entradas de Datos al MRP:** El motor MRP toma el inventario inicial existente en los almacenes seleccionados en el escenario de planificación.

- **Consideración de Ubicaciones y Almacenes Excluidos:** Los almacenes de calidad/inspección o definidos como no disponibles para MRP son ignorados por el algoritmo para evitar falsas disponibilidades de stock.

- **Generación de Órdenes Sugeridas:** En función del stock mínimo por almacén y los tiempos de entrega (Lead Time) configurados en los datos maestros del artículo, el MRP genera recomendaciones de compra u órdenes de transferencia entre almacenes.

---

# 2. Diagrama de Procesos - BPMN

El siguiente diagrama representa gráficamente los principales procesos del módulo de gestión de almacenes del ERP-Simulator, considerando sus requerimientos funcionales y reglas de negocio.

```mermaid
flowchart TD

    INICIO((Inicio))
    OPERACION{"¿Qué operación se realizará?"}

    INICIO --> OPERACION

    subgraph P1["1. RECEPCIÓN DE MERCANCÍAS"]
        direction TB
        A1["Consultar Orden de Compra (PO)"]
        A2["Crear Entrada de Mercancías (Goods Receipt PO)"]
        A3["Registrar cantidades recibidas"]
        A4["Asignar ubicación de recepción"]
        A5{"¿Se cancela la entrada?"}
        A6["Cancelar documento de entrada"]
        A7{"¿Reapertura automática habilitada?"}
        A8["Reabrir Orden de Compra"]
        A9["Generar nueva entrada con cantidades reales"]
        A10["Actualizar inventario del almacén"]
        A11((Fin de recepción))

        A1 --> A2 --> A3 --> A4 --> A5
        A5 -- "Sí" --> A6 --> A7
        A7 -- "Sí" --> A8 --> A9 --> A10
        A7 -- "No" --> A9
        A5 -- "No" --> A10
        A10 --> A11
    end

    subgraph P2["2. TRANSFERENCIAS E INSPECCIÓN"]
        direction TB
        B1["Identificar artículo en almacén"]
        B2{"¿Requiere inspección o tiene daños?"}
        B3["Crear transferencia de inventario"]
        B4["Trasladar al almacén de inspección 05"]
        B5["Asignar ubicación 05-A1-S1-L2"]
        B6["Bloquear disponibilidad para reserva y venta"]
        B7["Realizar inspección de calidad"]
        B8["Crear transferencia de retorno"]
        B9["Regresar artículo al almacén 01"]
        B10["Actualizar existencias y ubicaciones"]
        B11((Fin de transferencia))

        B1 --> B2
        B2 -- "Sí" --> B3 --> B4 --> B5 --> B6 --> B7 --> B8 --> B9 --> B10
        B2 -- "No" --> B11
        B10 --> B11
    end

    subgraph P3["3. PROCESO DROP SHIPMENT"]
        direction TB
        C1["Registrar Pedido de Venta"]
        C2["Seleccionar almacén Drop Ship"]
        C3["Ejecutar Asistente de Confirmación de Aprovisionamiento"]
        C4["Generar Orden de Compra al proveedor"]
        C5["Vincular dirección de entrega del cliente"]
        C6["Proveedor despacha directamente al cliente"]
        C7["Registrar factura del proveedor (A/P Invoice)"]
        C8["Registrar factura del cliente (A/R Invoice)"]
        C9["Actualizar mapa de relaciones comerciales y financieras"]
        C10["No modificar stock físico local"]
        C11((Fin de Drop Shipment))

        C1 --> C2 --> C3 --> C4 --> C5 --> C6
        C6 --> C7 --> C8 --> C9 --> C10 --> C11
    end

    subgraph P4["4. ADMINISTRACIÓN Y CONTROL DE INVENTARIO"]
        direction TB
        D1["Configurar almacenes y tipos"]
        D2["Definir ubicaciones físicas (Bin Locations)"]
        D3["Configurar seguimiento por series o lotes"]
        D4["Seleccionar método de valoración: FIFO, Promedio o Estándar"]
        D5{"¿Existen transacciones contabilizadas?"}
        D6["Mantener método de valoración asignado"]
        D7["Permitir configuración del método"]
        D8["Registrar movimientos de inventario"]
        D9["Validar existencias y disponibilidad"]
        D10{"¿Se requiere planificación MRP?"}
        D11["Consultar inventario de almacenes seleccionados"]
        D12["Excluir almacenes de inspección o no disponibles"]
        D13["Evaluar stock mínimo y tiempos de entrega"]
        D14["Generar sugerencias de compra o transferencia"]
        D15((Fin de administración))

        D1 --> D2 --> D3 --> D4 --> D5
        D5 -- "Sí" --> D6 --> D8
        D5 -- "No" --> D7 --> D8
        D8 --> D9 --> D10
        D10 -- "Sí" --> D11 --> D12 --> D13 --> D14 --> D15
        D10 -- "No" --> D15
    end

    OPERACION -- "Recepción" --> A1
    OPERACION -- "Transferencia" --> B1
    OPERACION -- "Drop Shipment" --> C1
    OPERACION -- "Administración / MRP" --> D1

    classDef inicio fill:#d5f5e3,stroke:#239b56,color:#145a32
    classDef fin fill:#d5f5e3,stroke:#239b56,color:#145a32
    classDef decision fill:#fcf3cf,stroke:#d4ac0d,color:#7d6608
    classDef actividad fill:#d6eaf8,stroke:#2874a6,color:#154360

    class INICIO inicio
    class A11,B11,C11,D15 fin
    class OPERACION,A5,A7,B2,D5,D10 decision
    class A1,A2,A3,A4,A6,A8,A9,A10,B1,B3,B4,B5,B6,B7,B8,B9,B10,C1,C2,C3,C4,C5,C6,C7,C8,C9,C10,D1,D2,D3,D4,D6,D7,D8,D9,D11,D12,D13,D14 actividad
```

---

**Fin del documento.**
