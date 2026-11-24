# Especificación Técnica y Funcional: Módulo ERP (Recibos y Entregas)

## 1. Definición de Requerimientos Funcionales
Los requerimientos funcionales describen los comportamientos específicos del sistema, interfaces y reglas operativas que el módulo debe ejecutar para gestionar el flujo físico y digital de mercancías.

### Módulo de Recibos (Logística de Entrada / Inbound)
- **RF-01: Recepción basada en Órdenes de Compra (OC):** El sistema debe permitir consultar y seleccionar una Orden de Compra aprobada para importar automáticamente sus líneas, artículos y cantidades esperadas al documento de entrada (Goods Receipt PO).
- **RF-02: Registro de datos de trazabilidad obligatorios:** El sistema debe habilitar campos dinámicos para capturar Números de Lote, Números de Serie y Fechas de Caducidad en tiempo de recepción para artículos que lo requieran por configuración de maestro de materiales.
- **RF-03: Sugerencia y asignación de ubicación (Putaway):** El sistema debe proponer automáticamente una ubicación de almacenamiento (Bin Location) en el almacén basada en la zona de rotación del producto, peso y disponibilidad de espacio.
- **RF-04: Cierre y actualización de stock:** Al confirmar el recibo, el sistema debe generar de manera automática un asiento de incremento de inventario físico y actualizar el estatus de la Orden de Compra (parcial o totalmente recibida).

### Módulo de Entregas (Logística de Salida / Outbound)
- **RF-05: Procesamiento de Pedidos de Venta:** El sistema debe capturar los requerimientos de salida originados por pedidos de clientes confirmados, filtrándolos por fecha de entrega requerida y prioridad de ruta.
- **RF-06: Asignación y reserva de inventario (Allocation/Picking):** El sistema debe bloquear o reservar físicamente las cantidades en stock del almacén correspondiente para evitar que se asignen a múltiples pedidos simultáneos.
- **RF-07: Generación de documentos de expedición:** El sistema debe emitir la lista de empaque (Packing List), la etiqueta de bulto y la guía de embarque asociada al transportista.
- **RF-08: Confirmación de salida de mercancía (Goods Issue):** Al momento del despacho físico en andén, el sistema debe descontar de forma definitiva el inventario y generar el asiento contable de salida.

---

## 2. Descripción de Reglas de Negocio
Las reglas de negocio imponen restricciones de validación que el motor del ERP debe hacer cumplir de forma estricta para garantizar la coherencia operativa y financiera.

- **RN-01: Restricción absoluta de Stock Negativo:** El ERP no permitirá bajo ninguna circunstancia confirmar una entrega si el stock disponible en la ubicación de origen es menor a la cantidad solicitada, a menos que exista un parámetro de excepción con rol gerencial.
- **RN-02: Bloqueo por Caducidad o Lotes Cuarentena:** El sistema prohibirá la selección y despacho de artículos cuyos lotes se encuentren vencidos o marcados con estatus de "Inspección de Calidad" o "Bloqueado".
- **RN-03: Tolerancia en Discrepancias de Recepción:** Si la cantidad física recibida excede el porcentaje de tolerancia superior permitido respecto a la Orden de Compra (ej. más del 5%), el sistema bloqueará la contabilización y requerirá la aprobación del departamento de compras o un addendum a la OC.
- **RN-04: Inmutabilidad de Documentos Contabilizados:** Una vez que un documento de recibo o entrega pasa al estatus de "Contabilizado/Cerrado", sus líneas de artículos, cantidades y costos unitarios se vuelven inmutables; cualquier corrección requerirá un documento compensatorio (Nota de Devolución o Entrada de Ajuste).

---

## 3. Pruebas Unitarias (Unit Testing)
Las pruebas unitarias validan la lógica de código de componentes y funciones aisladas del módulo.

- **UT-01: Validación de función de cálculo de stock disponible**
  - **Entrada:** `almacen_id = "A01"`, `articulo_id = "PROD-001"`, `cantidad_solicitada = 150`, `stock_actual = 100`.
  - **Resultado esperado:** La función `verificar_disponibilidad()` debe retornar un booleano `False` acompañado de un código de error por stock insuficiente.
- **UT-02: Validación del formato de nomenclatura de lotes**
  - **Entrada:** Cadena de texto de lote ingresada `L-2026-11-04-X`.
  - **Resultado esperado:** La expresión regular (Regex) de validación debe retornar `True` si cumple con el estándar de trazabilidad de la planta.
- **UT-03: Cálculo de peso bruto volumétrico para embarque**
  - **Entrada:** Listado de ítems de una entrega con sus respectivos pesos unitarios y cantidades.
  - **Resultado esperado:** La función matemática debe arrojar la sumatoria exacta con dos decimales para los reportes de la guía de transporte.

---

## 4. Pruebas Funcionales (Functional Testing)
Pruebas de extremo a extremo (End-to-End) que simulan la interacción real del operador o supervisor en el sistema.

- **TF-01: Flujo Completo de Recepción de Proveedores (Inbound)**
  1. **Acción:** Crear y aprobar una Orden de Compra de 50 piezas de un componente electrónico con número de serie obligatorio.
  2. **Acción:** Registrar la entrada de mercancía en el módulo de recibos capturando 50 números de serie individuales.
  3. **Verificación:** Comprobar que el inventario del almacén aumentó en 50 unidades, que la Orden de Compra figura como "Cerrada" y que los números de serie se encuentran consultables en el maestro de trazabilidad.
