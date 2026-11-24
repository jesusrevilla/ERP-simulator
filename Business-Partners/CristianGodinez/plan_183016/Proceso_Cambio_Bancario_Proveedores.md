# Plan funcional — Control seguro de modificaciones bancarias de proveedores

**Alumno:** Cristian Ricardo Godinez Limones | **Matrícula:** 183016  
**Equipo:** Business Partners | **Caso:** TechAssembly S.A. | **Materia:** CNO VI Sistemas ERP  
**Rama de trabajo:** \`feature/183016\` | **Ubicación:** \`Business-Partners/CristianGodinez/plan_183016/\`  
**Naturaleza:** especificación de negocio; no es una implementación bancaria ni una integración real con SAP B1.

## 1. Alcance y antecedentes

Se estudia el cambio de cuenta bancaria de **proveedores ya existentes** (\`CardCode\`, tipo \`V\`) y su posterior habilitación para pagos. Los cambios quedan **pendientes** hasta completar verificaciones independientes, con trazabilidad de cada decisión.

Esta planeación se diferencia de:
- [Issue #216](https://github.com/jesusrevilla/ERP-simulator/issues/216): Ulises Loredo, ciclo general de alta, validación fiscal/crediticia y mantenimiento de Business Partners.
- [Issue #217](https://github.com/jesusrevilla/ERP-simulator/issues/217): expediente maestro centralizado y evaluación integral de socios.
- [Aportación previa de Cristian](../business_partner_events_cristian.py): estados y validaciones de socios, contactos, límites y bloqueos.

**Aporte individual:** autorización de un cambio *sensible* posterior al alta; diseño del doble control, verificación por canal conocido, versiones bancarias y protección del destino de pago.

La documentación anterior del equipo distingue clientes/proveedores/Leads y el vínculo con MRP. Esta planeación no agrega tablas a la base de datos operativa ni cambia archivos ajenos.

## 2. Problema de negocio

Supongamos que un proveedor avisa por correo que cambió su cuenta de cobro. Si un operador cambia los datos inmediatamente, se corre el riesgo de registrar una cuenta incorrecta, aceptar una solicitud falsificada o permitir que una sola persona solicite y apruebe su propia modificación. La cuenta nueva podría ser utilizada en un pago antes de que alguien haya verificado la identidad del solicitante.

Se trata de **riesgos hipotéticos** para el ejercicio; no se afirma que TechAssembly o SAP Business One operen así hoy.

## 3. Objetivo y criterios de éxito

Diseñar un flujo **solicitud → comprobación de datos → verificación fuera de banda → autorización humana independiente → activación versionada → auditoría**, de modo que solo una cuenta vigente y autorizada sea elegible en Tesorería.

Resultados esperados:
1. **Cero** activaciones sin verificación y aprobación independientes.
2. **Cero** pagos dirigidos a cuentas marcadas como pendientes/rechazadas.
3. Historial consultable de cada solicitud sin publicar números de cuenta completos.
4. Capacidad de detectar, escalar y resolver solicitudes sospechosas.

Las metas son de diseño, **no resultados medidos**.

## 4. Actores y responsabilidades

| Actor | Responsabilidad | Límite |
|---|---|---|
| Proveedor | Solicitar cambio y proporcionar justificante | No activar cuentas ni aprobar |
| Compras (solicitante interno) | Capturar solicitud, asociar \`CardCode\`, registrar documentos | No verificar ni aprobar su propia solicitud |
| Datos Maestros | Validar tipo V, estado, formato, versionado y consistencia | No utilizar cuentas pendientes para pagos |
| Finanzas (verificador) | Confirmar solicitud con contacto **ya registrado** antes del cambio | No ser el solicitante ni aprobador |
| Finanzas (aprobador) | Evaluar riesgo y aprobar/rechazar | No ser solicitante ni verificador |
| Tesorería | Consultar cuenta autorizada en el momento de pago | No usar la cuenta propuesta hasta aprobación |
| Auditoría | Revisar bitácora y evidencias | Acceso de solo lectura |
| Agente IA | Señalar anomalías y proporcionar motivos explicables | **Nunca** aprobar, activar ni ejecutar pagos |

## 5. Flujo actual AS-IS (hipótesis de riesgo)

\`\`\`mermaid
flowchart LR
  A([Proveedor informa nueva cuenta]) --> B[Compras recibe correo]
  B --> C[Operador consulta CardCode]
  C --> D[Captura manual y guarda cuenta]
  D --> E[Tesorería consulta cuenta actual]
  E --> F([Ejecutar un pago posterior])
  B -.-> X[Posible suplantación del remitente]
  D -.-> Y[Posible ausencia de doble control]
  E -.-> Z[Posible uso de cambio no verificado]
\`\`\`

## 6. Proceso propuesto TO-BE

\`\`\`mermaid
flowchart TD
  A([Solicitud del proveedor]) --> B[Compras registra solicitud y versión propuesta]
  B --> C{¿CardCode tipo V, activo y elegible?}
  C -- No --> X[Rechazar y registrar causa]
  C -- Sí --> D[Datos Maestros valida formato, titular y documentos]
  D --> E{¿Información consistente?}
  E -- No --> X
  E -- Sí --> F[Conservar cuenta actual y bloquear uso de la propuesta]
  F --> G[Finanzas verifica por contacto histórico, fuera de banda]
  G --> H{¿Verificación positiva y documentada?}
  H -- No --> X
  H -- Sí --> I[Segundo responsable evalúa riesgo y conflicto de roles]
  I --> J{¿Aprobación humana independiente?}
  J -- No --> X
  J -- Sí --> K[Transacción atómica: archivar versión anterior y activar nueva]
  K --> L[Auditar cambio y notificar a Tesorería]
  L --> M([Fin])
  X --> M
\`\`\`

El modelo BPMN editable del TO-BE está en [cambio_bancario_proveedores.bpmn](cambio_bancario_proveedores.bpmn).

### Estados de solicitud

| Origen | Destino | Condición |
|---|---|---|
| \`DRAFT\` | \`PENDING_VERIFICATION\` | Datos completos y proveedor elegible |
| \`PENDING_VERIFICATION\` | \`PENDING_APPROVAL\` | Confirmación fuera de banda con evidencia |
| \`PENDING_VERIFICATION\` | \`REJECTED\` | Identidad/formato no válido |
| \`PENDING_APPROVAL\` | \`APPROVED\` | Aprobador independiente autoriza y activa versión |
| \`PENDING_APPROVAL\` | \`REJECTED\` | Riesgo, incumplimiento o conflicto de roles |
| \`PENDING_VERIFICATION\`/\`PENDING_APPROVAL\` | \`EXPIRED\` | Vencimiento del plazo definido (propuesta: 48 h hábiles) |

Los estados \`APPROVED\`, \`REJECTED\` y \`EXPIRED\` son terminales. Una corrección posterior crea **otra solicitud**, nunca reescribe una decisión histórica.

### Casos de uso (CU)

| ID | Actor | Acción | Salida |
|---|---|---|---|
| CU-BP-01 | Compras | Registrar petición de cambio | Folio, CardCode y versión PENDING |
| CU-BP-02 | Datos Maestros | Revisar elegibilidad del proveedor y formato | Aprobado para verificación o rechazo motivado |
| CU-BP-03 | Verificador financiero | Llamar al contacto histórico y registrar evidencia | Resultado verificable con fecha y actor |
| CU-BP-04 | Aprobador financiero | Autorizar/rechazar con segregación de funciones | Decisión firmada |
| CU-BP-05 | Tesorería | Consultar cuenta vigente al crear pago | Únicamente cuenta APPROVED |
| CU-BP-06 | Auditor | Consultar bitácora y excepciones | Línea de tiempo enmascarada |
| CU-BP-07 | Agente IA | Priorizar solicitudes de riesgo | Puntaje, explicaciones y alerta (sin activación) |

## 7. Reglas de negocio verificables

| ID | Regla | Consecuencia |
|---|---|---|
| BP-BC-01 | Solo \`CardCode\` existente, tipo V y activo admite solicitud | Rechazar en otro caso |
| BP-BC-02 | Cambios pendientes no alteran la cuenta autorizada vigente | Bloquear su uso en pagos |
| BP-BC-03 | CLABE mexicana: 18 dígitos y dígito de control válido; para bancos extranjeros, validación específica por país | Rechazar formato inválido |
| BP-BC-04 | Verificar identidad por **canal preexistente**; no usar contacto aportado en la solicitud | Mantener PENDING si no se puede comprobar |
| BP-BC-05 | Solicitante, verificador y aprobador son tres usuarios distintos | Impedir autoaprobación |
| BP-BC-06 | Solo se permite una solicitud abierta por proveedor y cuenta/moneda/uso | Bloquear carreras y duplicados |
| BP-BC-07 | Cualquier cambio de titular o repetición anómala exige escalamiento humano | Mantener pendiente |
| BP-BC-08 | Activación y retiro de versión anterior ocurren en una transacción indivisible | No dejar dos cuentas vigentes para mismo uso |
| BP-BC-09 | Toda denegación/caducidad conserva causa y sello de tiempo | No borrar historial |
| BP-BC-10 | La cuenta completa y el documento bancario se protegen mediante cifrado/controles de acceso; eventos públicos solo usan últimos cuatro dígitos y token | Prevenir exposición de datos |
| BP-BC-11 | El agente IA solo recomienda \`REVIEW\`/\`ESCALATE\` | Rechazar aprobación automática |
| BP-BC-12 | Si se sospecha fraude, Finanzas puede ordenar retención explícita de pagos, incluso a la versión vigente | Registrar decisión y motivo |

**Aclaración:** son políticas propuestas para TechAssembly. No se afirman como características nativas garantizadas de SAP Business One.

## 8. Indicadores de desempeño (KPIs)

| KPI | Fórmula | Fuente | Meta piloto |
|---|---|---|---|
| Activaciones correctamente autorizadas | (\`activaciones_con_doble_control / activaciones_totales\`) × 100 | Aprobaciones + auditoría | 100 % |
| Activaciones sin control | Conteo de cambios activos sin verificación o aprobador | Versiones + verificaciones | 0 |
| Tiempo hábil de resolución | Promedio \`fecha_resolucion - fecha_solicitud\` en horas hábiles | Solicitudes | ≤ 24 h |
| Verificación fuera de banda | (\`aprobadas_verificadas / aprobadas_totales\`) × 100 | Bitácora | 100 % |
| Solicitudes vencidas | (\`pendientes_mayores_48h / pendientes_totales\`) × 100 | Solicitudes | ≤ 5 % |
| Alertas con revisión humana | (\`alertas_revisadas / alertas_generadas\`) × 100 | Alertas + decisiones | 100 % |

**Línea base:** no disponible todavía; iniciar medición durante piloto. En denominadores 0, reportar **N/A**, no 0 % ni 100 %.

## 9. Escenarios y criterios de aceptación

Los ejemplos utilizan códigos y cuentas **ficticios enmascarados**. No hay datos bancarios reales.

| Escenario | Dato de entrada | Resultado esperado |
|---|---|---|
| Escenario A, normal | Proveedor V activo, 2 revisores distintos, evidencia de llamada | Versión nueva activa y anterior archivada |
| Escenario B, autoprobación | Solicitante = aprobador | Rechazo \`SEGREGATION_OF_DUTIES\` |
| Escenario C, suplantación | No coincide el contacto histórico | Rechazo \`IDENTITY_UNVERIFIED\` |
| Escenario D, pendiente | Se intenta pagar usando la versión pendiente | Rechazo \`BANK_VERSION_NOT_APPROVED\` |
| Escenario E, concurrente | Dos cambios del mismo proveedor abiertos | Rechazo de segundo intento \`DUPLICATE_OPEN_REQUEST\` |
| Escenario F, vencida | Falta evidencia transcurridas 48 h hábiles | \`EXPIRED\`, cuenta vieja sigue vigente |
| Escenario G, riesgo alto | Cambio 12 h antes de un pago, titular distinto | Agente recomienda revisión humana; no activa |
| Escenario H, error al guardar | Fallo de activación entre versión anterior y nueva | Rollback; no hay pérdida de cuenta vigente |

Los resultados anteriores son **criterios de aceptación**, no pruebas ejecutadas en una base operativa.

## 10. Información requerida para Bases de Datos

Diseño lógico propuesto (**no implementado**):

| Entidad propuesta | Campos principales | Regla |
|---|---|---|
| \`bp_bank_change_request\` | \`request_id\`, \`card_code\`, \`old_version_id\`, \`proposed_account_token\`, \`status\`, \`requester_id\`, \`reason\`, \`created_at\`, \`expires_at\` | FK a maestro BP, unicidad lógica por solicitud activa |
| \`bp_bank_change_verification\` | \`request_id\`, \`verifier_id\`, \`channel_ref\`, \`result\`, \`verified_at\`, \`evidence_ref\` | Verificador distinto del solicitante |
| \`bp_bank_change_approval\` | \`request_id\`, \`approver_id\`, \`decision\`, \`decided_at\`, \`reason\` | Aprobador distinto de ambos |
| \`bp_bank_account_version\` | \`account_version_id\`, \`card_code\`, \`currency\`, \`payment_use\`, \`masked_account\`, \`encrypted_ref\`, \`valid_from\`, \`valid_to\`, \`active\` | Máximo una versión activa por BP/moneda/uso |
| \`bp_bank_change_audit\` | \`event_id\`, \`request_id\`, \`actor_id\`, \`event_type\`, \`occurred_at\`, \`details_sanitized\` | Bitácora sin CLABE completa |

**Integración:** la referencia a BP \`CardCode\` debe mapearse con el identificador real que utilice la implementación local, no asumir que existe una tabla física llamada \`OCRD\` en PostgreSQL. Como el módulo ya dispone de reglas \`supplier_rules\` con \`supplier_code\`, se requiere especificar el mapeo \`supplier_code\` ↔ \`CardCode\`; ninguna cuenta bancaria pertenece a \`supplier_rules\`.

### Consultas necesarias

1. Solicitudes pendientes por proveedor, responsable, estado y antigüedad.
2. Versiones bancarias aprobadas/vigentes, para Tesorería, con control de acceso.
3. Solicitudes aprobadas sin evidencia completa (debería devolver **0**).
4. Historial de aprobaciones por usuario y conflictos de segregación.
5. KPIs por semana/mes, excluyendo rechazos de los denominadores de aprobaciones cuando corresponda.

## 11. Agente IA: decisiones permitidas y no permitidas

**Entradas mínimas (sin datos bancarios completos):** CardCode tokenizado, fecha de solicitud, recurrencia de cambios, presencia de documentos, discrepancia entre titular verificado y propuesto, proximidad de pagos, verificaciones pendientes, canal de origen.

**Salidas:** \`risk_band: LOW/MEDIUM/HIGH\`, lista de señales explicables, \`suggested_action: REVIEW/ESCALATE\`, \`human_required: true\`.

**Prohibido:** aprobar cambios, activar cuentas, modificar saldos, ejecutar pagos o usar documentos/CLABE sin los permisos del custodio.

Política propuesta: **riesgo alto** produce alerta y revisión; **riesgo bajo** tampoco omite los dos controles humanos.

## 12. Evidencias y resultado

- Issue individual redactado: [ISSUE_plan_de_trabajo_183016.md](ISSUE_plan_de_trabajo_183016.md).
- Diagrama BPMN de proceso TO-BE: [cambio_bancario_proveedores.bpmn](cambio_bancario_proveedores.bpmn).
- Matriz y ejemplos: este documento, con dos diagramas Mermaid y ocho escenarios.
- Los resultados son propuestas funcionales; **no** se afirma integración SAP B1, prueba de pagos ni ejecución del agente IA.

## 13. Entrega y seguimiento

Según \`Document.PDF\` del profesor: primero Issue \`[Plan de Trabajo] ... - 183016\`, rama \`feature/183016\`, luego análisis y documentos, y finalmente PR \`[Entrega Final] 183016 - Business Partners: cambios bancarios seguros\` hacia \`development\` con enlace al Issue.

Esta carpeta se mantiene dentro de \`Business-Partners/CristianGodinez/\`, junto al código y pruebas ya aportados al equipo.
