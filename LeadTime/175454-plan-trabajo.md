
# Información del Alumno

**Matrícula:** 175454

**Tema General del Proyecto:** Lead Time de Materiales y Productos Internos.

**Enfoque individual:** Optimización del Lead Time de fabricación mediante dependencias operativas y disponibilidad de materiales.

---

# Proceso ERP Asignado

Análisis y optimización del Lead Time de fabricación de productos internos en TechAssembly S.A., considerando las operaciones necesarias para el ensamble de Gaming PC, las dependencias entre actividades, los tiempos de preparación y procesamiento y la disponibilidad de materiales en cada etapa.

Se busca identificar las operaciones que deben realizarse de manera secuencial y aquellas que pueden ejecutarse en paralelo para reducir tiempos de espera y mejorar la planificación de producción.

---

# Problema de Negocio

Una planificación que únicamente considere la suma de los tiempos de fabricación o requiera la disponibilidad de todos los materiales antes de iniciar la producción puede generar tiempos de espera innecesarios.

La falta de información sobre las dependencias operativas y los materiales requeridos en cada etapa dificulta determinar qué actividades pueden adelantarse sin comprometer la continuidad del proceso productivo.

Esta situación puede incrementar el Lead Time de fabricación y afectar el cumplimiento de las fechas de entrega.

---

# Objetivo

Definir un modelo funcional para optimizar el Lead Time de fabricación mediante el análisis de dependencias operativas, actividades paralelas y disponibilidad de materiales por etapa.

Proporcionar al sistema ERP y a los agentes inteligentes información que permita evaluar alternativas de planificación, reducir tiempos de espera y mejorar el cumplimiento de las fechas de producción.

---

# Actores Involucrados

- **Cliente:** genera la demanda del producto terminado.
- **Planificador MRP:** analiza los requerimientos y las fechas estimadas de producción.
- **Producción:** define las operaciones, tiempos y dependencias del proceso de fabricación.
- **Almacén:** proporciona información sobre disponibilidad y reservas de materiales.
- **Sistema ERP:** integra la información de materiales, inventario y operaciones.
- **Agente inteligente:** analiza alternativas y recomienda secuencias de fabricación factibles.

---

# Flujo Actual del Proceso

Tomando como referencia el funcionamiento inicial del simulador ERP:

1. Se registra una orden de venta de Gaming PC.
2. El MRP identifica los materiales requeridos mediante la lista de materiales (BOM).
3. Se consulta el inventario disponible.
4. Se calculan los requerimientos y faltantes de materiales.
5. Se obtiene información para apoyar la planificación de producción.

Se propone complementar este flujo mediante un modelo que considere las operaciones de fabricación, sus dependencias, tiempos de ejecución y disponibilidad de materiales por etapa.

Se revisará la versión vigente del repositorio para identificar las funcionalidades existentes y evitar duplicidades.

---

# Problemas Identificados

- Posibles retrasos por materiales que no son necesarios durante las primeras etapas de fabricación.
- Sobreestimación del Lead Time al sumar operaciones que podrían ejecutarse simultáneamente.
- Evaluación manual de alternativas de fabricación.
- Falta de visibilidad sobre las dependencias y los materiales requeridos por operación.
- Dificultad para identificar las operaciones críticas que condicionan la finalización del producto.
- Limitaciones para evaluar el inicio parcial de producción ante faltantes de materiales.

---

# Propuesta de Mejora

Se propone desarrollar un modelo funcional que permita:

- Identificar las operaciones necesarias para la fabricación de Gaming PC.
- Establecer las dependencias entre operaciones.
- Asociar los materiales requeridos a cada etapa de fabricación.
- Identificar actividades secuenciales y paralelas.
- Considerar tiempos de preparación, procesamiento y espera.
- Identificar la ruta crítica del proceso de fabricación.
- Evaluar el inicio parcial de producción cuando existan faltantes de materiales requeridos en etapas posteriores.
- Recalcular el Lead Time ante cambios en la disponibilidad de materiales.
- Comparar diferentes alternativas de planificación.

El inicio parcial de producción deberá considerar las restricciones de recursos, reservas de materiales, capacidades y tamaños de lote.

## Relación con Inteligencia Artificial

Los agentes inteligentes podrán:

- Identificar operaciones críticas.
- Detectar posibles tiempos de espera.
- Analizar alternativas de ejecución secuencial y paralela.
- Recomendar secuencias de fabricación factibles.
- Proponer ajustes en la planificación ante cambios en la disponibilidad de materiales.

Las recomendaciones deberán validarse mediante las reglas de negocio del ERP y por el planificador antes de modificar las órdenes de producción.

## Relación con Base de Datos

Se definirán los requerimientos de información y consultas necesarias para gestionar:

