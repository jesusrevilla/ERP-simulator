# Información del Alumno
Matrícula: 172068
Tema General del Proyecto: Lead Time de Materiales y Productos Internos (Enfoque: Materiales Comprados)

---

# Proceso ERP Asignado
Cálculo y control del tiempo de entrega para materiales adquiridos en el MRP, integrando tránsito del proveedor, tiempos internos de recepción, inspección de calidad y almacenamiento seguro, margen de tiempo de seguridad y contraste con tiempos reales históricos.

---

# Problema de Negocio
Calcular el tiempo de entrega de insumos comprados sin contemplar todos los pasos internos de recepción, inspección y almacenamiento, sin sumar margen de seguridad ante alta variabilidad o sin contrastar los tiempos teóricos contra entradas reales genera órdenes de compra tardías y desabasto.

---

# Objetivo
Definir las reglas, pruebas e integridad de datos para calcular el tiempo de entrega de materiales comprados, aplicar un margen de tiempo de seguridad en casos de alta variabilidad y validar los tiempos teóricos frente a la operación real registrada en entradas de mercancía.

---

# Actores Involucrados
- Comprador: Gestiona tiempos de tránsito de proveedores y asigna un margen de tiempo de seguridad a materiales variables.
- Proveedor: Entrega los materiales comprados dentro de su plazo de tránsito.
- Almacén y Calidad: Ejecutan recepción, inspección de calidad y almacenamiento seguro, y registran entradas de mercancía reales.
- Sistema ERP / Agente Inteligente: Suma componentes de compra, aplica margen de seguridad, registra cambios en auditoría y compara tiempos teóricos contra reales.

---

# Flujo Actual del Proceso
1. Se identifica un artículo de compra con necesidad bruta en el MRP.
2. Se suman el tiempo de tránsito del proveedor más recepción, inspección de calidad y almacenamiento seguro.
3. Si el material tiene alta variabilidad, se suma el margen de tiempo de seguridad al tiempo de entrega base.
4. Se contrastan periódicamente los tiempos teóricos configurados frente a los tiempos reales obtenidos de las entradas de mercancía.

---

# Problemas Identificados
- Retrasos: Variabilidad en entregas o inspecciones que superan el tiempo planeado.
- Errores: Captura de tiempos de entrega negativos, nulos o no numéricos en el registro del artículo.
- Actividades manuales: Revisión manual de retrasos de proveedores y cálculo a mano de tiempos reales vs. teóricos.
- Falta de información: Ausencia de bitácora de auditoría al modificar tiempos de entrega o margen de tiempo de seguridad.
- Cuellos de botella: Inspección de calidad o almacenamiento seguro sin tiempo reservado en el cálculo.

---

# Propuesta de Mejora
Automatizar el cálculo compuesto del tiempo de entrega de compra y el margen de tiempo de seguridad en el MRP. Validar la integridad de los parámetros específicos de abastecimiento (transit_time, receiving_time, inspection_time, storage_time y safety_lead_time) como valores enteros positivos con trazabilidad en bitácora, y emplear un agente inteligente para detectar desviaciones recurrentes entre los tiempos teóricos y las entradas de mercancía reales.

---

# Indicadores de Desempeño (KPIs)
- Desviación de Lead Time de Compra: Diferencia entre tiempo de entrega teórico y real en entradas de mercancía.
- Cumplimiento de Abastecimiento: Porcentaje de compras disponibles a tiempo para la necesidad del MRP.
- Cobertura por Safety Lead Time: Frecuencia con que el margen de seguridad absorbe variaciones sin retrasar la orden.
- Integridad de Parámetros de Compra: Porcentaje de artículos comprados con tiempos de entrega enteros positivos válidos.
- Trazabilidad de Modificaciones: Porcentaje de cambios de tiempos de entrega con registro de usuario, fecha, valor anterior y nuevo.

---

# Plan de Actividades

## Investigación
Revisar la composición del tiempo de entrega para materiales adquiridos y el uso de margen de tiempo de seguridad en el proyecto.

## Levantamiento de Requisitos
Especificar requerimientos funcionales, reglas de negocio y casos de prueba unitarios/funcionales para materiales comprados.

## Modelado del Proceso
Representar en Mermaid el flujo de cálculo de tiempo de entrega de compras y la validación cruzada contra tiempos reales.

## Diseño de Mejoras
Definir restricciones CHECK, bitácora de auditoría y análisis de desviaciones apoyado por agente inteligente.

## Documentación
Subir la documentación, pruebas y evidencias en el repositorio y vincular el Pull Request con este Issue.

---

# Entregables
- Reglas de negocio y requerimientos para tiempo de entrega de compras y margen de tiempo de seguridad
- Casos de pruebas unitarias y funcionales del subproceso de compras
- Diagrama en Mermaid y criterios de integridad/auditoría de datos
- Evidencias en el repositorio

---

# Criterios de Aceptación
- Documentación completa: Alcance delimitado al tiempo de entrega de materiales comprados y su validación contra entradas reales.
- Proceso modelado: Diagrama en Mermaid que separa el cálculo preventivo en el MRP y la validación cruzada post-entrega.
- KPIs definidos: Indicadores de desviación, cumplimiento de abastecimiento, cobertura de safety lead time, integridad de datos y trazabilidad.
- Reglas de negocio documentadas: Cálculo compuesto (tránsito, recepción, calidad, almacenamiento y margen de seguridad), restricciones CHECK en parámetros de compra y casos de prueba.
- Pull Request generado: Evidencias y documentación subidas al repositorio y vinculadas correctamente al Issue.
