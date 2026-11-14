# Business Partners — aportación individual de Cristian Godinez

**Asignatura:** CNO VI Sistemas ERP — grupo A26-T51A  
**Alumno:** Cristian Ricardo Godinez Limones  
**Profesor:** Jesús Alberto Revilla Silva  
**Empresa del caso:** TechAssembly S.A.  
**Actividad:** Reglas de negocio, eventos ISA-95 y tutorial de Neo4j centrados en socios de negocio  
**Fecha:** 11 de noviembre de 2026

## 1. Contexto y objetivo

Mi equipo trabaja el módulo **Business Partners (socios de negocio)**, basado en conceptos de SAP Business One. Esta entrega **individual** implementa un flujo de datos maestros de clientes, proveedores y prospectos, con controles para contactos, direcciones, condiciones comerciales, crédito, bloqueos y conversión de clientes potenciales.

La aportación toma como referencia los documentos existentes:

- [BusinessPartner.md](BusinessPartner.md), con requerimientos del módulo, reglas y pruebas.
- [Business-Partners/business-partners.md](../Business-Partners/business-partners.md), con interacción de socios, compras y MRP.

No se reproducen sus textos ni se cambian los trabajos de otros integrantes. Mi caso de estudio y catálogo de eventos son propios, aunque cubren el mismo módulo asignado.

## 2. Alcance funcional del módulo

