# Documentación Técnica: MRP Temporal Scheduling & Lead Time Exception Agent

## 1. Propósito y Alcance
Agente de inteligencia artificial encargado de la planificación temporal, el cálculo de *lead times* de abastecimiento y fabricación interna, y la detección proactiva de desviaciones entre el **Nivel 4 (ERP/MRP)** y el **Nivel 3 (MES/MOM)** bajo la norma **ISA-95 / IEC 62264**. Controla la disponibilidad real de materiales tras la inspección de calidad y bloquea el arranque de órdenes de producción internas cuando existen déficits de inventario.

---

## 2. Arquitectura y Algoritmos Implementados

### 2.1. Método de la Ruta Crítica (CPM - *Critical Path Method*)
* **Modelo Matemático:** Modela el ciclo de cumplimiento de una orden como una red de actividades secuenciales y paralelas que abarcan compras (emisión de orden de compra, tránsito, recepción en almacén, inspección de calidad y liberación a inventario) y producción interna (ensamble, pruebas funcionales y empaque).
* **Cálculo de Inicio Más Temprano (*Early Start* - $ES$):** Identifica los materiales con déficit de inventario y determina el instante en que el 100% de los insumos críticos estarán liberados y aprobados por calidad:
  $$ES_{\text{ensamble}} = \max \left( T_{\text{pedido}}, \max_{k \in \text{Faltantes}} \left( T_{\text{liberación\_calidad}, k} \right) \right)$$
* **Métricas de Lead Time Calculadas:**
  * **Lead Time de Materiales ($LT_{\text{mat}}$):**
    $$LT_{\text{mat}} = T_{\text{disponible\_producción}} - T_{\text{emisión\_OC}}$$
  * **Lead Time de Producto Interno ($LT_{\text{interno}}$):**
    $$LT_{\text{interno}} = T_{\text{liberación\_PT}} - T_{\text{inicio\_ensamble}}$$
  * **Lead Time Total de la Orden ($LT_{\text{total}}$):**
    $$LT_{\text{total}} = T_{\text{liberación\_PT}} - T_{\text{creación\_orden\_venta}}$$

### 2.2. Evaluación de Restricciones Temporales (CSP) y *Backward/Forward Scheduling*
* **Monitoreo de Órdenes Abiertas (RN-05 / RN-06):** Evalúa continuamente la restricción temporal:
  $$T_{\text{actual}} \le T_{\text{estimada\_disponibilidad}}$$
  Si la restricción se viola sin que exista aprobación de calidad, el agente marca la orden como `RETRASADO`, calcula el tiempo transcurrido y evita asignar un *lead time* real definitivo hasta el cierre formal del proceso.
* **Cálculo de Holgura (*Slack*) y Reprogramación:** Si existe una fecha compromiso de entrega $T_{\text{compromiso}}$, calcula la holgura disponible:
  $$\text{Holgura} = T_{\text{compromiso}} - (ES_{\text{ensamble}} + LT_{\text{interno}})$$
  Valores negativos detonan alertas de reprogramación hacia adelante (*Forward Rescheduling*) en el MRP.

---

## 3. Especificación de Métodos e Interfaces (API)

| Método | Parámetros de Entrada | Retorno | Reglas / Casos de Prueba Cubiertos |
| :--- | :--- | :--- | :--- |
| `__init__` | `inventario_actual: Dict[str, int]`, `tiempo_interno_horas: float = 7.5` | Instancia del agente | Inicializa el estado de inventario disponible y tiempos estándar de piso. |
| `_horas_entre` | `inicio: str`, `fin: str` (ISO 8601) | `float` (Horas) | **RN-03, PU-01, PU-03** (Valida coherencia cronológica). |
| `registrar_orden_compra` | `oc_id: str`, `codigo_material: str`, `cantidad: int`, `fecha_emision: str`, `lead_time_estimado_horas: float` | `dict` (Orden de Compra) | **RF-02, RF-03, RN-01, PU-06** |
| `procesar_recepcion_y_calidad` | `oc_id: str`, `fecha_recepcion: str`, `fecha_aprobacion_calidad: Optional[str]`, `fecha_disponible_inventario: Optional[str]` | `dict` (OC actualizada) | **RF-03, RF-04, RN-02, RN-03, RN-04, PU-01, PU-02, PU-03, PU-05, PF-01** |
| `auditar_ordenes_abiertas_csp` | `timestamp_actual: str` | `List[dict]` (Alertas) | **RF-06, RN-05, RN-06, PU-04, PF-03** |
| `planificar_orden_produccion_cpm` | `op_id: str`, `requerimientos_mrp: Dict[str, int]`, `fecha_creacion_pedido: str`, `fecha_entrega_comprometida: Optional[str]` | `dict` (Plan CPM) | **RF-04, RF-05, RN-08, PF-02, PF-06** |

---

## 4. Estados del Ciclo de Vida Gestionados

### 4.1. Ciclo de Abastecimiento (Órdenes de Compra)
1. `EN_TRANSITO`: Orden emitida al proveedor con fecha estimada de disponibilidad calculada.
2. `EN_REVISION`: Material recibido físicamente en almacén (`Nivel 3`), pero pendiente de inspección y liberación de calidad (**RN-04 / PU-05**). No se suma al inventario disponible.
3. `DISPONIBLE`: Material aprobado por calidad y liberado para producción; se calcula su `lead_time_real_horas` y `desviacion_horas`.
4. `RETRASADO`: Orden abierta cuya fecha actual supera la fecha estimada de disponibilidad (**RN-06 / PF-03**).
5. `CANCELADA`: Orden anulada que permanece en historial pero se excluye de promedios de *lead time* (**RN-07**).

### 4.2. Ciclo de Fabricación Interna (Órdenes de Producción)
1. `BLOQUEADA_POR_FALTANTES`: Existen materiales con stock insuficiente y sin orden de compra programada (**RN-08 / PF-06**).
2. `EN_ESPERA_DE_MATERIAL_CRITICO`: Existen faltantes cubiertos por órdenes de compra activas; el inicio de ensamble queda condicionado a la ruta crítica de abastecimiento.
3. `LISTA_PARA_PRODUCCION`: El 100% de los materiales requeridos están disponibles y aprobados en inventario.

---

## 5. Manejo de Excepciones y Validaciones de Integridad

* **`ValueError` (Coherencia Cronológica - RN-03 / PU-03):** Rechaza cualquier registro donde la fecha de recepción, liberación de calidad o disponibilidad sea cronológicamente anterior a la fecha de emisión o a la etapa precedente.
* **`ValueError` (Unicidad de Identificador - RN-01 / PU-06):** Impide registrar dos órdenes de compra con el mismo identificador único (`oc_id`), conservando intacto el registro original.
* **Control de Disponibilidad Real (RN-04):** Evita que una recepción física en almacén incremente el inventario utilizable si `fecha_aprobacion_calidad` o `fecha_disponible_inventario` son nulas.
* **Bloqueo Preventivo en Piso (RN-08):** Impide liberar órdenes de producción internas cuando existe déficit de insumos, detallando los materiales faltantes y sus cantidades exactas.