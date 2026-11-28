# Pruebas Funcionales: Módulo de Lead Time de Materiales y Productos Internos

Este documento contiene las especificaciones de las pruebas funcionales para validar el cálculo de tiempos de entrega (Lead Time), la programación hacia atrás del MRP, el respeto al calendario operativo y la gestión de alertas de retraso.

---

## Caso de Prueba 1: Validación integral de Lead Time acumulado (Materiales y Productos Internos)

### Objetivo
Verificar que el motor de MRP sume correctamente los tiempos de aprovisionamiento y fabricación en una estructura multinivel, realizando una programación hacia atrás respetando los días no laborables.

### Precondiciones y Datos Maestros
* **Producto Terminado (PT):** Fabricación interna con un Lead Time de producción de **3 días**.
* **Subensamble (SUB):** Fabricación interna con un Lead Time de producción de **4 días**.
* **Materia Prima (MP):** Artículo comprado con un Lead Time de proveedor de **10 días** más **2 días** adicionales de inspección y recepción.
* **Calendario Operativo:** Debe contener días no laborables (fines de semana y/o festivos) registrados dentro del horizonte de prueba.

### Pasos de Ejecución
1. Registrar un pedido de cliente para el Producto Terminado (PT) con fecha de entrega programada a **25 días**.
2. Ejecutar el asistente de cálculo del MRP incluyendo el Producto Terminado y sus componentes.
3. Revisar las recomendaciones generadas para las Órdenes de Fabricación (PT y SUB) y la Solicitud/Orden de Compra (MP).

### Resultado Esperado
* El sistema realiza la programación hacia atrás sumando todos los tiempos de compra, recepción y fabricación (19 días hábiles acumulados en total).
* Se excluyen automáticamente los días inhábiles registrados en el calendario.
* Las fechas sugeridas de lanzamiento de las Órdenes de Compra y Órdenes de Fabricación se escalonan correctamente para cumplir a tiempo con la entrega final del cliente.

---

## Caso de Prueba 2: Cálculo de Lead Time, calendario operativo y alertas retroactivas

### Objetivo
Validar el desglose de tiempos operativos tanto en compras como en manufactura, la exclusión de días inhábiles y el comportamiento del sistema ante demandas urgentes con fechas de inicio inviables en el pasado.

### Precondiciones y Datos Maestros
* **Artículo de Compra:** Configurado con tiempo de tránsito del proveedor más tiempos internos de recepción, inspección y almacenamiento.
* **Producto Interno:** Configurado con tiempos de preparación (setup), procesamiento y espera dentro de su ruta de producción.
* **Calendario Operativo:** Activo, excluyendo fines de semana y días festivos oficiales.

### Pasos de Ejecución
1. Generar una **demanda normal** (con holgura suficiente dentro del horizonte) y una **demanda urgente** (cuyo tiempo de entrega requerido sea menor al Lead Time total calculado, proyectando un inicio en el pasado).
2. Ejecutar el asistente de MRP sobre ambos artículos.
3. Analizar las fechas de liberación sugeridas y las notificaciones o mensajes del sistema.

### Resultado Esperado
* Para la **demanda normal**, el sistema proyecta las fechas de liberación ubicándolas estrictamente en días hábiles.
* Para la **demanda urgente**, el sistema **nunca programa órdenes en el pasado**; en su lugar, reasigna la fecha de inicio al día actual.
* El asistente emite una **alerta automática de retraso/urgencia** indicando la inviabilidad de cumplir con la fecha solicitada bajo los tiempos estándar.
