# Definición de KPIs (Módulo BOM – TechAssembly S.A.)
**Matrícula:** 179761 | **Issue:** #244
## 1. Definición de KPIs

Los siguientes indicadores miden el impacto de eliminar la duplicidad de componentes y automatizar la validación de la **Bill of Materials (BOM)** en **TechAssembly S.A.** (ensamble de **Gaming PC**):

| Indicador (KPI) | Fórmula de Cálculo | Fuente en el ERP | Línea Base | Meta |
| :--- | :--- | :--- | :--- | :--- |
| **Tasa de BOMs Libres de Duplicados** | `(BOMs sin SKUs repetidos por nivel / Total de BOMs) × 100` | PostgreSQL (`bom_detalle`) | 85 % | 100 % |
| **Tiempo de Validación y Depuración de BOM** | `Σ Minutos invertidos en revisar/corregir duplicados / Total de BOMs` | MongoDB (Auditoría) | 35 min | 0 min |
| **Desviación del *Cost Roll-up* por Duplicidad** | `((Costo estándar calculado - Costo real unitario) / Costo real unitario) × 100` | PostgreSQL (`cost_rollup`) | +18 % | 0 % |
| **Exactitud de Explosión MRP** | `(Requerimientos netos exactos / Total de corridas MRP) × 100` | Neo4j / Motor MRP | 88 % | 100 % |
| **Sobrestock por Compras Duplicadas** | `(Unidades adquiridas en exceso por duplicidad / Total comprado) × 100` | Abastecimiento / MRP | 12 % | 0 % |
| **Efectividad de Pruebas Automatizadas (CI/CD)** | `(Pruebas de unicidad y MRP aprobadas en pytest / Total de pruebas) × 100` | GitHub Actions (`pytest`) | 0 % | 100 % |

---
## 2. Indicadores de Desempeño Operativo y Logístico (KPIs Generales)

De manera complementaria, se establecen métricas globales para evaluar el rendimiento integral del ciclo de vida de la BOM, el surtimiento en almacén y la planeación del MRP:

| Categoría | Indicador (KPI) | Fórmula / Medición | Meta Esperada |
| :--- | :--- | :--- | :--- | 
| **Tiempo de ciclo** | Tiempo de creación y validación de BOM | Tiempo promedio desde el alta de ingeniería hasta la liberación de la BOM sin errores | < 15 minutos |
| **Nivel de servicio** | Exactitud de *Picking List* (OTIF interno) | $(\text{Órdenes surtidas sin discrepancias} / \text{Total de OP}) \times 100$ | 99.5 % |
| **Tiempo de entrega** | *Lead Time* de preparación de lote MRP | Tiempo desde la recepción del pedido del cliente hasta la emisión de órdenes de compra/surtimiento | 3 días | < 1 hora (automatizado) |
| **Costo operativo** | Precisión del *Cost Roll-up* y reducción de sobrecompras | % desviación entre costo estándar BOM y costo real de ensamble | < 1 %  |
