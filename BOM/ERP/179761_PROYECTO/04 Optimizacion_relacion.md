# Optimización: Propuestas de Mejora mediante ERP y Automatización
**Matrícula:** 179761 | **Issue:** #244
* **Validación Transaccional en el ERP (Prevención y Consolidación):** Implementar una restricción de unicidad compuesta `UNIQUE (id_padre, id_componente, nivel)` en PostgreSQL combinada con lógica de consolidación automática (`ON CONFLICT DO UPDATE`). Si un analista agrega dos veces el *CPU Ryzen 7* o la *RAM 16GB DDR5* en el mismo nivel de la *Gaming PC*, el sistema bloquea la fila redundante o unifica ambas cantidades en un solo registro.
* **Sincronización Políglota Automatizada:** Conectar el flujo transaccional para que cada inserción o consolidación en PostgreSQL actualice la arista única (`MERGE`) en **Neo4j** (garantizando un grafo acíclico para el MRP) y registre un documento de auditoría inmutable en **MongoDB**.
* **Recálculo Automático de Costos (*Cost Roll-up*):** Disparar automáticamente el cálculo acumulado del costo estándar de Nivel 0 cada vez que se inserta un componente único o se consolida una cantidad, eliminando hojas de cálculo manuales en Finanzas.

---

# Relación con las Otras Materias – Módulo BOM (TechAssembly S.A.)

## 1. Relación con Bases de Datos

### 1.1 Control de Unicidad y Consolidación de Componentes
* **Proceso:** Unicidad y consolidación de componentes en BOM (`RN-01`, `RN-02`).
* **Información necesaria:** Identificador del producto padre (`id_padre`), identificador del componente (`id_componente`), nivel jerárquico (`nivel`), cantidad y unidad de medida (`uom`).
* **Consulta / Acción requerida:**
  * **PostgreSQL:** Inserción con llave única `UNIQUE (id_padre, id_componente, nivel)` y suma automática mediante `ON CONFLICT DO UPDATE`.
  * **Neo4j:** Creación o actualización de arista única mediante `MERGE (p)-[r:REQUIRES]->(c)` sin duplicar relaciones.

### 1.2 Validación de Catálogo, Dominio y Cost Roll-up
* **Proceso:** Validación de existencia en *Item Master*, cantidades positivas y recálculo de costos (`RN-05`, `RN-06`, `RN-07`, `RN-08`, `RN-11`).
* **Información necesaria:** Estatus del artículo (`ACTIVO`), tipo de insumo (discreto o consumible), unidad base del inventario y costo unitario de cada componente.
* **Consulta / Acción requerida:**
  * **PostgreSQL:** Validación mediante claves foráneas (`FOREIGN KEY`), restricción `CHECK (cantidad > 0)` y consulta de agregación `SUM(cantidad * costo_unitario)` para actualizar el costo acumulado del Nivel 0.

### 1.3 Auditoría de Consolidaciones y Control de Versiones (ECO)
* **Proceso:** Trazabilidad de duplicados bloqueados/consolidados e inmutabilidad de revisiones congeladas (`RN-04`, `RN-10`).
* **Información necesaria:** Usuario responsable, fecha/hora (`timestamp`), revisión de BOM (`Rev A`, `Rev B`), SKU afectado, cantidad previa, cantidad agregada y cantidad final.
* **Consulta / Acción requerida:**
  * **MongoDB:** Inserción de bitácora inmutable (`db.bom_auditoria.insertOne(...)`) y consulta de historial de cambios por BOM (`db.bom_auditoria.find({ id_bom: ... })`).

---

## 2. Relación con Inteligencia Artificial (Agentes Inteligentes)

### 2.1 Agente Validador de Captura y Consolidación
* **Proceso:** Unicidad y consolidación de componentes en BOM.
* **Regla de Negocio:** Un componente no puede registrarse dos veces bajo el mismo producto padre y nivel; si ya existe, las cantidades deben consolidarse o bloquearse notificando al usuario (`RN-01`, `RN-02`, `RN-03`, `RN-04`).
* **Entonces (Acción del Agente):** Valida la captura en tiempo real, calcula el *Cost Roll-up*, fusiona los registros sumando sus cantidades (consolidación), registra la traza en **MongoDB** y envía una notificación explicativa al usuario.

### 2.2 Agente de Integridad de Catálogo y Dominio
* **Proceso:** Validación de artículos, unidades de medida e indivisibilidad de hardware.
* **Regla de Negocio:** Solo se admiten componentes activos en el *Item Master*, con unidad de medida compatible, cantidad mayor a cero y valores enteros para piezas discretas (`RN-05`, `RN-06`, `RN-07`, `RN-08`).
* **Entonces (Acción del Agente):** Verifica el maestro de artículos antes de guardar, bloquea cantidades decimales en hardware indivisible (ej. procesadores o memorias RAM) y sugiere la unidad de medida correcta.

### 2.3 Agente Topológico de Grafos
* **Proceso:** Detección de referencias circulares en estructuras multinivel.
* **Regla de Negocio:** La jerarquía de materiales debe ser un grafo dirigido acíclico; ningún componente puede contener directa o indirectamente a su propio producto padre (`RN-09`).
* **Entonces (Acción del Agente):** Ejecuta un recorrido en profundidad en **Neo4j** antes de confirmar la estructura; si detecta un bucle ($A \rightarrow B \rightarrow A$), rechaza la operación y señala los nodos en conflicto.

### 2.4 Agente Gestor de Cambios de Ingeniería (ECO)
* **Proceso:** Inmutabilidad de BOM frente a Órdenes de Producción activas.
* **Regla de Negocio:** Una BOM vinculada a una Orden de Producción en estado *Liberada* o *En Proceso* queda congelada y exige crear una nueva revisión para cualquier cambio (`RN-10`).
* **Entonces (Acción del Agente):** Bloquea la edición directa sobre la revisión activa (`Rev A`), clona automáticamente la estructura hacia un borrador (`Rev B`) con la modificación solicitada y notifica a Planeación MRP.

### 2.5 Agente Auditor Pre-MRP
* **Proceso:** Recálculo de costos y validación previa a la explosión de materiales.
* **Regla de Negocio:** Toda actualización en la BOM recalcula el costo acumulado de Nivel 0 y garantiza que los requerimientos netos del MRP carezcan de anomalías (`RN-11`).
* **Entonces (Acción del Agente):** Compara el costo y las cantidades de la BOM contra patrones históricos de ensamble; si detecta sobrecostos o cantidades atípicas, detiene la emisión de órdenes de compra y solicita confirmación.
