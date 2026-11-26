# [Plan de Trabajo] APReceiptCapacityAgent - 175932

**Versión local del plan. Issue publicado: https://github.com/jesusrevilla/ERP-simulator/issues/301**

# Información del Alumno
Alumno: José Armando Palomo Cerda
Matrícula: 175932
Tema Asignado: A/R y A/P (cuentas por pagar)

# Nombre del Agente
APReceiptCapacityAgent - Agente de Capacidad Acumulada de Facturación de Recepciones.

# Problema que Resolverá
Una comprobación individual puede aceptar dos facturas de 6 piezas contra una recepción de 10; juntas suman 12. El agente controla la cantidad neta acumulada de documentos aprobados por línea de recepción, incluyendo notas de crédito de cantidad, reintentos y concurrencia.

# Objetivo del Agente
Evitar consumir más capacidad que la recibida y producir decisiones explicables y trazables. Es un sistema experto determinista, no un LLM ni un sistema de pagos. Su alcance se diferencia de conciliación de precio, crédito de clientes, tesorería, sincronización general y detección de facturas duplicadas por folio.

# Entradas del Agente
Línea de recepción validada (cantidad, artículo, proveedor), evento de factura o nota de crédito de cantidad, documento origen, cantidad Decimal y clave idempotente del evento.

# Decisiones o Acciones del Agente
Aceptar una reserva de capacidad; bloquear un exceso; rechazar una nota mayor que la factura neta; detectar un evento repetido o una clave reutilizada con otro contenido; registrar decisión, motivo y cantidades antes/después. No ordena pagos.

# Tecnologías a Utilizar
Python, PostgreSQL (esquema aislado y bloqueo de fila), Neo4j/Cypher (grafo de trazabilidad y auditoría independiente), MongoDB (bitácora idempotente de decisiones), GitHub y GitHub Actions. Datos de prueba sintéticos.

# Plan de Actividades
## Fase 1. Investigación
Analizar AR&AP/Requerimientos_y_Diagramas.md y las funciones existentes; contrastar propuestas de compañeros. RN-04 y la prohibición de facturar más de lo pendiente sustentan el alcance.
## Fase 2. Diseño
Definir capacidad neta = facturas aceptadas - notas de crédito de cantidad aceptadas; disponible = recibido - capacidad neta. Documentar reglas, contrato de evento y esquema aislado para no alterar tablas compartidas.
## Fase 3. Implementación
Implementar función transaccional con idempotencia, motor de reglas Python, proyección Cypher y bitácora MongoDB. Preparar avances locales separados; commits únicamente cuando el alumno los autorice.
## Fase 4. Pruebas
Cubrir factura válida, exceso acumulado, límite exacto, crédito válido/excesivo, reintento, colisión de clave y dos solicitudes simultáneas. Contrastar decisiones y conteos en las tres bases.
## Fase 5. Documentación
Guardar resultados reales, imágenes del grafo derivadas de la ejecución, logs, instrucciones, PDF de evidencias y PR final hacia development del repositorio original.

# Entregables
Código fuente; esquema y validaciones PostgreSQL; consultas Cypher y MongoDB; workflow; pruebas; evidencia; documentación técnica y PDF; PR vinculado al Issue.

# Criterios de Aceptación
- Rama feature/175932.
- No sobrepasar capacidad, ni liberar más de lo facturado.
- Reintentos no duplican cantidades ni bitácoras.
- Concurrencia deja una decisión bloqueada si ambas no caben.
- Coincidencia entre PostgreSQL, grafo y bitácora.
- Pruebas reproducibles en GitHub Actions.
- Evidencia y documentación; PR generado. La aprobación/merge corresponde al mantenedor.
