# Prueba Funcional: Gestión de Almacenes (Warehouses) y MRP

## Identificación de la Prueba
* **ID de Prueba:** `PF-WH-01`
* **Módulo:** Almacenes (`Warehouses`) & Planificación de Requerimientos (`MRP`)
* **Empresa:** TechAssembly S.A.
* **Producto Evaluado:** Gaming PC (Ensamble) y sus componentes

---

## Objetivo
Validar que el motor MRP del simulador ERP consulte y calcule correctamente la disponibilidad de stock por almacén en **PostgreSQL**, respete la estructura de componentes (BOM) en **Neo4j**, registre el historial/auditoría en **MongoDB** y genere recomendaciones de compra únicamente para los almacenes seleccionados y habilitados para MRP.

---

## Precondiciones (Datos Semilla)
Antes de ejecutar la validación, el esquema ERP (`seed`) debe contar con la siguiente configuración en **PostgreSQL** y **Neo4j**:

1. **Almacenes configurados:**
   * **`WH-PROD` (Almacén de Ensamble / Producción):** Habilitado para MRP (`include_in_mrp = True`).
   * **`WH-CENT` (Almacén Central):** Habilitado para MRP (`include_in_mrp = True`).
   * **`WH-QUAR` (Almacén de Cuarentena / RMA):** Excluido de MRP (`include_in_mrp = False`).

2. **Inventario inicial de componentes (para ensamble de *Gaming PC*):**

| Componente | `WH-PROD` (Ensamble) | `WH-CENT` (Central) | `WH-QUAR` (Cuarentena) |
| :--- | :---: | :---: | :---: |
| **CPU Ryzen 7** | `0` | `10` | `5` |
| **Motherboard B650** | `2` | `8` | `0` |
| **RAM 16GB DDR5** | `4` | `20` | `2` |
| **SSD 1TB NVMe** | `0` | `15` | `0` |
| **Power Supply 750W** | `1` | `12` | `0` |
| **Graphics Card RTX** | `0` | `5` | `3` |

3. **Demanda registrada:** Una Orden de Venta activa por **`5` unidades de `Gaming PC`** asignada al almacén de salida **`WH-PROD`**.

---

## Pasos de Ejecución

### Escenario A: Corrida de MRP aislada por Almacén (`WH-PROD`)
1. Iniciar el cálculo de MRP seleccionando el producto terminado **`Gaming PC`**.
2. Configurar el alcance de inventario en modo **Por Almacén (`Run by Warehouse`)** filtrando exclusivamente **`WH-PROD`**.
3. Ejecutar el algoritmo de explosión de materiales (BOM desde **Neo4j**) y cruce de inventario (desde **PostgreSQL**).
4. Inspeccionar las recomendaciones de abastecimiento generadas y el log de ejecución en **MongoDB**.

### Escenario B: Corrida de MRP Consolidada (`WH-PROD` + `WH-CENT`)
1. Ejecutar nuevamente el cálculo de MRP para las mismas **`5` unidades de `Gaming PC`**.
2. Configurar el alcance de inventario en modo **Consolidado (`Run by Company`)**, incluyendo todos los almacenes activos (`include_in_mrp = True`).
3. Verificar el cálculo de necesidades netas y el aislamiento del almacén **`WH-QUAR`**.

---

## Resultados Esperados (Criterios de Aceptación)

### 1. En el Escenario A (Aislamiento en `WH-PROD`):
* El sistema ignora las existencias de `WH-CENT` y `WH-QUAR`.
* Se generan las siguientes **Recomendaciones de Compra** con destino a **`WH-PROD`**:
  * **CPU Ryzen 7:** `5` unidades (Stock: 0).
  * **Motherboard B650:** `3` unidades (Demanda: 5 - Stock: 2).
  * **RAM 16GB DDR5:** `1` unidad (Demanda: 5 - Stock: 4).
  * **SSD 1TB NVMe:** `5` unidades (Stock: 0).
  * **Power Supply 750W:** `4` unidades (Demanda: 5 - Stock: 1).
  * **Graphics Card RTX:** `5` unidades (Stock: 0).

### 2. En el Escenario B (Consolidado `WH-PROD` + `WH-CENT`):
* El sistema suma el stock disponible entre `WH-PROD` y `WH-CENT` (ej. *CPU Ryzen 7*: `0 + 10 = 10` disponibles; *Graphics Card RTX*: `0 + 5 = 5` disponibles).
* **No se generan recomendaciones de compra**, ya que el inventario consolidado cubre las `5` *Gaming PC*.
* El stock de **`WH-QUAR`** (ej. las 3 *Graphics Card RTX* dañadas) permanece intacto y excluido del cálculo.
* **Integridad y Automatización:** La ejecución registra el documento de resultados en **MongoDB** y pasa la validación automática mediante `pytest` dentro del workflow de **GitHub Actions**.
