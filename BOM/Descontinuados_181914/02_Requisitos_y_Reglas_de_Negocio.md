# 2. Levantamiento de requisitos y reglas de negocio

## 2.1 Requisitos funcionales

| ID | Requisito | Criterio de aceptación | Actor |
|---|---|---|---|
| RF-01 | Registrar y consultar el estado de ciclo de vida de cada componente (`ACTIVO`, `PROXIMO_A_DESCONTINUAR`, `DESCONTINUADO`) con fecha, fuente (PCN), fecha de última compra y usuario. | El cambio queda en el historial; las transiciones inválidas se rechazan (RN-01). | Comprador |
| RF-02 | Mantener las especificaciones técnicas estructuradas por componente y los criterios de compatibilidad por categoría. | Cada atributo tiene un valor de texto o uno numérico; cada criterio tiene una regla `IGUAL`, `MINIMO` o `MAXIMO`. | Responsable técnico |
| RF-03 | Detectar automáticamente las BOM afectadas cuando un componente cambia a `PROXIMO_A_DESCONTINUAR` o `DESCONTINUADO`, incluidas las estructuras multinivel. | La alerta lista cada BOM activa con su nivel y su ruta (por ejemplo, `PC-OFI-100 > ENS-BASE-AM4 > MB-B550-PLUS`). | ERP |
| RF-04 | Generar una alerta con existencias, órdenes abiertas afectadas, demanda abierta, cobertura y prioridad, y notificar a los responsables. | La alerta se crea en la misma transacción del cambio de estado o en el siguiente ciclo del proceso de detección (≤ 15 min). | ERP |
| RF-05 | Excluir los componentes descontinuados de las recomendaciones ordinarias de compra del MRP. | Ninguna recomendación ordinaria se emite para un componente `DESCONTINUADO`; el faltante se reporta como bloqueado. | MRP |
| RF-06 | Permitir consumir las existencias del componente descontinuado cuando el uso esté autorizado. | El MRP asigna primero el stock autorizado y reporta el consumo. | MRP / Almacén |
| RF-07 | Recomendar sustitutos: descartar los incompatibles con su motivo y ordenar los compatibles con una puntuación explicable. | Se obtiene una lista de hasta 3 candidatos con su puntuación por criterio y su justificación, más la lista de descartados con los atributos incumplidos. | Agente IA |
| RF-08 | Registrar la decisión del responsable técnico (aprobar o rechazar) con comentario. | Solo el rol `RESPONSABLE_TECNICO` puede decidir; la decisión es inmutable. | Responsable técnico |
| RF-09 | Evaluar las órdenes de fabricación afectadas antes de aplicar la sustitución. | Cada orden abierta recibe una decisión: `CONSERVAR` (liberada o en proceso) o `REPLANIFICAR` (planificada). | Producción |
| RF-10 | Aplicar la sustitución creando una nueva revisión de cada BOM con uso directo y cerrando la vigencia de la anterior. | La versión anterior queda `OBSOLETO` sin modificar sus líneas; la nueva queda `ACTIVO`; las BOM superiores toman el subensamble vigente. | Responsable de BOM |
| RF-11 | Conservar el historial completo: ciclo de vida, alerta, recomendaciones, autorización, sustitución y evaluación de órdenes. | Es posible reconstruir quién, cuándo, por qué y qué cambió; los registros históricos no se pueden editar ni borrar. | ERP |
| RF-12 | Recalcular el MRP después de la sustitución con la política "agotar existencias". | Se consume el stock del original antes de comprar el sustituto. | MRP |
| RF-13 | Calcular y consultar los KPIs del proceso. | Los seis KPIs se pueden obtener con consultas SQL (ver 06_KPIs.md). | Gerencia |

## 2.2 Requisitos no funcionales