- Operaciones de fabricación por producto.
- Dependencias entre operaciones.
- Tiempos de preparación y procesamiento.
- Materiales requeridos por operación.
- Disponibilidad y reservas de materiales.
- Recursos de fabricación.
- Fechas estimadas de inicio y finalización.
- Resultados de las alternativas de planificación.

---

# Indicadores de Desempeño (KPIs)

| Indicador | Descripción |
| --- | --- |
| Lead Time total de fabricación | Tiempo transcurrido desde el inicio de la primera operación hasta la finalización de la última operación requerida. |
| Tiempo de espera por materiales | Tiempo durante el cual las operaciones permanecen bloqueadas por faltantes de materiales. |
| Porcentaje de reducción del Lead Time | Comparación entre una planificación de referencia y una alternativa optimizada. |
| Disponibilidad de materiales por operación | Porcentaje de operaciones que cuentan con los materiales necesarios en su inicio planificado. |
| Cumplimiento de dependencias operativas | Porcentaje de operaciones programadas respetando sus actividades predecesoras. |
| Cumplimiento de fechas de fabricación | Porcentaje de órdenes finalizadas dentro de la fecha planificada. |

---

# Plan de Actividades

## Investigación

- Investigar los conceptos de Lead Time de fabricación, ruta crítica y dependencias operativas.
- Analizar las diferencias entre operaciones secuenciales y paralelas.
- Investigar la relación entre disponibilidad de materiales y planificación de producción.
- Revisar la estructura del simulador ERP y las aportaciones existentes del equipo.

## Levantamiento de Requisitos

- Identificar los requerimientos funcionales del proceso.
- Definir las reglas de negocio aplicables.
- Identificar la información requerida por el equipo de Base de Datos.
- Definir las decisiones que podrán apoyar los agentes inteligentes.
- Establecer criterios de validación.

## Modelado del Proceso

- Elaborar el diagrama BPMN del proceso propuesto.
- Elaborar un diagrama de dependencias operativas.
- Modelar escenarios con disponibilidad completa y parcial de materiales.
- Definir los casos de uso correspondientes.

## Diseño de Mejoras

- Proponer alternativas de planificación de fabricación.
- Identificar oportunidades de ejecución paralela.
- Definir criterios para identificar operaciones críticas.
- Establecer recomendaciones para los agentes inteligentes.
- Comparar una planificación de referencia con alternativas factibles mediante escenarios de prueba.

## Documentación

- Documentar los requerimientos funcionales y las reglas de negocio.
- Definir los KPIs y sus fórmulas de cálculo.
- Documentar los casos de uso y escenarios de prueba.
- Elaborar las especificaciones funcionales para los equipos de Base de Datos e Inteligencia Artificial.
- Generar eventos JSON con timestamps en formato ISO 8601 y referencia a la jerarquía ISA-95.
- Incorporar los entregables individuales en la carpeta compartida `LeadTime/`, identificados con la matrícula 175454.
- Registrar los avances mediante commits en la rama `Feature/175454`.
- Generar el Pull Request final vinculado a esta Issue.

---

# Entregables

- [ ] Diagrama BPMN del proceso propuesto.
- [ ] Diagrama de dependencias operativas.
- [ ] Requerimientos funcionales.
- [ ] Reglas de negocio.
- [ ] Casos de uso.
- [ ] KPIs y fórmulas de cálculo.
- [ ] Especificaciones funcionales para Base de Datos.
- [ ] Especificaciones funcionales para Inteligencia Artificial.
- [ ] Escenarios y casos de prueba.
- [ ] Eventos JSON con referencia a ISA-95.
- [ ] Documentación y evidencias.
- [ ] Pull Request final.

---

# Criterios de Aceptación

- [ ] Documentación completa del subproceso asignado.
- [ ] Proceso modelado mediante diagramas.
- [ ] Dependencias operativas identificadas.
- [ ] Operaciones secuenciales y paralelas documentadas.
- [ ] Reglas de negocio definidas.
- [ ] KPIs definidos con sus respectivas fórmulas.
- [ ] Escenarios de disponibilidad completa y parcial documentados.
- [ ] Requerimientos de información para Base de Datos e Inteligencia Artificial definidos.
- [ ] Comparación documentada de alternativas de planificación.
- [ ] Entregables incorporados en la carpeta compartida `LeadTime/`.
- [ ] Pull Request generado y vinculado a esta Issue.

---

**Alcance:** La propuesta corresponde al análisis y diseño funcional del proceso ERP. Las operaciones y duraciones que no estén definidas en el simulador serán identificadas como supuestos de simulación. Los beneficios de la optimización deberán evaluarse mediante escenarios de prueba.