| ID | Requerimiento | Evidencia de implementación |
|---|---|---|
| BP-RF01 | Alta de Business Partner con **CardCode**, tipo, grupo, identificación fiscal, nombre y moneda | \`BP_REGISTERED\`; validación de campos y de CardCode único |
| BP-RF02 | Clasificación Cliente (C), Proveedor (V) o Lead (L) | \`bp_type\`; validación de tipos |
| BP-RF03 | Asociar distintas direcciones fiscales/de entrega | \`ADDRESS_ADDED\`; llave \`address_id\` única por BP |
| BP-RF04 | Asociar personas de contacto | \`CONTACT_ADDED\`; identificador único por BP |
| BP-RF05 | Configurar condiciones de pago, grupos y etiquetas | \`PAYMENT_TERMS_UPDATED\`, \`PARTNER_TAG_ADDED\` |
| BP-RF06 | Convertir prospecto a cliente sin perder datos | \`LEAD_CONVERTED\`; se conservan contactos y direcciones |
| BP-RF07 | Definir límite de crédito y saldo abierto | \`CREDIT_LIMIT_UPDATED\`; importes enteros en centavos |
| BP-RF08 | Bloquear o desbloquear compras/ventas según estatus | \`PARTNER_BLOCKED\`, \`PARTNER_UNBLOCKED\` |
| BP-RF09 | Evaluar elegibilidad de documentos comerciales | \`DOCUMENT_ATTEMPTED\`, con decisión y causa trazables |
| BP-RF10 | Desactivar socio sin borrar historial | \`PARTNER_DEACTIVATED\`; el grafo conserva eventos |

> Los eventos son **datos de simulación**. Su proyección valida el flujo de negocio, pero no inserta órdenes reales ni se conecta a SAP B1. La jerarquía ISA-95 se usa como **referencia conceptual**, no como declaración de certificación.

## 3. Reglas de negocio

1. **BP-RN01 — Unicidad:** no puede existir otro socio con el mismo \`CardCode\`.
2. **BP-RN02 — Identificación:** nombre, grupo, identificador fiscal, tipo y moneda son obligatorios.
3. **BP-RN03 — Tipos:** C = cliente, V = proveedor, L = cliente potencial.
4. **BP-RN04 — Direcciones y contactos:** se vinculan con un socio válido y tienen ID único.
5. **BP-RN05 — Conversión:** solo un lead L puede convertirse a cliente C; se mantienen sus contactos y direcciones.
6. **BP-RN06 — Bloqueo:** ninguna orden nueva de venta/compra se autoriza si el socio está bloqueado para esa operación.
7. **BP-RN07 — Documento por rol:** orden de compra únicamente con V; orden de venta únicamente con C.
8. **BP-RN08 — Crédito:** monto del pedido + saldo pendiente no puede superar el límite autorizado del cliente.
9. **BP-RN09 — Moneda:** la moneda del documento debe coincidir con la registrada para el socio en este prototipo.
10. **BP-RN10 — Baja lógica:** un socio inactivo conserva su historial, pero no puede realizar nuevas operaciones.
11. **BP-RN11 — Orden cronológico:** cada evento tiene un identificador exclusivo y una marca UTC ISO 8601 posterior al evento anterior.
12. **BP-RN12 — Auditoría:** la respuesta de autorización/rechazo conserva el evento y la causa.

Estas son reglas de **nuestro prototipo académico**; las políticas exactas y los permisos configurables de SAP Business One pueden variar.

## 4. Escenarios de ejemplo

### A. Proveedor de componentes para Gaming PC

Se da de alta el proveedor simulado \`BP-V-001\`, se crean una dirección fiscal y un contacto, se configuran pagos a 30 días y una etiqueta de proveedor crítico. El área administrativa lo bloquea para compras mientras se revisa su documentación.

Se intenta crear una orden de compra de **$2,500.00 MXN** y se obtiene \`REJECTED / BLOCKED\`. Tras quitar el bloqueo, el mismo escenario da \`APPROVED / NONE\`. No se afecta el inventario ni se crea una orden real.

### B. Lead a cliente empresarial

El socio simulado \`BP-L-001\` comienza como prospecto L, con contacto y dirección de envío. No se permite una orden de venta mientras sea L. Después se convierte a C conservando sus datos.

Con crédito autorizado de **$15,000.00 MXN** y saldo abierto inicial cero, una orden simulada de $10,000.00 se considera elegible y una de $18,000.00 se rechaza por \`CREDIT_LIMIT\`. Después se prueba bloqueo comercial, desbloqueo y desactivación.

Los nombres, correos con dominio \`example.test\` y claves fiscales con prefijo \`SIMULADO-\` son ficticios, **no identificaciones fiscales válidas para facturación real**.

## 5. Catálogo de eventos

**Ruta:** \`Business-Partner/CristianGodinez_BP_events.json\`

Se incluyen **22 eventos** con:

- \`event_id\`, \`timestamp_utc\`, \`event_type\` y \`card_code\`.
- Actor, sistema origen \`ERP_LEVEL_4\`, destino \`MOM_LEVEL_3\`.
- \`payload\` específico: contacto, dirección, límites, bloqueo, conversión o intento de documento.
- \`expected_result\` / \`expected_reason\` en eventos de evaluación de órdenes.

Ejemplos de mensajes: \`BP_REGISTERED\`, \`CONTACT_ADDED\`, \`LEAD_CONVERTED\`, \`PARTNER_BLOCKED\`, \`CREDIT_LIMIT_UPDATED\`, \`DOCUMENT_ATTEMPTED\`.

## 6. Algoritmo de validación

**Ruta:** \`src/business_partner_events_cristian.py\`

El proceso lee el catálogo, valida cronología y unicidad, proyecta cada evento al estado del socio y comprueba decisiones comerciales.

\`\`\`mermaid
flowchart TD
    A([Inicio: alta de Business Partner]) --> B[Validar CardCode, nombre, grupo, tipo y fiscal]
    B --> C{¿Datos válidos y código único?}
    C -- No --> X[Rechazar registro]
    C -- Sí --> D[Asociar contactos, direcciones y condiciones]
    D --> E{¿Es Lead?}
    E -- Sí --> F[Convertir L a C preservando historial]
    E -- No --> G[Evaluar solicitud de orden]
    F --> G
    G --> H{¿Activo y rol compatible?}
    H -- No --> Y[Rechazar por tipo o inactividad]
    H -- Sí --> I{¿Bloqueado para la operación?}
    I -- Sí --> Z[Rechazar por bloqueo]
    I -- No --> J{¿Moneda y crédito válidos?}
    J -- No --> W[Rechazar con causa]
    J -- Sí --> K[Autorizar escenario de documento]
    K --> L([Conservar eventos para auditoría])
    W --> L
    Z --> L
    Y --> L
\`\`\`

## 7. Tutorial Neo4j — solo Business Partners

**Ruta:** \`src/neo4j_business_partners_cristian.py\`

Se modelan **dos socios** y sus **22 eventos** mediante nodos separados:

- \`CGBPartner\`: datos maestros de proveedor y cliente.
- \`CGBPartnerContact\`: personas de contacto.
- \`CGBPartnerAddress\`: direcciones fiscal y de entrega.
- \`CGBPartnerEvent\`: eventos de alta, cambios y validaciones.

Las relaciones \`CG_HAS_CONTACT\`, \`CG_HAS_ADDRESS\` y \`CG_REFERS_TO_BP\` vinculan los nodos. Se utilizan \`MERGE\`, \`UNWIND\` y parámetros de Cypher, y se compara el número de nodos tras dos cargas para verificar **idempotencia**. Se evita \`DETACH DELETE\` para no alterar datos de otros participantes.

### Prueba sin servidor

Desde la raíz del proyecto:

\`\`\`bash
python -m pytest tests/test_business_partner_events_cristian.py tests/test_business_partner_graph_cristian.py -q
python -m src.business_partner_events_cristian
python -m src.neo4j_business_partners_cristian --offline
\`\`\`

### Prueba con Neo4j

Instalar dependencias:

\`\`\`bash
python -m pip install -r requirements.txt
\`\`\`

Configurar en el **entorno local**, no en código ni Git, \`NEO4J_URI\`, \`NEO4J_USERNAME\`, \`NEO4J_PASSWORD\` y opcionalmente \`NEO4J_DATABASE\`:

\`\`\`bash
python -m src.neo4j_business_partners_cristian
\`\`\`

El archivo \`.github/workflows/cristian_business_partners.yml\` ejecuta pruebas y crea un servicio Neo4j local para verificar la carga. No requiere credenciales de Neo4j Aura ni datos bancarios.

## 8. Integridad de datos y pruebas

| ID | Escenario | Resultado esperado |
|---|---|---|
| BP-PU01 | Registrar CardCode repetido | Rechazo |
| BP-PU02 | Registrar BP sin identificador fiscal | Rechazo |
| BP-PU03 | Convertir Lead en Cliente | Datos asociados preservados |
| BP-PU04 | Registrar contacto o dirección con ID repetido | Rechazo |
| BP-PU05 | Crear orden con socio bloqueado | \`REJECTED / BLOCKED\` |
| BP-PU06 | Crear orden de venta con Lead | \`REJECTED / PARTNER_TYPE\` |
| BP-PU07 | Exceder límite de crédito | \`REJECTED / CREDIT_LIMIT\` |
| BP-PU08 | Usar socio inactivo | \`REJECTED / INACTIVE\` |
| BP-PU09 | Intentar evento duplicado o fuera de orden | Rechazo |
| BP-PU10 | Repetir carga Neo4j con MERGE | Sin duplicados de socios/eventos |

La verificación de integridad en este ejercicio se realiza en la capa de validación de Python y en las restricciones de unicidad de Neo4j. No se presume la existencia de una tabla \`OCRD\` de SAP Business One ni de transacciones empresariales reales.

## 9. Conclusión

Esta contribución queda directamente vinculada al tema asignado de **Business Partners**: ciclo de vida del socio, condiciones comerciales, elegibilidad de documentos, trazabilidad y representación de relaciones mediante Neo4j. Se desarrolló de forma independiente para integrarse al ERP-Simulator sin sustituir las aportaciones del resto del equipo.