| ID | Requisito |
|---|---|
| RNF-01 | **Integridad.** Las reglas críticas (RN-02, RN-06, RN-08) se aplican también en la base de datos mediante triggers, para que ningún canal de escritura pueda saltarlas. |
| RNF-02 | **Atomicidad.** La aplicación de una sustitución (nueva revisión, cierre de la anterior, historial y reasignación de órdenes) ocurre en una sola transacción. |
| RNF-03 | **Explicabilidad.** Toda recomendación del agente guarda la puntuación por criterio, la justificación textual y la versión del modelo. |
| RNF-04 | **Supervisión humana.** El agente no escribe en BOM ni en órdenes; solo propone. |
| RNF-05 | **Rendimiento.** La consulta where-used multinivel responde en menos de 2 s para 10 000 BOM activas (índice en `bom_detalle.component_sku`). |
| RNF-06 | **Auditoría.** Las fechas se almacenan en UTC (`TIMESTAMPTZ`) para medir los KPIs de tiempo. |

## 2.3 Información necesaria

| Información | Origen | Uso | Tabla (ver 07) |
|---|---|---|---|
| Estado de ciclo de vida, fecha de EOL, LTB y fuente | Proveedor → Compras | Detección y bloqueo de compras | `componente_ciclo_vida`, `componente_ciclo_vida_historial` |
| Categoría y especificaciones técnicas | Ingeniería | Filtro de compatibilidad | `articulos.categoria`, `articulo_especificaciones`, `criterios_compatibilidad` |
| Estructura de las BOM activas | BOM | Where-used multinivel | `bom_cabecera`, `bom_detalle` |
| Existencias disponibles y reservadas | Inventarios | Cobertura, consumo autorizado y puntuación de inventario | `existencias` |
| Costo, tiempo de entrega y disponibilidad por proveedor | Compras | Puntuación del sustituto | `proveedores`, `articulo_proveedor` |
| Órdenes de fabricación abiertas | Producción | Prioridad e impacto | `ordenes_produccion` |
| Alertas y BOM afectadas | ERP | Seguimiento y KPI | `alertas_descontinuacion`, `alerta_bom_afectada` |
| Recomendaciones del agente | IA | Decisión técnica | `recomendaciones_sustitucion` |
| Autorizaciones | Responsable técnico | Control | `autorizaciones_sustitucion` |
| Historial de sustituciones y evaluación de órdenes | ERP | Trazabilidad | `sustituciones_bom`, `sustitucion_evaluacion_ordenes` |
| Recomendaciones de compra del MRP | MRP | KPI de compras inválidas | `recomendaciones_compra` |

## 2.4 Reglas de negocio

Las reglas preliminares del issue se numeran y precisan a continuación. La columna **Aplicación** indica dónde se hace cumplir cada regla.

