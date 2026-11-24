# SKU Sentinel & Data Steward

**Autor:** Eduardo Gabriel Morquecho Medina — **Matrícula:** 175805
**Materia:** Inteligencia Artificial 1 — **Tema:** Item Master
**Issue:** #265 · **Rama:** `feature/175805`

Agente inteligente que protege la calidad del catálogo maestro de artículos (`Item_Master`) del Simulador ERP. Actúa en tres fases: evita altas duplicadas, valida la integridad de los datos y recomienda sustitutos cuando un componente crítico se agota.

## Problema que resuelve

- Un mismo componente puede darse de alta dos veces con nombres distintos (por ejemplo, "Memoria Kingston Fury 16 GB DDR5" y "RAM DDR5 16GB Kingston Fury").
- Pueden entrar datos inconsistentes: precio menor al costo, unidad de medida inválida o un componente crítico sin stock de seguridad.
- Cuando un componente crítico se agota no hay un mecanismo automático que proponga un reemplazo compatible.

## Funcionamiento

| Fase | Qué hace | Técnica de IA | Archivo |
|---|---|---|---|
| 1. Deduplicación y clasificación | Compara la estructura del SKU nuevo (categoría, marca, modelo, capacidad, tipo) contra el catálogo. Si coincide, bloquea el alta y sugiere el SKU existente. Sugiere categoría a partir de la descripción y advierte descripciones muy parecidas. | Equivalencia estructural y reglas | `src/fase1_deduplicacion.py` |
| 2. Validación de integridad | Verifica `ItemType`, `UnitOfMeasure`, `ListPrice >= StandardCost` y `SafetyStock > 0` en críticos. Valida tipo y capacidad como un problema de satisfacción de restricciones. | CSP: consistencia de nodo y AC-3 | `src/fase2_validacion.py` |
| 3. Sustitutos y ABC | Si un componente crítico no tiene existencias, busca en el grafo un reemplazo de la misma categoría, con stock y compatible con la misma Motherboard. Clasifica los artículos en A, B o C por valor de consumo anual. | BFS y Greedy Best-First Search | `src/fase3_sustitutos.py` |

### Detalle de los algoritmos

- **Consistencia de nodo:** cada atributo asignado debe pertenecer al dominio de su categoría (por ejemplo, el tipo de una RAM debe ser DDR4 o DDR5).
- **AC-3:** poda los dominios de `tipo` y `capacidad` con una restricción binaria por categoría. Si un dominio queda vacío, la combinación es inválida. Si falta un atributo, AC-3 infiere qué valores siguen siendo posibles.
- **BFS:** recorre el grafo `(:Item)-[:COMPATIBLE_WITH]->(:Item)` por niveles y devuelve el sustituto con menos saltos. Si hay empate, elige el más parecido según la heurística.
- **Greedy Best-First:** expande siempre el nodo con menor `h(n)`, donde `h(n)` suma una penalización por categoría distinta, grupo de sustitutos distinto, diferencia relativa de capacidad y diferencia relativa de precio.
- **ABC:** ordena por `DemandaAnual x StandardCost`. Clase A hasta el 80 % acumulado, B hasta el 95 % y C el resto.

### Mejora propuesta al esquema de datos

Agregar a `Item_Master` el objeto `atributosTecnicos` (`marca`, `modelo`, `capacidad`, `tipo`) y los campos `Category` y `SubstituteGroup`. Así el agente compara atributos exactos en lugar de depender del texto libre, y las relaciones del grafo se crean de forma automática.

## Estructura

```
item/175805/
├── README.md
├── datos/items.json                    Datos de ejemplo: 16 artículos, compatibilidades y altas de prueba
├── src/
│   ├── fase1_deduplicacion.py
│   ├── fase2_validacion.py
│   ├── fase3_sustitutos.py
│   ├── main.py                         Demostración de las tres fases
│   └── neo4j_carga.py                  Genera y carga el grafo en Neo4j
├── cypher/
│   ├── 01_carga_grafo.cypher           Generado por neo4j_carga.py
│   └── 02_consultas_agente.cypher      Consultas de cada fase
├── pruebas/test_sku_sentinel_175805.py
└── evidencias/                         Salidas de ejecución y capturas
```

## Cómo ejecutarlo

El núcleo del agente usa solo la biblioteca estándar de Python 3 (no necesita base de datos).

```bash
# Desde la raíz del repositorio
python item/175805/src/main.py          # demostración de las tres fases
python -m pytest item/175805/pruebas    # 18 pruebas
```

### Con Neo4j

```bash
pip install neo4j
export NEO4J_PASSWORD="tu_password"     # opcional: NEO4J_URI y NEO4J_USER
python item/175805/src/neo4j_carga.py --cargar
```

Después se pueden ejecutar las consultas de `cypher/02_consultas_agente.cypher` en Neo4j Browser. La consulta de sustitutos recibe el parámetro `$codigo`, por ejemplo `:param codigo => 'SSD-SAM980-1TB'`.

## Resultados de la demostración

Salida completa en `evidencias/salida_ejecucion.txt`.

| Caso | Resultado |
|---|---|
| Alta "RAM DDR5 16GB Kingston Fury" | **Bloqueada**: duplicado de `RAM-KF-16-D5` |
| Alta SSD con precio menor al costo, unidad `PAQUETE` y SafetyStock 0 | **Rechazada** con 3 violaciones |
| Alta RAM DDR4 de 64 GB | **Rechazada** por AC-3 (combinación inválida) |
| Alta RAM Kingston Fury 64 GB DDR5 | **Aprobada** |
| `RAM-KF-16-D5` sin existencias | Sustituto: `RAM-CV-16-D5` (no sugiere la DDR4, que no es compatible con la placa) |
| `SSD-SAM980-1TB` sin existencias | Sustituto: `SSD-WD770-1TB` (BFS exploró 14 nodos; Greedy, 3) |

## Alcance y limitaciones

- Los 16 artículos y las reglas de dominio por categoría son **datos de ejemplo** de una PC gamer. No son el Item Master real del simulador.
- Las consultas Cypher y la carga a Neo4j deben ejecutarse en una instancia propia para generar las capturas de evidencia.