- **TF-02: Flujo Completo de Despacho de Pedidos (Outbound)**
  1. **Acción:** Generar un pedido de venta por 20 unidades de producto terminado.
  2. **Acción:** Ejecutar el proceso de asignación (picking) y confirmar la salida en andén.
  3. **Verificación:** Validar que el stock disponible en el sistema disminuyó exactamente en 20 unidades y que se generó correctamente la lista de empaque.
- **TF-03: Prueba de Excepción Operativa por Diferencia en Recepción**
  1. **Acción:** Intentar recibir 120 piezas contra una Orden de Compra de 100 piezas (excediendo el umbral permitido).
  2. **Verificación:** El sistema debe desplegar una alerta visual de bloqueo y rechazar la contabilización definitiva del documento.

---

## 5. Integridad de los Datos
La integridad asegura que los datos logísticos no sufran anomalías, duplicidades o estados inconsistentes ante fallas del sistema o accesos concurrentes.

- **DI-01: Control de Concurrencia y Bloqueo de Filas (Row-Level Locking):** El motor de base de datos del ERP debe implementar bloqueos de exclusividad a nivel de registro en las tablas de inventario cuando dos operadores intenten procesar recibos o entregas sobre el mismo almacén o lote de productos de forma simultánea, evitando condiciones de carrera (race conditions).
- **DI-02: Transacciones Atómicas (ACID) en Contabilización:** Cada operación de recibo o entrega debe envolverse en una transacción ACID estricta. Si al confirmar una entrega ocurre un fallo en la actualización del saldo de inventario o en la inserción del asiento contable, toda la transacción debe revertirse (Rollback) para evitar stock fantasma o registros huérfanos.
- **DI-03: Integridad Referencial Estricta (Foreign Keys):** Garantizar mediante restricciones de base de datos que una línea de detalle de recibo o entrega no pueda existir de manera independiente sin estar atada a una cabecera de documento válida y a un artículo existente en el catálogo maestro.

---

## 6. Diagrama de Procesos (Mermaid)

```mermaid
flowchart TD
    %% Estilos de Nodos BPMN
    classDef startEvent fill:#85e3a5,stroke:#2e7d32,stroke-width:2px,rx:15,ry:15;
    classDef endEvent fill:#f8bbd0,stroke:#c2185b,stroke-width:3px,rx:15,ry:15;
    classDef task fill:#e3f2fd,stroke:#1565c0,stroke-width:1px,rx:5,ry:5;
    classDef gateway fill:#fff9c4,stroke:#fbc02d,stroke-width:2px;

    subgraph ERP_Module ["📦 Módulo ERP: Recibos y Entregas"]
        
        subgraph Sub_Inbound ["📥 Logística de Entrada (Recibos)"]
            Start_Inbound((🏁 Inicio)):::startEvent
            RF01["📋 RF-01: Consultar Orden de Compra"]:::task
            RF02["🏷️ RF-02: Capturar Lote y Serie"]:::task
            GW_RN03{"⚖️ RN-03: ¿Excede tolerancia (> 5%)?"}:::gateway
            Block_Recibo["🚫 Bloquear recepción"]:::task
            End_Inbound_Error((🛑 Fin Bloqueado)):::endEvent
            RF03["📍 RF-03: Asignar Ubicación"]:::task
            
            subgraph TX_Inbound ["🔒 Transacción ACID (DI-02)"]
                RF04["💾 RF-04: Incrementar inventario y cerrar OC"]:::task
            end
            
            End_Inbound((🏁 Fin Recibido)):::endEvent
            
            Start_Inbound --> RF01 --> RF02 --> GW_RN03
            GW_RN03 -->|s29| Block_Recibo --> End_Inbound_Error
            GW_RN03 -->|s30| RF03 --> RF04 --> End_Inbound
        end

        subgraph Sub_Outbound ["📤 Logística de Salida (Entregas)"]
            Start_Outbound((🏁 Inicio)):::startEvent
            RF05["📑 RF-05: Procesar Pedido de Venta"]:::task
            GW_RN02{"🔍 RN-02: ¿Lote Vencido/Bloqueado?"}:::gateway
            Block_Lote["🚫 Bloquear artículo"]:::task
            End_Outbound_Lote((🛑 Fin Detenido)):::endEvent
            GW_RN01{"📦 RN-01: ¿Stock Insuficiente?"}:::gateway
            GW_Gerencial{"👔 ¿Autorización gerencial?"}:::gateway
            Block_Stock["❌ Denegar salida"]:::task
            End_Outbound_Stock((🛑 Fin Bloqueado)):::endEvent
            RF06["🗂️ RF-06: Picking (Bloqueo DI-01)"]:::task
            RF07["📦 RF-07: Emitir Packing List"]:::task
            
            subgraph TX_Outbound ["🔒 Transacción ACID (DI-02)"]
                RF08["💾 RF-08: Descontar stock y contabilizar"]:::task
            end
            
            End_Outbound((🏁 Fin Despachado)):::endEvent
            
            Start_Outbound --> RF05 --> GW_RN02
            GW_RN02 -->|s31| Block_Lote --> End_Outbound_Lote
            GW_RN02 -->|s32| GW_RN01
            GW_RN01 -->|s33| GW_Gerencial
            GW_Gerencial -->|s34| Block_Stock --> End_Outbound_Stock
            GW_Gerencial -->|s35| RF06
            GW_RN01 -->|s36| RF06
            RF06 --> RF07 --> RF08 --> End_Outbound
        end
    end