| ID | Regla | Regla preliminar del issue | Aplicación |
|---|---|---|---|
| RN-01 | **Ciclo de vida.** Las transiciones válidas son `ACTIVO ↔ PROXIMO_A_DESCONTINUAR` y `ACTIVO/PROXIMO_A_DESCONTINUAR → DESCONTINUADO`. `DESCONTINUADO` es un estado final; si el proveedor reactiva la pieza, se registra como un artículo nuevo. Todo cambio guarda usuario, fecha y fuente. | — | Trigger `trg_ciclo_vida_cambio`; `ERP.cambiar_estado` |
| RN-02 | **Sin compras ordinarias.** Un componente `DESCONTINUADO` no genera nuevas recomendaciones ordinarias de compra. Solo se admite una compra de tipo `ULTIMA_COMPRA` antes de la fecha LTB y con autorización de Compras. | "Un componente descontinuado no deberá generar nuevas recomendaciones ordinarias de compra." | Trigger `trg_bloquear_compra_descontinuado`; `ERP.mrp` |
| RN-03 | **Consumo de existencias.** Un descontinuado se puede seguir usando mientras haya unidades disponibles y `uso_stock_autorizado = TRUE`. Tras la sustitución, el MRP consume primero ese stock (política `AGOTAR_EXISTENCIAS`), salvo que se elija `INMEDIATA` por razones de calidad. | "Podrá seguir utilizándose mientras existan unidades disponibles y su uso esté autorizado." | `ERP.mrp`; `sustituciones_bom.politica` |
| RN-04 | **Detección multinivel.** El ERP identifica todas las BOM activas que contienen el componente en cualquier nivel, sin repetir y sin entrar en ciclos. | "El ERP deberá identificar todas las listas de materiales afectadas, incluyendo aquellas con estructuras multinivel." | `fn_boms_afectadas` (CTE recursiva); `ERP.boms_afectadas` |
| RN-05 | **Compatibilidad técnica.** Un sustituto debe pertenecer a la misma categoría, no estar descontinuado y cumplir **todos** los criterios obligatorios de `criterios_compatibilidad` (`IGUAL`, `MINIMO` y `MAXIMO`). Un componente `PROXIMO_A_DESCONTINUAR` puede recomendarse, pero se penaliza. | "Los componentes sustitutos deberán cumplir con los requisitos técnicos del producto." | `ERP.es_compatible`; consulta 3.2; trigger `trg_validar_sustitucion` |
| RN-06 | **Autorización obligatoria.** Ninguna sustitución se aplica sin una autorización `APROBADA` del rol `RESPONSABLE_TECNICO` que coincida con el par original–sustituto recomendado. | "Ninguna sustitución podrá aplicarse sin autorización del responsable correspondiente." | `CHECK rol`; trigger `trg_validar_sustitucion`; `ERP.autorizar` |
| RN-07 | **Evaluación de órdenes.** Antes de aplicar la sustitución se evalúan las órdenes abiertas afectadas (en cualquier nivel): las `LIBERADA`/`EN_PROCESO` **conservan** su versión de BOM (snapshot) y las `PLANIFICADA` se **replanifican** con la nueva revisión. Las `TERMINADA`/`CANCELADA` no se tocan. | "Las órdenes de fabricación existentes deberán evaluarse antes de aplicar modificaciones." | `sustitucion_evaluacion_ordenes`; `ERP.aplicar_sustitucion` |
| RN-08 | **Historial inmutable.** Toda sustitución crea una **nueva revisión** de la BOM; la anterior pasa a `OBSOLETO` sin modificar sus líneas. Las autorizaciones, las sustituciones y el historial del ciclo de vida no se pueden actualizar ni borrar. | "Toda sustitución deberá conservar un registro histórico." | Triggers `trg_*_inmutables`; `ERP.aplicar_sustitucion` |
| RN-09 | **Supervisión humana del agente.** El agente solo lee datos y escribe recomendaciones. No cambia estados, BOM ni órdenes. | — | Permisos de rol; diseño del agente (07) |
| RN-10 | **Prioridad de alertas.** `CRITICA`: descontinuado, con órdenes abiertas y existencias insuficientes. `ALTA`: con órdenes abiertas, o descontinuado usado en 3 o más BOM. `MEDIA`: usado en BOM, sin órdenes. `BAJA`: sin uso en BOM activas. | — | `ERP.priorizar`; trigger (versión preliminar sin cobertura) |

## 2.5 Decisiones apoyadas por el agente inteligente

| Decisión | Quién decide | Apoyo del agente | Nivel de automatización |
|---|---|---|---|
| ¿Qué BOM y órdenes están afectadas? | ERP | Ejecuta la consulta where-used y cruza la información con las órdenes. | Automática (determinista) |
| ¿Qué tan urgente es la alerta? | Responsable de BOM | Calcula la prioridad con RN-10 y la cobertura de inventario. | Automática; la persona puede reclasificar |
| ¿Existe riesgo de desabasto? | Comprador / Producción | Compara existencias contra demanda abierta y fecha LTB. | Recomendación |
| ¿Qué candidatos son compatibles? | Responsable técnico | Aplica el filtro duro de RN-05 e indica los atributos incumplidos. | Recomendación |
| ¿Cuál sustituto conviene más? | Responsable técnico | Ranking ponderado por costo, disponibilidad, tiempo de entrega, ciclo de vida e impacto, con justificación. | Recomendación |
| ¿Se aplica la sustitución? | Responsable técnico | — | **Humana obligatoria** (RN-06) |
| ¿Se conserva o se replanifica cada orden? | Producción | Propone la decisión según el estado de la orden (RN-07). | Recomendación |
