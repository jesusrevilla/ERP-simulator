# Prueba Funcional: `Integridad_de_las_transacciones`

**Proyecto:** ERP MRP Demo  
**Empresa:** TechAssembly S.A.  
**Producto Principal:** Gaming PC  
**Módulo bajo prueba:** `Integridad_de_las_transacciones`  
**Entorno de ejecución:** GitHub Actions (`pytest`) + PostgreSQL + MongoDB + Neo4j

---

## 1. Objetivo de la prueba funcional

Verificar que las operaciones críticas del ERP—especialmente la ejecución del asistente MRP, el registro de recomendaciones (Solicitudes/Órdenes de Compra y Órdenes de Fabricación) y la actualización de inventarios/estados—se ejecuten de forma **atómica, consistente y trazable** entre **PostgreSQL**, **MongoDB** y **Neo4j**.

Si ocurre un fallo parcial (por ejemplo, error de validación, pérdida de conexión o excepción a mitad del proceso), **ninguna base de datos debe quedar con cambios a medias** (rollback / compensación) y la **Lista de Materiales (BOM)** del **Gaming PC** debe mantenerse íntegra.

---

## 2. Contexto del ERP y datos de prueba

* **Empresa:** `TechAssembly S.A.`
* **Producto terminado (`Fabricar`):** `Gaming PC`
* **Componentes (`Comprar` por defecto, salvo casos de prueba específicos):**
  * `CPU Ryzen 7`
  * `Motherboard B650`
  * `RAM 16GB DDR5`
  * `SSD 1TB NVMe`
  * `Power Supply 750W`
  * `Graphics Card RTX`

### Responsabilidad de cada base de datos en una transacción MRP
* **PostgreSQL:** Datos maestros, órdenes/solicitudes de compra y fabricación, movimientos transaccionales y control ACID.
* **MongoDB:** Bitácoras/logs de ejecución del MRP, snapshots de corrida o documentos de auditoría del proceso.
* **Neo4j:** Grafo de dependencias / BOM (`Gaming PC` conectado a `CPU Ryzen 7`, `Motherboard B650`, `RAM 16GB DDR5`, `SSD 1TB NVMe`, `Power Supply 750W` y `Graphics Card RTX`) y relaciones de aprovisionamiento.

---

## 3. Alcance de casos de prueba funcionales

### PF-01: Commit atómico en corrida MRP exitosa
* **Precondición:** Esquema ERP creado, datos semilla cargados (`Gaming PC` y sus 6 componentes) y servicios PostgreSQL, MongoDB y Neo4j activos.
* **Acción:** Ejecutar el asistente MRP para una demanda de `Gaming PC` donde existan artículos configurados como `Fabricar` y otros como `Comprar`.
* **Resultado esperado:**
  * Se generan recomendaciones de **Órdenes de Fabricación** para artículos `Fabricar` y **Solicitudes/Órdenes de Compra** para artículos `Comprar`.
  * El registro transaccional queda confirmado en **PostgreSQL**, el log/auditoría de ejecución queda registrado en **MongoDB** y las relaciones/estados del grafo en **Neo4j** coinciden con la corrida.

### PF-02: Rollback ante fallo forzado a mitad de la transacción
* **Precondición:** Estado base limpio tras carga de datos semilla.
* **Acción:** Iniciar una ejecución MRP que genere recomendaciones para los componentes del `Gaming PC` (`CPU Ryzen 7`, `Motherboard B650`, `RAM 16GB DDR5`, `SSD 1TB NVMe`, `Power Supply 750W`, `Graphics Card RTX`) e inyectar un fallo simulado antes de cerrar la transacción (por ejemplo, restricción violada, error de escritura o excepción en uno de los almacenes de datos).
* **Resultado esperado:**
  * Se revierte la transacción en **PostgreSQL** (no quedan órdenes o movimientos parciales).
  * No se persiste una corrida marcada como completada de forma inconsistente en **MongoDB** (o se registra explícitamente como `ABORTED`/`ROLLED_BACK` sin mutaciones parciales de estado).
  * **Neo4j** conserva intacta la estructura BOM del `Gaming PC` sin nodos o relaciones huérfanas de la corrida fallida.

### PF-03: Prevención de inconsistencia entre aprovisionamiento (`Comprar` vs. `Fabricar`) y registros generados
* **Precondición:** Artículos configurados explícitamente como `Comprar` y `Fabricar` dentro del catálogo de `TechAssembly S.A.`.
* **Acción:** Ejecutar el asistente MRP y validar las recomendaciones generadas frente al método de aprovisionamiento de cada artículo (`Gaming PC` y componentes).
* **Resultado esperado:**
  * Todo artículo `Comprar` solo produce recomendaciones de **Solicitud/Orden de Compra** (nunca Orden de Fabricación).
  * Todo artículo `Fabricar` solo produce recomendaciones de **Orden de Fabricación**.
  * No existen registros duplicados ni huérfanos entre tablas relacionales, documentos de auditoría y grafo.

### PF-04: Idempotencia / reintento seguro tras un error
* **Precondición:** Una corrida previa falló y aplicó rollback (PF-02).
* **Acción:** Reejecutar `pytest` / el flujo MRP con los mismos parámetros válidos.
* **Resultado esperado:**
  * El sistema se recupera sin requerir recrear manualmente el esquema ni recargar toda la semilla, completando la transacción de forma limpia.

---

## 4. Integración en el workflow de GitHub Actions

El pipeline ejecuta automáticamente:
1. **Espera servicios:** Verifica disponibilidad de `PostgreSQL`, `MongoDB` y `Neo4j`.
2. **Crea esquema ERP:** Inicializa tablas, índices, colecciones y restricciones/índices del grafo.
3. **Carga datos semilla:** Inserta `TechAssembly S.A.`, `Gaming PC` y los componentes (`CPU Ryzen 7`, `Motherboard B650`, `RAM 16GB DDR5`, `SSD 1TB NVMe`, `Power Supply 750W`, `Graphics Card RTX`).
4. **Ejecuta validación MRP:** Verifica reglas de aprovisionamiento (`Comprar` vs. `Fabricar`) y recomendaciones.
5. **Ejecuta pruebas unitarias:** Corre `pytest` (incluyendo las pruebas del módulo `Integridad_de_las_transacciones`).

---

## 5. Criterios de aceptación

* `pytest` finaliza con estado **0 (passed)** en el entorno de GitHub Actions.
* Ningún caso de prueba deja datos residuales corruptos que afecten pruebas posteriores.
* Tras un fallo simulado, el estado final en **PostgreSQL**, **MongoDB** y **Neo4j** es idéntico al estado previo a la operación fallida (o refleja un aborto limpio y consistente).