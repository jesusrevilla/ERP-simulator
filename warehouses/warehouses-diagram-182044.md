Requerimientos Warehouses ERP-simulator 
#1. Definición de Requerimientos Funcionales 
(RF - MRP y Almacén) 

RF-01 (Inclusión/Exclusión de Almacenes en MRP). El sistema debe permitir 
definir a nivel de cada almacén si su inventario existente, oferta (suministros) y 
demanda serán considerados dentro del cálculo del Asistente de MRP. 

RF-02 (Cálculo de Consolidación y Almacén Individual). El sistema debe 
permitir ejecutar el cálculo de MRP consolidando todos los almacenes de la 
empresa o ejecutándose de manera independiente para cada almacén 
individual (Run By Warehouse). 
inventario 

RF-03 (Consumo de Inventario Inicial por Almacén). El sistema debe calcular el proyectado periódicamente (diario/semanal/mensual) considerando el stock inicial real de cada almacén seleccionado. 

RF-04 (Asignación Automática de Almacén en Recomendaciones). El sistema 
debe generar las recomendaciones de órdenes de compra o producción 
asignando automáticamente el almacén predeterminado definido en los datos 
maestros del artículo o el almacén donde se originó la demanda. 

RF-05 (Integración de Solicitudes de Traslado en MRP). El sistema debe incluir 
las solicitudes de transferencia de inventario (Inventory Transfer Requests) 
entre almacenes como fuente de demanda para el almacén origen y fuente de 
oferta para el almacén destino. 

#2. Descripción de las Reglas de Negocio (RN) 
RN-01 (Almacenes Drop Ship y Consignación). Por regla general de MRP, los 
almacenes marcados como Drop Ship o Consignación no deben ser 
considerados dentro de la corrida estándar de planificación de requerimientos 
de la planta principal, a menos que el usuario los seleccione explícitamente en 
el asistente. 
RN-02 (Restricción de Stock Inactivo o Dañado). Si un artículo se encuentra en 
un almacén configurado como "No Disponible" o "Stock Dañado/Calidad", el 
MRP no debe considerar esa cantidad como inventario disponible para cubrir 
demanda. 
RN-03 (Consideración del Lead Time de Transferencia). Cuando la oferta de 
un almacén dependa de un traslado desde otro almacén de la misma empresa, 
el cálculo del MRP debe añadir el tiempo de tránsito/logística (Lead Time) para 
calcular la fecha de liberación recomendada. 
RN-04 (Prioridad de Surtido por Almacén Predeterminado). Al generarse una 
recomendación de pedido basada en demanda de varios almacenes 
consolidada, la sugerencia de compra debe dirigirse prioritariamente al 
almacén definido como receptor general en los datos maestros del ítem. 

#3. Pruebas Unitarias (PU) 
PU-01 (Validación de Checkbox). Verificar que el campo "Incluir en MRP" del 
maestro de almacenes modifique correctamente la bandera lógica en la base 
de datos. 
PU-02 (Cálculo de Inventario Proyectado en MRP). Verificar que la lógica de la 
matriz del reporte aplique correctamente: 
𝐼𝑛𝑣𝑒𝑛𝑡𝑎𝑟𝑖𝑜𝐹𝑖𝑛𝑎𝑙 = 𝐼𝑛𝑣𝑒𝑛𝑡𝑎𝑟𝑖𝑜𝐼𝑛𝑖𝑐𝑖𝑎𝑙 + 𝑂𝑓𝑒𝑟𝑡𝑎(𝑆𝑢𝑝𝑝𝑙𝑦) − 𝐷𝑒𝑚𝑎𝑛𝑑𝑎(𝐷𝑒𝑚𝑎𝑛𝑑)
PU-03 (Filtrado de Almacenes en Step 4 del MRP Wizard). Verificar que si se 
desmarca un almacén en el Paso 4 del Asistente de MRP, las cantidades de 
inventario de ese almacén no aparezcan en la pestaña Report del Paso 6. 

