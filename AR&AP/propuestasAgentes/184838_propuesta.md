# Propuesta de Arquitectura de Agente Autónomo: LiquiGuard AI (Módulos A/R y A/P)

## 1. Resumen Ejecutivo y Enfoque Estratégico

Dentro del ecosistema del **Mini ERP** y su integración con el **MRP**, se propone el diseño de **LiquiGuard AI**, un sistema multi-agente orientado a la **optimización de capital de trabajo (tesorería), prevención de fraude documental y automatización conversacional de cobranza**.

A diferencia de los sistemas tradicionales basados únicamente en validación estática de recepción, **LiquiGuard AI** opera bajo una arquitectura orientada a eventos (*Event-Driven Architecture*), enfocándose en la **programación inteligente de pagos a proveedores (A/P)** para maximizar descuentos y flujo de caja, así como en la **gestión proactiva de recuperación de cartera y notas de crédito (A/R)**.

## 2. Alcance Funcional del Sistema Multi-Agente

El sistema se divide en dos sub-agentes especializados coordinados por un orquestador central:

### A. Sub-Agente de Tesorería y Egresos (Módulo A/P)

* **Validación Fiscal y Detección de Duplicidad (CFDI/XML):** Antes de procesar cualquier pasivo, el agente parsea nativamente la estructura XML del comprobante fiscal, validando la vigencia del RFC en el catálogo de `proveedores`, verificando que el UUID/Folio fiscal no haya sido registrado previamente y comprobando el desglose matemático exacto de impuestos (`IVA 16%`, `0%`, retenciones).

* **Optimización de Calendario de Pagos (Cash Flow Scheduling):** Cruza las fechas de vencimiento de las facturas de proveedores contra la proyección de liquidez del ERP. Sugiere lotes de pago semanales priorizando proveedores críticos de materia prima (ligados al MRP) y aprovechando descuentos por pronto pago sin comprometer el saldo mínimo operativo.

* **Auditoría de Variaciones Históricas:** Analiza el historial de compras de cada artículo para alertar sobre incrementos silenciosos de costos unitarios entre distintas órdenes de compra, incluso si la factura actual coincide con la OC vigente.

### B. Sub-Agente de Cobranza Proactiva y Cartera (Módulo A/R)

* **Orquestación de Cobranza Preventiva y Correctiva:** Monitorea diariamente la antigüedad de saldos (*Aging Report*) según las `condiciones_pago` pactadas. Envía recordatorios personalizados automatizados (vía correo o webhook de mensajería) 5 días antes del vencimiento y escala alertas cuando una factura entra en mora.

* **Gestión Automatizada de Devoluciones y Notas de Crédito:** Cuando se registra una devolución de mercancía o ajuste comercial en el ERP, el agente calcula el documento inverso correspondiente (Nota de Crédito), vinculándolo estrictamente a la factura origen para mantener la trazabilidad contable sin alterar registros históricos.

* **Conciliación Bancaria por Similitud Semántica:** Cruza los extractos bancarios (referencias de transferencias SPEI, montos y fechas) contra las facturas abiertas de clientes, identificando pagos parciales o pagos agrupados de múltiples facturas y proponiendo el asiento contable de aplicación.

## 3. Stack Tecnológico Propuesto

Para garantizar baja latencia, seguridad transaccional y escalabilidad dentro del entorno del Mini ERP, se selecciona una arquitectura moderna distinta a los esquemas monolíticos:

| Capa del Sistema | Tecnología Seleccionada | Justificación Técnica | 
| ----- | ----- | ----- | 
| **Orquestación de Agentes** | **LlamaIndex (Workflows)** o **CrewAI** | Permite definir flujos asíncronos basados en eventos donde cada sub-agente tiene herramientas (*tools*) aisladas de lectura y escritura controlada. | 
| **Motor de Inferencia (LLM)** | **Claude 3.5 Sonnet** / **Llama 3.1 (vía Groq/Ollama)** | Excelente capacidad de razonamiento estructurado (JSON Mode) para interpretar referencias bancarias ambiguas y redactar comunicaciones de cobranza con tono corporativo. | 
| **Procesamiento Documental** | **lxml / Python ElementTree + PyMuPDF** | Procesamiento determinista y ultrarrápido (< 50ms) para extracción directa de nodos XML (CFDI) sin depender de OCR costoso cuando existe el archivo digital nativo. | 
| **Bus de Eventos y Colas** | **Redis Streams / Celery** | Desacopla la ejecución del agente de las transacciones síncronas del ERP, asegurando que la interfaz de usuario mantenga tiempos de respuesta inferiores a 2 segundos. | 
| **Persistencia y Auditoría** | **PostgreSQL + pgvector** | Mantiene la integridad referencial del ERP y añade búsqueda vectorial para detectar similitud en descripciones de conceptos de facturación o referencias bancarias. | 

## 4. Implementación Teórica y Arquitectura de Ejecución

