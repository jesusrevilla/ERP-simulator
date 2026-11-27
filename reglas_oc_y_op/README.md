# Módulo: Reglas de Órdenes de Compra (OC) y Órdenes de Producción (OP)

Este directorio contiene la especificación funcional, diagramas de procesos (BPMN), eventos bajo el estándar **ISA-95**, esquemas de bases de datos y reportes de revisión correspondientes al módulo de **Reglas de Órdenes de Compra y Órdenes de Producción** del Simulador ERP (`TechAssembly S.A.`).

---

## Estructura del Directorio

Para facilitar el trabajo colaborativo entre los equipos de **Requerimientos/Procesos**, **Bases de Datos** e **Inteligencia Artificial (Agentes)**, los archivos del módulo se encuentran organizados en 4 subcarpetas:

```text
reglas_oc_y_op/
├── README.md                           # Guía de organización del módulo
├── docs_requerimientos/                # 1. Requerimientos funcionales, reglas de negocio y BPMN
│   ├── Act1_181591.md
│   └── reglas_oc_y_op.md
├── eventos_isa95/                      # 2. Bases de conocimiento JSON y eventos ISA-95 para IA
│   ├── actividad2_181591.json
│   ├── eventos183060.json
│   ├── eventos_182483.json
│   └── eventos_182712_rafael_sanchez_saucedo.json
├── esquemas_bd/                        # 3. Esquemas y validaciones de bases de datos
│   ├── esquema_mongodb.js
│   └── esquema_neo4j.cypher
└── feedback_y_revisiones/              # 4. Reportes de revisión y alineación entre equipos
    ├── feedback183060.md
    ├── team_feedback_182483.md
    └── team_feedback_182712.md
```

---

## Descripción de Subcarpetas y Archivos

### 1. [`docs_requerimientos/`](./docs_requerimientos/)
Concentra la definición teórica, funcional y operativa del módulo:
* **[`reglas_oc_y_op.md`](./docs_requerimientos/reglas_oc_y_op.md):** Documento maestro de requerimientos funcionales (MRP, consumo de *Forecast*, trazabilidad por lotes FEFO, cálculo de merma/scrap, cuarentena e inspección de calidad, límites de stock y reglas de integridad) junto con sus diagramas BPMN en Mermaid.
* **[`Act1_181591.md`](./docs_requerimientos/Act1_181591.md):** Especificación detallada de requerimientos (`RF-01` a `RF-13`), reglas de negocio para compras (`RN-OC-01` a `RN-OC-05`) y producción (`RN-OP-01` a `RN-OP-06`), casos de prueba unitarios/funcionales y controles de integridad ACID.

### 2. [`eventos_isa95/`](./eventos_isa95/)
Almacena las bases de conocimiento en formato JSON diseñadas para ser consumidas por los agentes de Inteligencia Artificial bajo la jerarquía del estándar **ISA-95** (Niveles 3 MES/WMS y 4 ERP):
* **[`eventos_182712_rafael_sanchez_saucedo.json`](./eventos_isa95/eventos_182712_rafael_sanchez_saucedo.json):** Secuencia operativa ISA-95 con equivalencias en transacciones SAP (`MD01`, `ME21N`, `MIGO`, `CO01`, `CO15`) y catálogo de 9 eventos de integridad (`EVT-INT-001` a `EVT-INT-009`) con tópicos `"empresa/linea/maquina"`.
* **[`actividad2_181591.json`](./eventos_isa95/actividad2_181591.json):** Secuencia de 11 eventos transaccionales (`EVT-MRP`, `EVT-OC`, `EVT-ALM`, `EVT-OP`) con estados de éxito, alerta y bloqueo.
* **[`eventos_182483.json`](./eventos_isa95/eventos_182483.json):** Eventos basados en reglas de negocio (`OC_REG_01..04` y `OP_REG_01..04`), incluyendo validación de *3-Way Matching* y programación de capacidad.
* **[`eventos183060.json`](./eventos_isa95/eventos183060.json):** Trazabilidad de eventos desde el ingreso del *Forecast* hasta el cierre de la OP en almacén de producto terminado.

### 3. [`esquemas_bd/`](./esquemas_bd/)
Contiene la implementación de los modelos de datos y restricciones de integridad del módulo:
* **[`esquema_mongodb.js`](./esquemas_bd/esquema_mongodb.js):** Esquema documental en MongoDB con validación estricta `$jsonSchema` e índices únicos para `proveedores`, `materiales`, `productos_terminados`, `ordenes_compra`, `ordenes_produccion`, `forecast` y `pedidos_venta`.
* **[`esquema_neo4j.cypher`](./esquemas_bd/esquema_neo4j.cypher):** Modelo de grafos en Neo4j (`Proveedor`, `Material`, `ProductoTerminado`, `OrdenCompra`, `OrdenProduccion`), relaciones (`REQUIERE`, `SOLICITADA_A`, `PIDE`, `PRODUCE`, `CONSUME`) y consultas Cypher de auditoría de integridad y explosión MRP.
* *(Espacio reservado para incorporar los scripts `.sql` relacionales específicos de OC y OP).*

### 4. [`feedback_y_revisiones/`](./feedback_y_revisiones/)
Reúne las notas de auditoría, retroalimentación cruzada y hallazgos de integración con otros módulos del repositorio (como `Integridad_de_las_transacciones/documentacion/04_integridad_ordenes.md`):
* **[`team_feedback_182712.md`](./feedback_y_revisiones/team_feedback_182712.md):** Reporte de alineación documental e identificación de tablas SQL pendientes para el módulo OC y OP.
* **[`team_feedback_182483.md`](./feedback_y_revisiones/team_feedback_182483.md):** Nota sobre componentes pendientes y su relación con `04_integridad_ordenes.md`.
* **[`feedback183060.md`](./feedback_y_revisiones/feedback183060.md):** Observación inicial sobre la integración con el módulo de integridad transaccional.

