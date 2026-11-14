# Documentación Técnica: BOM Graph & Explosion Reasoning Agent

## 1. Propósito y Alcance
Agente de inteligencia artificial especializado en el razonamiento estructural, validación de integridad jerárquica y cálculo de requerimientos brutos de materiales dentro del módulo **Bill of Materials (BOM)** del ERP. Opera sobre estructuras multinivel (`Nivel 0` Producto Terminado, `Nivel 1` Subensambles, `Nivel N` Materias Primas) y garantiza que las explosiones del MRP y consultas de ingeniería cumplan con las reglas de vigencia, aciclicidad, conversión de unidades y redondeo discreto.

---

## 2. Arquitectura y Algoritmos Implementados

### 2.1. Validación de Grafo Acíclico Dirigido (DAG) mediante DFS con Coloración de 3 Estados
* **Modelo Matemático:** Representa el catálogo maestro y las relaciones padre-hijo como un grafo dirigido $G = (V, E)$, donde los vértices $V$ representan artículos (`PT`, `SE`, `MP`) y las aristas ponderadas $E$ representan las relaciones de ensamble.
* **Funcionamiento:** Asigna tres estados a cada nodo durante el recorrido en profundidad (*Depth-First Search*):
  * `0` (**Blanco**): Nodo no visitado.
  * `1` (**Gris**): Nodo actualmente en la pila de recursión.
  * `2` (**Negro**): Nodo y todos sus descendientes completamente procesados.
* **Detección de Ciclos:** Si durante la exploración de vecinos una arista apunta a un nodo en estado `1`, se identifica una referencia circular directa ($A \to A$) o indirecta ($A \to B \to C \to A$) y se aborta la operación antes de persistir o aprobar.
* **Complejidad Computacional:** Tiempo $O(|V| + |E|)$ y espacio auxiliar $O(|V|)$ en la pila de recursión.

### 2.2. Explosión Recursiva *Top-Down* con Memoización (Programación Dinámica)
* **Funcionamiento:** Descompone un artículo padre (`PT` o `SE`) en sus materias primas hoja (`MP`), multiplicando las proporciones de consumo por nivel. Almacena en caché (`_memo_explosion`) los subárboles ya resueltos indexados por `(sku, fecha_demanda)` para evitar recomputaciones en componentes compartidos entre distintas ramas.
* **Fórmula Matemática de Necesidad Bruta (RN08):**
  $$Q_{\text{bruta}}(m) = \left\lceil D \cdot \sum_{p \in \text{Rutas}(m)} \prod_{(u,v) \in p} \frac{q_{uv}}{B_u \cdot (1 - \text{merma}_{uv})} \right\rceil$$
  Donde:
  * $D$: Cantidad demandada del producto padre.
  * $q_{uv}$: Cantidad estándar del componente hijo $v$ en la línea de detalle.
  * $B_u$: Cantidad base definida en la cabecera del BOM del padre $u$.
  * $\text{merma}_{uv} \in [0, 1)$: Factor decimal de desperdicio o *scrap*.
* **Regla de Redondeo (PU09):** El operador techo $\lceil \cdot \rceil$ se aplica **únicamente al finalizar** la acumulación de todas las ramas para artículos discretos (`es_discreto = True`), evitando sobreestimaciones por redondeos intermedios.

---

## 3. Especificación de Métodos e Interfaces (API)

| Método | Parámetros de Entrada | Retorno | Reglas / Casos de Prueba Cubiertos |
| :--- | :--- | :--- | :--- |
| `__init__` | `items_master: Dict[str, dict]`, `bom_headers: List[dict]`, `bom_details: List[dict]` | Instancia del agente | Inicializa catálogos en memoria y estructura de caché. |
| `_build_adjacency_graph` | `include_drafts: bool = True` | `Dict[str, List[str]]` | Construye la lista de adyacencia $G=(V,E)$ filtrando por estado (`ACTIVO` / `BORRADOR`). |
| `validar_grafo_aciclico_dag` | `proposed_parent: str = None`, `proposed_child: str = None` | `Tuple[bool, str]` | **RN03, RN-13, PU02, PU-BOM-019, PU-BOM-020, PF02, PF-BOM-008** |
| `seleccionar_version_vigente` | `parent_sku: str`, `fecha_demanda: datetime` | `dict` (Cabecera BOM) | **RN01, RN06, RN07, RN-08, RN-15, PU08, PU-BOM-001, PF05** |
| `_explotar_recursivo` | `sku: str`, `fecha_demanda: datetime`, `visitados: set` | `Dict[str, float]` | **RF07, RN04, RN08, RN-10, PU04, PU05, PU06** |
| `explotar_bom` | `parent_sku: str`, `cantidad_demanda: float`, `fecha_demanda: str` | `dict` (Payload JSON) | **RF03, RF07, RN08, PU09, PF03, PF-BOM-006, PF-BOM-010** |

---

## 4. Integración con Eventos ISA-95 y Dominio

* **Eventos Consumidos:**
  * `EVT-MRP-201` (*ExplosionMateriales_MRP*): Solicitud de cálculo de requerimientos brutos ante un pedido de producción.
  * `BOM.WhereUsedQueried`: Consultas inversas de impacto ante desabasto o cambios de ingeniería (ECO).
* **Eventos Emitidos:**
  * `BOM.VersionResolved` (`MES->ERP` / Verbo `Get`): Confirma la versión exacta seleccionada para la fecha de demanda en cada nivel.
  * `BOM.Exploded` (`ERP->MES` / Verbo `Process`): Entrega la lista aplanada (*Summarized BOM*) de materias primas con cantidades brutas finales y costo estimado.
  * `BOM.ExplosionRejected` (`ERP->MES` / Verbo `Respond`): Detiene la planificación sin emitir requerimientos parciales si falta una versión aprobada en cualquier subensamble.
  * `BOM.ValidationFailed` (`ERP internal`): Reporta ciclos DAG, mermas fuera de rango o intentos de crear una lista de materiales sobre una Materia Prima (`MP`).

---

## 5. Manejo de Excepciones y Controles de Integridad

* **`ValueError`:** Se lanza ante:
  * Cantidades de demanda $\le 0$.
  * Porcentajes de merma fuera del intervalo semiabierto $[0, 1)$.
  * Artículos inexistentes o marcados como inactivos (`activo = False`).
  * Intentos de asignar una Materia Prima (`tipo_item == 'MP'`) como producto padre.
  * Detección de ciclos directos o indirectos en la estructura.
* **`LookupError`:** Se lanza cuando no existe ninguna versión en estado `ACTIVO` cuyo intervalo de vigencia `[fecha_inicio, fecha_fin)` cubra la `fecha_demanda` solicitada.
* **`RuntimeError`:** Se lanza ante conflictos de concurrencia donde coexisten dos o más versiones activas superpuestas cronológicamente para un mismo `parent_sku`.
* **`RecursionError`:** Salvaguarda adicional en tiempo de ejecución durante el recorrido recursivo para prevenir bucles infinitos.