El agente no escribe directamente en las tablas core mediante SQL libre; en su lugar, consume **Endpoints Internos (REST/gRPC)** del backend del ERP que encapsulan las reglas de negocio y transacciones ACID.

### Caso de Uso Teórico: Conciliación y Aplicación de Cobro (A/R)

1. **Disparador (Trigger):** El módulo de tesorería carga un movimiento de abono bancario en estado `PENDIENTE_CONCILIAR` por `$45,240.00 MXN` con la referencia *"PAGO FAC 104 Y 108 DIST NORTE"*.

2. **Recuperación de Contexto (RAG / SQL Tool):** El Sub-Agente A/R consulta mediante API los clientes cuyo nombre o razón social coincida semánticamente con *"DIST NORTE"* y recupera sus facturas con estatus `A` (Activa/Pendiente).

3. **Razonamiento y Validación Matemática:**

   * Encuentra dos facturas para *Distribuidora del Norte S.A.*: `FAC-104` por `$25,240.00` y `FAC-108` por `$20,000.00`.

   * Verifica que la suma exacta (`$45,240.00`) coincida con el depósito bancario utilizando aritmética decimal exacta (`Decimal` en Python).

   * Valida que el monto a aplicar a cada factura no exceda su saldo insoluto actual.

4. **Ejecución Transaccional:** El agente invoca el servicio de aplicación de pagos del ERP enviando el payload JSON estructurado. El backend ejecuta la transacción bajo aislamiento `SERIALIZABLE` / bloqueo pesimista, actualiza los saldos, cambia el estatus de ambas facturas a `C` (Cerrada/Pagada) y genera la póliza contable (Cargo a Bancos, Abono a Clientes).

### Diagrama de Secuencia del Proceso (Mermaid)

```
sequenceDiagram
    autonumber
    participant Bank as Webhook / Extracto Bancario
    participant Queue as Redis Event Bus
    participant Agent as LiquiGuard AI (Sub-Agente A/R)
    participant API as ERP Core API (Reglas de Negocio)
    participant DB as PostgreSQL (ACID)

    Bank->>Queue: Evento: Nuevo Abono ($45,240.00 | Ref: "DIST NORTE")
    Queue->>Agent: Consumir evento de conciliación
    Agent->>API: GET /clientes/buscar?q="DIST NORTE"
    API-->>Agent: Cliente ID: 84 (Distribuidora del Norte)
    Agent->>API: GET /ar/facturas?cliente_id=84&estatus=A
    API-->>Agent: [FAC-104: $25,240.00, FAC-108: $20,000.00]
    Note over Agent: Validación aritmética exacta<br/>(Suma = Abono y Saldos >= Aplicación)
    alt Coincidencia Exacta (Confianza > 95%)
        Agent->>API: POST /ar/aplicar-pago (Payload JSON)
        API->>DB: BEGIN TRANSACTION (Lock filas facturas)
        DB-->>API: Actualiza saldos, estatus='C' y Póliza Contable
        API-->>Agent: HTTP 200 OK (Pago Registrado)
    else Discrepancia o Pago Parcial Ambiguo
        Agent->>API: POST /ar/bandeja-revision (Sugerencia de aplicación)
        API-->>Agent: Notificación enviada a Analista de Crédito
    end

```

## 5. Gobernanza, Seguridad y Cumplimiento de Reglas del ERP

Para garantizar que **LiquiGuard AI** opere de forma segura dentro de un entorno productivo sin comprometer la integridad contable, se establecen las siguientes salvaguardas técnicas:

* **Inmutabilidad Contable (Zero-Delete Policy):** El agente tiene estrictamente revocados los permisos de borrado físico. Cualquier corrección derivada de una cancelación o error de captura se resuelve exclusivamente mediante la emisión automatizada de **Notas de Crédito** o pólizas de reclasificación, conservando la pista de auditoría completa.

* **Precisión Numérica Estricta:** Todos los cálculos internos del agente (prorrateos de pagos parciales, cálculo de IVA al 16% o tasa 0%, y redondeos) se ejecutan mediante tipos de datos de punto fijo (`NUMERIC(18,4)` / `Decimal`), prohibiendo el uso de variables flotantes (`float`) para evitar desfases de centavos.

* **Human-in-the-Loop (Umbrales de Autonomía):** Se configuran límites de autorización por monto. Operaciones menores a un umbral definido por tesorería se ejecutan de manera 100% autónoma, mientras que aplicaciones de pago con diferencias cambiarias o notas de crédito superiores al límite quedan en estado `EN_APROBACION` requiriendo firma digital del supervisor financiero.

* **Prevención de Inyección y Alucinaciones:** El agente utiliza *Structured Outputs* (esquemas Pydantic) para comunicarse con el ERP. Si el LLM genera un código de estatus inválido (distinto a los permitidos por las restricciones `CHECK` de la base de datos) o un cálculo donde $\text{Total} \neq \text{Subtotal} + \text{IVA}$, el validador rechaza la instrucción antes de tocar la capa de API.