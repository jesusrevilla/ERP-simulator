# Análisis del proceso empresarial - BOM

**Matrícula:** 179761 | **Issues:** #244 

##  Contexto

**TechAssembly S.A.** es una organización dedicada al ensamble de hardware y equipos de cómputo de alto rendimiento. Como parte de su transformación digital, la empresa está implementando un sistema **MRP (Material Requirements Planning)**.

El módulo de **Bill of Materials (BOM)** define la receta exacta de componentes necesarios para ensamblar cada equipo. La exactitud de esta estructura determina directamente la precisión de las compras a proveedores, el cálculo de costos de manufactura (*Cost Roll-up*) y el surtimiento de materiales en planta.

---

## Problemática a Solucionar

Durante la creación o edición de una BOM, el sistema actual carece de validaciones de unicidad por nivel jerárquico, permitiendo que un analista de ingeniería registre **dos o más veces el mismo componente bajo un mismo producto padre**.

Esta duplicidad resulta en fallos operativos como:

1.**Explosión MRP inflada:** Al recibir un pedido, el MRP calcula una demanda bruta detonando órdenes de compra excedentes e inmovilizando capital.
2.**Distorsión del Cost Roll-up:** El costo estándar de producción resulta elevado y erróneo.
* **Errores en piso (*Picking List*):** Almacén recibe y surte componentes duplicados a la línea de ensamble.

---

## Proceso Empresarial: Gestión de BOM 

El proceso empresarial abarca desde la definición del BOM hasta la explosión de materiales en el MRP, operando en cuatro etapas:

1. **Captura y Estructuración:**
El analista selecciona el producto padre y comienza a asociar los componentes requeridos desde el Maestro de Artículos (*Item Master*), indicando cantidad y unidad de medida.
2. **Validación de Integridad y Control de Duplicidad:**
Antes de persistir cada línea, el sistema valida la existencia del componente, que la cantidad sea mayor a cero y verifica la llave compuesta `(ID_Padre, ID_Componente, Nivel)`:
* Si el componente **no existe** en ese nivel, se inserta normalmente.
* Si el componente **ya existe** el sistema intercepta la operación: **bloquea la fila duplicada** o **consolida automáticamente las cantidades** en un único registro ($\text{Cantidad Total} = \text{Cantidad Previa} + \text{Cantidad Nueva}$), registrando el evento


3. **Cálculo de Costos y Liberación:**
Con la estructura libre de duplicados, el sistema ejecuta el *Cost Roll-up* sumando los precios unitarios de los componentes validados y marca la BOM como *Activa*.
4. **Explosión de Materiales y Abastecimiento (Planeación MRP y Almacén):**
Al ingresar una orden de venta el motor MRP recorre el grafo en Neo4j, multiplica la demanda por las cantidades únicas de la BOM, contrasta contra el inventario disponible y genera órdenes de compra netas o listas de surtimiento (*Picking Lists*) exactas para producción.

---

### 4. Diagramas BPMN del Proceso Empresarial

#### A. Diagrama BPMN del Proceso Actual (Con Falla por Duplicidad)

```mermaid
flowchart TD
    classDef startEvent fill:#85e3b5,stroke:#2e7d32,stroke-width:2px;
    classDef endEvent fill:#ffab91,stroke:#c62828,stroke-width:2px;
    classDef task fill:#e3f2fd,stroke:#1565c0,stroke-width:1.5px;
    classDef errorTask fill:#ffe0b2,stroke:#ef6c00,stroke-width:1.5px;

    subgraph Pool_AsIs ["Proceso Actual (As-Is) - TechAssembly S.A."]
        direction TB
        subgraph Lane_Ing ["Ingeniería de Producto"]
            S1(["Inicio: Solicitud de nueva BOM Gaming PC"]):::startEvent --> T1["Seleccionar componentes del catálogo"]:::task
            T1 --> T2["Registrar línea 1: CPU Ryzen 7 - Cant: 1"]:::task
            T2 --> T3["Registrar por error línea 2: CPU Ryzen 7 - Cant: 1"]:::errorTask
            T3 --> T4["Guardar BOM sin validación de unicidad"]:::errorTask
        end

        subgraph Lane_MRP ["Planeación MRP y Compras"]
            T4 --> T5["Ejecutar explosión MRP para pedido de 50 PCs"]:::task
            T5 --> T6["Calcular requerimiento inflado: 100 CPU Ryzen 7"]:::errorTask
            T6 --> T7["Emitir orden de compra con sobrecosto del 100% en CPU"]:::errorTask
        end

        subgraph Lane_Prod ["Almacén y Producción"]
            T7 --> T8["Generar Picking List con líneas repetidas"]:::task
            T8 --> T9["Detectar sobrante físico en línea de ensamble"]:::errorTask
            T9 --> E1(["Fin: Paro de línea y reproceso manual"]):::endEvent
        end
    end
```

