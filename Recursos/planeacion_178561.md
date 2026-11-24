# Planeación del Proyecto — ERP Inteligente
- **Alumno:** Arturo Palau Andrade
- **Matrícula:** 178561
- **Rama:** `feature/178561`
- **Tema General:** Proyecto Integrador ERP Inteligente — Simulador ERP (Módulo de Recursos, Calendarios y Capacidad en SAP Business One)

## 1. Proceso ERP Asignado
Gestión de recursos de producción (máquinas, mano de obra y otros recursos), calendarios de turnos/jornadas, disponibilidad horaria, mantenimiento y validación de capacidad para la programación de órdenes de producción en SAP Business One.

## 2. Problema de Negocio
La asignación de recursos y su disponibilidad frente a calendarios y mantenimiento carece de validaciones automáticas y centralizadas, lo que provoca conflictos de programación, sobreasignación de capacidad, uso de recursos en mantenimiento o fuera de turno y desfase entre la capacidad real y la planeada.

## 3. Objetivo
Estandarizar el control de recursos alineado a calendarios, jornadas y horas disponibles en el ERP, asegurando reglas claras de validación, métricas de desempeño (KPIs), requerimientos para Bases de Datos y decisiones automatizables para agentes de Inteligencia Artificial.

## 4. Actores Involucrados
- Planeador de Producción / MRP
- Supervisor de Planta / Manufactura
- Operador de Máquina / Recurso
- Mantenimiento
- Almacén / Producción
- Administrador del ERP / TI

## 5. Flujo Actual del Proceso
1. Alta de recursos y asignación de horarios/calendarios de forma manual o parcial.
2. Programación de órdenes de producción sin validar estrictamente capacidad disponible, días no laborables o mantenimientos.
3. Cambios de turno o paros por mantenimiento que no se reflejan de inmediato en la disponibilidad.
4. Revisión manual de choques de horarios o saturación de recursos cuando ocurren conflictos.

## 6. Problemas Identificados
- Retrasos en la programación y ejecución por choques de horario o falta de disponibilidad.
- Errores por recursos sin calendario válido, capacidad mal definida o datos desactualizados.
- Trabajo manual para detectar conflictos, días festivos o ventanas de mantenimiento.
- Falta de visibilidad clara entre horas disponibles, asignadas y consumidas.
- Cuellos de botella en recursos críticos.

## 7. Propuesta de Mejora
- **Reglas en el ERP:** Exigir calendario válido, unidad de medida y capacidad definida antes de asignar un recurso; bloquear o alertar asignaciones en días no laborables, ventanas de mantenimiento o capacidad excedida; registrar cambios de estado y calendario.
- **Relación con Inteligencia Artificial:** Detectar conflictos de agenda, saturación de capacidad y mantenimientos próximos; recomendar reprogramaciones o recursos alternativos disponibles; alertar desviaciones de horas.
- **Relación con Bases de Datos:** Almacenar maestros de recursos, calendarios/turnos, mantenimientos/excepciones, capacidad disponible/asignada y bitácora de eventos (`events_178561.json`). Consultas clave: disponibilidad horaria por recurso y fecha, recursos con conflicto/saturación y trazabilidad de uso por orden.

## 8. KPIs Propuestos
- **Utilización de capacidad:** Horas productivas asignadas / Horas disponibles.
- **Tasa de conflictos de programación:** Asignaciones conflictivas o inválidas / Total de asignaciones (Meta: reducir al mínimo / 0 asignaciones inválidas).
- **Cumplimiento de programación en fecha:** Órdenes ejecutadas en ventana planificada / Total de órdenes.
- **Tiempo de respuesta ante indisponibilidad:** Tiempo desde el reporte de paro/mantenimiento hasta la reasignación.
- **Integridad de datos maestros:** Recursos con calendario y parámetros válidos / Total de recursos (Meta: 100%).

## 9. Plan de Actividades y Entregables
- **Investigación:** Revisión de recursos, calendarios, capacidad y eventos ISA-95 / ISO 8601 UTC.
- **Levantamiento de Requisitos:** Actores, reglas de negocio, restricciones y necesidades de BD e IA.
- **Modelado del Proceso:** Diagrama de flujo / esquema en `recursos.md` y casos de uso.
- **Diseño de Mejoras:** Reglas operativas, KPIs y esquema de eventos en `events_178561.json`.
- **Documentación y Entrega:** Archivos en `Recursos/` (`recursos.md`, `events_178561.json`, `planeacion_178561.md`) y Pull Request hacia el repositorio principal.

## 10. Criterios de Aceptación
- Documentación completa y diferenciada en `feature/178561`.
- Flujo, reglas de negocio y KPIs definidos.
- Requerimientos claros para Bases de Datos e Inteligencia Artificial.
- Pull Request creado y validado.
