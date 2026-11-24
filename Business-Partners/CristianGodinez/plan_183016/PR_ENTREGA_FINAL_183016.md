# Plantilla de Pull Request final (publicar después del Issue)

**Título obligatorio:** `[Entrega Final] 183016 - Business Partners: control seguro de cambios bancarios`

> El Issue individual ya fue publicado: [#240](https://github.com/jesusrevilla/ERP-simulator/issues/240). Esta descripción puede usarse para el PR final.

# Resumen

Planeación individual del proceso **Cambio seguro de cuentas bancarias de proveedores** del módulo **Business Partners** de TechAssembly S.A. La propuesta se enfoca en validación de solicitudes, segregación de funciones, verificación fuera de banda, autorización humana, versionado y auditoría. Es distinta del ciclo general del socio (#216) y del expediente centralizado (#217).

Closes #240

---

# Actividades Realizadas

- Análisis del proceso AS-IS hipotético y diseño TO-BE.
- Identificación de actores y matriz de responsabilidades.
- Levantamiento de 12 reglas verificables y 7 casos de uso.
- Diseño de 6 KPIs con fórmula, fuente y meta.
- Especificación de entidades lógicas y consultas para BD.
- Definición de decisiones permitidas al agente IA.
- Ocho escenarios de aceptación con datos ficticios.

---

# Diagramas Generados

- **BPMN 2.0**: `Business-Partners/CristianGodinez/plan_183016/cambio_bancario_proveedores.bpmn`.
- Flujos **AS-IS** y **TO-BE** en Mermaid dentro del documento de análisis.
- Casos de uso CU-BP-01 a CU-BP-07.

---

# Reglas de Negocio Definidas

- El proveedor debe existir, ser de tipo V y estar activo.
- Una cuenta propuesta no se utiliza en pagos hasta ser aprobada.
- La identidad se verifica mediante un contacto previamente registrado.
- Solicitante, verificador y aprobador deben ser **personas diferentes**.
- Cada versión aprobada sustituye a la anterior mediante transacción atómica.
- No se publican números bancarios completos en eventos ni evidencias.
- El agente IA **no aprueba**, **no cambia cuentas** y **no ejecuta pagos**.

---

# KPIs Propuestos

- 100 % de cambios activados con doble control y verificación.
- 0 activaciones sin autorización.
- Tiempo medio de resolución ≤ 24 horas hábiles (meta propuesta).
- 100 % de autorizaciones con verificación fuera de banda.
- ≤ 5 % de solicitudes pendientes vencidas (>48 h hábiles).
- 100 % de alertas de riesgo revisadas por una persona.

Los KPIs son propuestas, **no métricas medidas**.

---

# Relación con IA

Motor de recomendaciones explicables que identifica solicitudes duplicadas o inusuales, cambios próximos a pagos o diferencias de titular; envía señal `REVIEW/ESCALATE` a Finanzas, sin autorizar pagos.

---

# Relación con Base de Datos

Entidades lógicas propuestas: `bp_bank_change_request`, `bp_bank_change_verification`, `bp_bank_change_approval`, `bp_bank_account_version` y `bp_bank_change_audit`. Referencia al `CardCode` del BP, control de versiones e integridad transaccional.

---

# Evidencias

- [Plan de trabajo](ISSUE_plan_de_trabajo_183016.md)
- [Análisis funcional y casos](Proceso_Cambio_Bancario_Proveedores.md)
- [Modelo BPMN 2.0](cambio_bancario_proveedores.bpmn)

---

# Resultado Obtenido

Especificación funcional auditable para implementar en el futuro un proceso seguro de modificaciones bancarias de proveedores. **No se implementan cambios reales en SAP B1 ni se ejecutan pagos.**
