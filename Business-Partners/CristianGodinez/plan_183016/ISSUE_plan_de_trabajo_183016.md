# Información del Alumno
**Nombre:** Cristian Ricardo Godinez Limones  
**Matrícula:** 183016  
**Tema General del Proyecto:** Proyecto Integrador ERP Inteligente — Business Partners (TechAssembly S.A.)

---

# Proceso ERP Asignado
**Cambio seguro de cuentas bancarias de proveedores ya registrados.** Se analiza el mantenimiento y la activación de nuevos datos bancarios de un Business Partner tipo proveedor (V), vinculado con su `CardCode`, sin confundirlo con el alta general del socio.

**Alcance individual:** verificación independiente de la solicitud, doble autorización, control de pagos y auditoría de versiones. Se diferencia del [Issue #216](https://github.com/jesusrevilla/ERP-simulator/issues/216) (ciclo general de alta y control del socio) y del [Issue #217](https://github.com/jesusrevilla/ERP-simulator/issues/217) (centralización de información).

---

# Problema de Negocio
Si el cambio de cuenta bancaria se procesa solo con un correo y una captura manual, una suplantación de identidad o un error de transcripción podría desviar pagos. No basta validar el formato de la cuenta: también debe verificarse que el proveedor solicitó el cambio y que personas diferentes lo revisaron y aprobaron.

Esta es una **situación de riesgo planteada para la empresa ficticia TechAssembly S.A.**, no la afirmación de que el repositorio actual haya sufrido fraudes.

---

# Objetivo
Definir un proceso de **solicitud → revisión → verificación fuera de banda → aprobación independiente → activación → trazabilidad**, en el que ninguna cuenta nueva pueda usarse para pagos sin autorizaciones válidas y evidencia verificable.

---

# Actores Involucrados
- **Proveedor:** solicita el cambio.
- **Compras:** registra la solicitud, identificación del socio y evidencia.
- **Responsable de datos maestros:** valida campos, estado del proveedor y versión.
- **Finanzas (verificador):** confirma con un contacto que ya estaba validado, no el incluido en el mensaje del cambio.
- **Finanzas (aprobador independiente):** decide aprobar o rechazar.
- **Tesorería:** paga únicamente a la versión autorizada de cuenta.
- **Auditoría:** consulta la línea de tiempo de decisiones.
- **Agente IA:** detecta indicios de anomalía y recomienda escalar, nunca autoaprueba.

---

# Flujo Actual del Proceso (AS-IS supuesto para el ejercicio)
1. Proveedor solicita modificar datos bancarios por correo.
2. Compras recibe la información y revisa su CardCode.
3. Se recopilan soportes y se trasladan manualmente entre áreas.
4. El dato podría actualizarse sin un control obligatorio de dos responsables independientes.
5. Tesorería consulta la cuenta guardada para el siguiente pago.
6. Las pruebas del cambio y las decisiones quedan dispersas.

**Nota:** se trata de un supuesto de análisis; no se afirma que así opere realmente SAP Business One.

---

# Problemas Identificados
- Suplantación de identidad y alteración del beneficiario.
- Errores manuales en datos bancarios o titular.
- Falta de separación de responsabilidades y evidencia.
- Solicitudes paralelas o vencidas sin control de versión.
- Uso accidental de cuentas pendientes o no verificadas.
- Ausencia de alertas de cambios próximos a un pago.

---

# Propuesta de Mejora
- Crear expediente de cambio vinculado a `CardCode` y versión bancaria anterior.
- Estados: `DRAFT`, `PENDING_VERIFICATION`, `PENDING_APPROVAL`, `APPROVED`, `REJECTED`, `EXPIRED`.
- Validación de formato (para cuentas mexicanas, CLABE de 18 dígitos con verificador), titular, banco y documento de respaldo; sin publicar cuentas completas.
- Verificar fuera de banda con contacto preexistente y registrar hora, método y verificador.
- Exigir **solicitante, verificador y aprobador distintos**.
- Bloquear el uso de la **nueva cuenta** hasta que sea aprobada; mantener la anterior válida salvo una suspensión explícita de pagos por Finanzas.
- Generar un evento de activación con la cuenta enmascarada, versión y referencia de evidencia.
- Agente inteligente: sugerir revisión adicional por actividad atípica o cambio cercano a vencimientos, sin decidir el pago.

---

# Indicadores de Desempeño (KPIs)
| Indicador | Fórmula | Meta de diseño |
|---|---|---|
| Doble aprobación | Cambios activados con verificación y aprobación válidas / total activados × 100 | 100% |
| Cambios no autorizados | Activaciones sin controles completos | 0 |
| Tiempo de resolución | Promedio de horas hábiles entre solicitud y resolución | ≤ 24 h |
| Verificación fuera de banda | Solicitudes aprobadas con constancia de contacto independiente / aprobadas × 100 | 100% |
| Solicitudes vencidas | Pendientes con antigüedad > 48 h / total pendientes × 100 | ≤ 5% |
| Alertas de riesgo revisadas | Alertas analizadas por una persona / alertas generadas × 100 | 100% |

Metas propuestas para el diseño, no cifras observadas.

---

# Plan de Actividades
## Investigación
Examinar las guías del equipo, los estados de proveedor y sus controles de compras/pagos. Delimitar los riesgos de cambio de beneficiario.

## Levantamiento de Requisitos
Definir roles, requisitos documentales, autorizaciones, eventos, datos mínimos, auditoría y excepciones.

## Modelado del Proceso
Crear BPMN AS-IS y TO-BE, diagrama de decisión y casos de uso incluyendo rechazo, caducidad y fraude sospechoso.

## Diseño de Mejoras
Especificar segregación de funciones, reglas de operación, KPIs, datos y sugerencias permitidas al agente inteligente.

## Documentación
Subir artefactos en `Business-Partners/CristianGodinez/plan_183016/` y abrir Pull Request final hacia `development` desde `feature/183016`, enlazado a este issue.

---

# Relación con Bases de Datos e IA
**BD (propuesta, no código ya implementado):** tablas `bp_bank_change_request`, `bp_bank_change_verification`, `bp_bank_account_version` y `bp_bank_change_audit`; relación por `CardCode`. Consultas para cambios pendientes, dos aprobaciones, cuenta vigente y antigüedad. **IA:** señales de riesgo, clasificación explicable y escalamiento a Finanzas; ninguna aprobación o cambio de cuenta automático.

---

# Entregables
- [ ] Análisis AS-IS / TO-BE y BPMN.
- [ ] Casos de uso y matriz de responsabilidades.
- [ ] Reglas de negocio y KPIs calculables.
- [ ] Requerimientos de BD y decisiones de IA.
- [ ] Evidencias con datos ficticios.
- [ ] Pull Request con título `[Entrega Final] 183016 - Business Partners: cambios bancarios seguros`.

---

# Criterios de Aceptación
- [ ] Documentación completa y diferenciada de #216 y #217.
- [ ] Proceso modelado en BPMN y flujo alternativo de rechazo.
- [ ] KPIs y reglas verificables con metas.
- [ ] Solicitud, verificación y aprobación segregadas.
- [ ] Contratos de información para IA y BD.
- [ ] Pull Request hacia `development`, referenciando este Issue.

**Nota:** todo es un diseño funcional didáctico, sin datos bancarios reales ni intervención sobre SAP Business One.