#### B. Diagrama BPMN del Proceso Mejorado (Detección / Consolidación y MRP)

```mermaid
flowchart TD
    classDef startEvent fill:#85e3b5,stroke:#2e7d32,stroke-width:2px;
    classDef endEvent fill:#ffab91,stroke:#c62828,stroke-width:2px;
    classDef task fill:#e3f2fd,stroke:#1565c0,stroke-width:1.5px;
    classDef gateway fill:#fff59d,stroke:#f57f17,stroke-width:1.5px;
    classDef sysTask fill:#ede7f6,stroke:#4527a0,stroke-width:1.5px;

    subgraph Pool_ToBe ["Proceso Optimizado (To-Be) - Arquitectura Políglota ERP"]
        direction TB
        subgraph Lane_Ing2 ["Ingeniería de Producto"]
            S2(["Inicio: Crear/Editar BOM Gaming PC"]):::startEvent --> UI1["Ingresar componente ej. CPU Ryzen 7 y cantidad"]:::task
        end

        subgraph Lane_ERP ["Motor ERP (PostgreSQL + Neo4j + MongoDB)"]
            UI1 --> V1["Validar existencia en Item Master y Cantidad > 0"]:::sysTask
            V1 --> G1{"¿Componente ya existe en el mismo nivel?"}:::gateway
            
            G1 -- "No (Registro Único)" --> DB1["Insertar línea única en PostgreSQL y arista MERGE en Neo4j"]:::sysTask
            
            G1 -- "Sí (Duplicidad Detectada)" --> G2{"¿Política configurada?"}:::gateway
            G2 -- "Bloqueo Estricto" --> ERR1["Rechazar inserción y notificar duplicidad al usuario"]:::sysTask
            ERR1 --> UI1
            
            G2 -- "Consolidación Automática" --> DB2["Sumar cantidades en registro existente PostgreSQL/Neo4j"]:::sysTask
            DB2 --> AUD1["Registrar evento de consolidación en MongoDB"]:::sysTask
            
            DB1 --> CR1["Ejecutar Cost Roll-up automático y activar BOM"]:::sysTask
            AUD1 --> CR1
        end

        subgraph Lane_MRP2 ["Planeación MRP y Almacén"]
            CR1 --> MRP1["Recibir pedido de cliente y ejecutar explosión MRP"]:::task
            MRP1 --> MRP2["Calcular requerimientos netos exactos sin duplicados"]:::sysTask
            MRP2 --> ALM1["Emitir Picking List consolidada y órdenes de compra óptimas"]:::task
            ALM1 --> E2(["Fin: Ensamble fluido y sin sobrecostos"]):::endEvent
        end
    end

```

---

### Objetivo

Implementar un control integral de validación y gobierno de datos dentro del módulo **Bill of Materials (BOM)** del ERP de **TechAssembly S.A.** que **erradique la duplicidad de componentes por nivel jerárquico** mediante detección temprana o consolidación automática de cantidades. Con ello, se busca asegurar la integridad de la estructura de fabricación, garantizar la exactitud en el cálculo de costos (*Cost Roll-up*) y optimizar la explosión de requerimientos del **MRP**, eliminando compras excedentes, paros en la línea de ensamble y discrepancias en el inventario.