#4. Pruebas Funcionales (PF) 
PF-01 (MRP Ejecutado por Empresa o por Almacén): 
1. Configurar 10 unidades de demanda en el Almacén 01 y 15 
unidades de inventario en el Almacén 02. 
2. Ejecutar MRP seleccionando la opción Company (Consolidado). 
3. Criterio de Aceptación: El MRP determina que hay cobertura total 
y no genera recomendación de compra. 
4. Ejecutar el MRP seleccionando Warehouse (Individual). 
5. Criterio de Aceptación: El MRP genera una recomendación de 
compra por 10 unidades exclusivamente para el Almacén 01. 
PF-02 (Recomendación de Compra con Destino a Almacén Específico): 
1. Correr el escenario seleccionando el Almacén 01 (General 
Warehouse). 
2. Analizar las recomendaciones generadas en el Paso 6 y pasar a 
Order Recommendation. 
3. Criterio de Aceptación: La orden de compra generada asigna 
automáticamente el código de almacén 01 en las líneas del 
documento respaldatorio.

#5. Integridad de los Datos 
Cada línea de resultado de MRP (MRP_Results) debe estar vinculada 
obligatoriamente a un código de artículo válido (ItemCode) y a un código de 
almacén existente (WhsCode). 
Los movimientos de almacén realizados (entradas, salidas, transferencias) 
entre el diseño del escenario y la ejecución final del MRP deben reflejarse de 
forma consistente si la corrida vuelve a ejecutarse. 
Los cálculos e hipótesis de almacenes de un escenario en modo Simulación no 
deben alterar ni modificar las tablas reales de stock físico ni las órdenes 
activas en la base de datos.
```mermaid
flowchart TD
    classDef startEvent fill:#d4edda,stroke:#28a745,stroke-width:2px,color:#155724;
    classDef endEvent fill:#f8d7da,stroke:#dc3545,stroke-width:2px,color:#721c24;
    classDef task fill:#e2e3e5,stroke:#383d41,stroke-width:1px,color:#383d41;
    classDef gateway fill:#fff3cd,stroke:#ffc107,stroke-width:2px,color:#856404;
    classDef subprocess fill:#d1ecf1,stroke:#17a2b8,stroke-width:1px,color:#0c5460;

    Start([Inicio: Necesidad de Planificación MRP]):::startEvent --> Sub1

    subgraph Sub1 [1. Prerrequisitos y Datos Maestros]
        direction TB
        T1_1[Configurar Artículo]:::task --> T1_2[Configurar Proveedor / Cliente ]:::task
    end

    Sub1 --> Sub2

    subgraph Sub2 [2. Demanda Inicial e Inventarios]
        direction TB
        T2_1[Registrar Orden de Compra]:::task --> T2_2[Recepción de Mercancía Goods Receipt PO]:::task
        T2_2 --> T2_3[Crear Orden de Venta Sales Order]:::task
        T2_3 --> T2_4[Verificar Estado de Inventario]:::task
    end

    Sub2 --> Sub3

    subgraph Sub3 [3. Pronóstico de Ventas Forecast]
        direction TB
        T3_1[Configurar Código y Fechas]:::task --> T3_2[Generar Pronóstico por Historial de Ventas]:::task
        T3_2 --> T3_3[Ajustar Cantidades Mensuales]:::task
    end

    Sub3 --> Sub4

    subgraph Sub4 [4. Asistente de MRP - MRP Wizard]
        direction TB
        T4_1[Paso 1: Escenario]:::task --> T4_2[Paso 2: Detalles y Horizonte de Fechas]:::task
        T4_2 --> T4_3[Paso 3: Selección de Artículo ]:::task
        T4_3 --> T4_4[Paso 4: Selección de Almacenes Consolidado vs. Individual]:::task
        T4_4 --> T4_5[Paso 5: Fuentes de Datos y Forecast PSF1]:::task
    end

    Sub4 --> Sub5

    subgraph Sub5 [5. Ejecución y Análisis de Resultados]
        direction TB
        T5_1[Ejecutar Cálculo del MRP]:::task --> T5_2[Analizar Pestaña Reporte: Stock Inicial + Oferta - Demanda]:::task
        T5_2 --> T5_3[Revisar Pestaña Recomendaciones]:::task
    end

    Sub5 --> G1{¿Se aprueban las Recomendaciones?}:::gateway

    G1 -- No --> T4_1
    G1 -- Sí --> Sub6

    subgraph Sub6 [6. Recomendación de Pedido Order Recommendation]
        direction TB
        T6_1[Configurar Criterios de Selección]:::task --> T6_2[Seleccionar Órdenes de Compra a Generar]:::task
        T6_2 --> T6_3[Procesar y Actualizar Recomendaciones]:::task
    end

    Sub6 --> End([Fin: Generación Automática de Órdenes de Compra]):::endEvent```
