# Propuesta de Agente Inteligente: FinControl AI (Módulo A/R y A/P)

## 1. Visión General
Basado en los requerimientos del Mini ERP y la integración con el MRP, se propone el desarrollo de **FinControl AI**, un agente inteligente diseñado para auditar, conciliar y predecir el comportamiento financiero dentro de los módulos de Cuentas por Cobrar (A/R) y Cuentas por Pagar (A/P). 

El objetivo principal de este agente es garantizar el cumplimiento estricto de las reglas de negocio (como el *3-way match* y los límites de crédito) de manera automatizada, reduciendo la carga manual y previniendo errores de integridad de datos.

## 2. Alcance del Agente

El agente actuará como un "Copiloto Financiero" autónomo con dos frentes principales:

### Frente A/P (Cuentas por Pagar) - Conciliador Inteligente
*   **Automatización del 3-Way Match (RF-04, RN-03, RN-04):** Al recibir una factura de proveedor (ya sea digitalizada o en XML), el agente extraerá los datos y los cruzará automáticamente contra la Orden de Compra (`OrdenesCompra`) y el registro de Recepción de Mercancía.
*   **Gestión de Tolerancias (PU-04, PU-05):** Evaluará las diferencias de precio o cantidad. Si la variación está dentro del margen de tolerancia dictado por Finanzas, el agente aprobará el documento para su pago. Si lo excede, bloqueará el pago y notificará a un administrador.
*   **Detección de Anomalías:** Identificará patrones inusuales en las facturas de proveedores, como precios significativamente distintos a los pactados en compras anteriores.

### Frente A/R (Cuentas por Cobrar) - Evaluador de Riesgo
*   **Gestión Dinámica de Crédito (RF-08, RN-05):** Analizará en tiempo real el saldo vencido y el límite de crédito cada vez que entre un nuevo pedido de venta. 
*   **Predicción de Flujo de Efectivo y Cobranza:** Basado en el historial de las `condiciones_pago` (contado, 15, 30, 60 días) y los hábitos de pago de cada cliente, predecirá qué facturas tienen riesgo de caer en morosidad.
*   **Aplicación Inteligente de Pagos:** Al registrar un cobro, si el cliente tiene múltiples facturas abiertas, el agente sugerirá la aplicación óptima del pago (por ejemplo, priorizando las facturas más antiguas o las que están a punto de vencer), respetando que nunca exceda el saldo de la factura (RN-07).

## 3. Tecnologías a Emplear

Para garantizar el cumplimiento de los requerimientos técnicos y de rendimiento (como respuestas en < 2s), se proponen las siguientes tecnologías:

*   **Framework de Agentes:** **LangChain** o **Microsoft AutoGen** para orquestar la toma de decisiones lógicas del agente (conectar el modelo de lenguaje con la base de datos SQL).
*   **Modelos de Procesamiento (LLM / NLP):** Modelos como OpenAI (GPT-4o) o Google Gemini para el análisis de texto no estructurado (ej. extracción de datos de facturas PDF) y para consultas en lenguaje natural ("¿Cuáles clientes excedieron su crédito hoy?").
*   **OCR (Reconocimiento Óptico de Caracteres):** AWS Textract o Google Document AI para digitalizar facturas físicas de proveedores antes de que el agente haga el *3-way match*.
*   **Base de Datos Relacional:** **PostgreSQL**. Se utilizarán consultas seguras y bloqueos de fila (`SELECT ... FOR UPDATE`) para garantizar la concurrencia y los principios ACID requeridos al aplicar pagos.
*   **Machine Learning para Riesgo (Opcional):** Scikit-learn (Python) para entrenar un modelo de clasificación que asigne un "Score de Riesgo de Impago" a los clientes basado en su historial en el ERP.

## 4. Implementación Teórica y Arquitectura

La implementación del agente interactuará directamente con las capas de lógica de negocio y persistencia del ERP.

### Flujo Teórico: Caso de Uso A/P (Recepción y Conciliación)
1. **Entrada de Datos:** El proveedor envía una factura. Un webhook la envía a FinControl AI.
2. **Extracción (OCR + LLM):** El agente extrae: RFC del Proveedor, Folio de Factura, Artículos, Cantidades y Precios.
3. **Consulta de Integridad (SQL):** El agente ejecuta una consulta a la BD. Revisa si el RFC existe y está activo (`proveedores`). Busca la Orden de Compra ligada y el registro de recepción.
4. **Validación (Motor de Reglas):** 
   * Compara `Cantidad_Facturada` vs `Cantidad_Recibida`. (Valida RN-04: No aceptar mayor cantidad).
   * Compara `Precio_Facturado` vs `Precio_OC`.
5. **Acción Transaccional:**
   * **Éxito:** Si hay *match* perfecto (o dentro de tolerancia), el agente llama a la API del ERP para crear la Factura de A/P y genera el asiento contable (cargo a Inventario/IVA, abono a Proveedores).
   * **Fallo:** Si hay discrepancia, etiqueta el documento con estado `En Revisión` y registra en la bitácora: *"Fallo de 3-way match: Diferencia de precio fuera de tolerancia."*

### Diagrama de Decisión del Agente (BPMN/Flujo)

```mermaid
flowchart TD
    A([Agente recibe Factura de Proveedor]) --> B[Extraer Datos: RFC, OC, Montos]
    B --> C{¿Proveedor Activo en Catálogo?}
    C -- No --> D[Rechazar y Notificar]
    C -- Sí --> E[Consultar OC y Recepción en BD]
    E --> F{¿3-Way Match Exitoso?<br>(Cantidades y Precios coinciden)}
    F -- No --> G{¿Diferencia dentro de Tolerancia?}
    G -- No --> H[Bloquear Pago y Notificar Compras (PU-05)]
    G -- Sí --> I[Aprobar con Ajuste de Variación (PU-04)]
    F -- Sí --> J[Aprobar Factura]
    I --> K[Generar Asiento Contable y Actualizar A/P]
    J --> K
    K --> L([Fin del proceso automatizado])
```

## 5. Alineación con Reglas de Base de Datos y Comentarios
El agente está diseñado respetando las observaciones técnicas del equipo:
*   **Consistencia:** El agente nunca realizará `DELETE` sobre registros; respetará la regla de inactivar usuarios/documentos y usar documentos inversos para cancelaciones (Notas de Crédito).
*   **Tipos de Datos:** El agente interpretará los montos monetarios estrictamente bajo variables tipo `DECIMAL` o `NUMERIC` para evitar pérdidas de precisión en los cálculos de IVA (16%, 0%).
*   **Validaciones CHECK:** El agente actuará como filtro previo, asegurándose de que valores como estatus (`A`, `C`, `X`) o que el `Total = Subtotal + IVA` sean matemáticamente correctos antes de intentar hacer el `INSERT` en la BD (evitando excepciones SQL en crudo).