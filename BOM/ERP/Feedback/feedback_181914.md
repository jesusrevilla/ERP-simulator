# Auditoría de `BOM/schema.sql` frente a requerimientos y eventos

## 1. Resumen de cumplimiento

| Área | Resultado | Evidencia y límite |
|---|---|---|
| Claves primarias y foráneas | ✅ Sí | PK y FK en catálogos, cabeceras, líneas y órdenes; `RESTRICT` en referencias principales. |
| Unicidad producto + versión | ✅ Sí | `uq_parent_version`. |
| Unicidad componente por versión | ✅ Sí | `uq_bom_componente (bom_id, component_sku)`. |
| Cantidad positiva y merma entre 0 y 1 | ✅ Sí | `CHECK` en cabecera y detalle. |
| Estados posibles | ✅ Parcial | `CHECK` permite cuatro estados, pero no limita las **transiciones**; el documento 181914 usa tres nombres/conceptos. |
| Vigencia sin traslapes para versiones activas | ✅ Sí | Exclusión GiST sobre `tstzrange` con intervalos `[)`; necesita probar concurrencia y publicación atómica. |
| Elegibilidad y actividad de artículos | ❌ No | FK comprueba existencia, no `PT/SE` para padres ni artículo activo para hijos. |
| Compatibilidad de unidades | ❌ No | Unidades existen, pero no se verifica dimensión, conversión ni precisión por artículo. |
| Cantidad entera para artículos discretos | ❌ No | `es_discreto` no condiciona `cantidad`. |
| Detección de ciclos multinivel | ❌ No | No hay función/trigger recursivo. |
| Inmutabilidad de versión aprobada/usada | ❌ No | No hay trigger de bloqueo `UPDATE/DELETE` ni verificación de órdenes. |
| Aprobación válida | ❌ No | Se puede declarar `ACTIVO` con cero líneas o con subensamble sin versión vigente. |
| Clonación y cambio de revisión | ⚠️ Parcial | La estructura permite versiones nuevas, pero no implementa la copia ni la publicación atómica. |
| Concurrencia optimista | ⚠️ Parcial | Existe `version_concurrencia`, pero no hay lógica que la compare/incremente. |
| Explosión BOM y consulta where-used | ❌ No en SQL | No existen consultas/funciones recursivas ni una vista de necesidades acumuladas; podrían residir en la aplicación. |
| Costeo multinivel | ⚠️ Parcial | `costo_estandar` y costo histórico en snapshot existen; no hay función de cost roll-up. |
| Snapshot histórico por orden | ⚠️ Parcial | Hay tabla, pero faltan FK, versionado inequívoco por nivel y protección contra cambios. |
| Auditoría completa y permisos | ❌ No | Usuarios/fechas en cabecera no equivalen a bitácora con valores antes/después ni control de roles. |
| Eventos de ambos JSON | ❌ No verificable | `schema.sql` no incluye outbox/event log ni rutinas para producirlos; pueden implementarse en otra capa. |
| Consumo, lotes, scrap físico y desmontaje | ❌ No en esquema | Campos de eventos de `events_179761.json` sin entidades transaccionales equivalentes. |

## 2. Correcciones prioritarias

### CRÍTICA 1 — Impedir padres de tipo `MP` y componentes inactivos
**Referencias:** `BOM requeriments.md`: RN01; `BOM_Requirements.md`: RF-01.1, RN-01, RN-02, RN-15; `BOM_Requirements_179761.md`: RN-01.  
**Problema:** `bom_cabecera.parent_sku` referencia `articulos`, pero admite materia prima. `bom_detalle.component_sku` admite un artículo inactivo.  
**Acción:** incorporar validación `BEFORE INSERT OR UPDATE` en cabecera para `articulos.tipo_item IN ('PT','SE') AND activo`; en detalle, exigir artículo hijo activo. Garantizar validación ante cambios posteriores del artículo; no basta con validar solo al insertar la BOM. La autorización del tipo de padre puede además reforzarse mediante un diseño referencial específico.

### CRÍTICA 2 — Validación de UOM y discreción
**Referencias:** documento 181914 RN02, PU07; documento general RN-04; documento 179761 RN-02, RN-03.  
**Problema:** una fila puede declarar RAM con unidad `KG` aunque el artículo tenga base `PCS`. `conversiones_uom` permite conversiones entre dimensiones incompatibles y carece de validación de SKU específico.  
**Acción:** validar para cabecera y líneas que la unidad sea la base o que exista conversión aplicable y autorizada; comprobar dimensiones compatibles salvo equivalencia SKU específica autorizada. Validar que para `es_discreto = true` la cantidad convertida a UOM base sea entera (y positiva). Revisar la precisión/unidad mínima. **Detalle SQL importante:** `UNIQUE (uom_origen_id,uom_destino_id,sku_especifico)` permite múltiples registros con `sku_especifico IS NULL` en PostgreSQL sin `NULLS NOT DISTINCT`; usar índices únicos parciales o `UNIQUE NULLS NOT DISTINCT` (PostgreSQL 15+).

### CRÍTICA 3 — Evitar ciclos directos e indirectos
**Referencias:** documento 181914 RN03, PU02, PF02; documento general RF-04.1/RN-13; documento 179761 TU-02.  
**Problema:** se puede guardar `A -> A` o `A -> B -> C -> A`.  
**Acción:** agregar `CHECK`/trigger para autorreferencia directa y una validación con `WITH RECURSIVE` antes de aprobar o persistir, según la especificación elegida. Debe recorrer versiones relevantes, evitar ciclos bajo cambios concurrentes y rechazar la transacción completa.

### CRÍTICA 4 — Proteger BOM aprobadas y vinculadas a órdenes
**Referencias:** documento 181914 RN05, RN09, PU10; documento general RN-14; documento 179761 TU-03.  
**Problema:** un `UPDATE bom_detalle` puede modificar una BOM `ACTIVO`, y un `UPDATE bom_cabecera` puede alterar su estructura histórica. `ON DELETE RESTRICT` por sí solo no impide editar filas.  
**Acción:** triggers `BEFORE UPDATE OR DELETE` en cabecera y detalle; bloquear cambios estructurales de versiones aprobadas/no editables o ya referenciadas por órdenes. Considerar los únicos cambios controlados indispensables para cerrar vigencia/obsoletar. Si una orden conserva snapshot, igualmente debe preservarse la integridad histórica.

### CRÍTICA 5 — Validar aprobación y transiciones
**Referencias:** documento 181914 RN01, RN05–RN07; documento general RN-05, RN-07 y RN-08.  
**Problema:** `estado='ACTIVO'` puede establecerse sin componentes, con ciclos, o con subensambles sin BOM válida. El `CHECK` no impide `OBSOLETO -> ACTIVO`.  
**Acción:** implementar un servicio/procedimiento de publicación transaccional que verifique permisos, al menos una línea, coherencia de padre/componentes/UOM, DAG, disponibilidad de versiones hijas y transiciones válidas. Cerrar la vigencia anterior e iniciar la nueva dentro de una sola transacción. Añadir triggers para bloquear rutas de escritura que evadan este servicio.

### ALTA 6 — Auditoría, permisos y concurrencia
**Referencias:** documento 181914 RF08, RN09, PF06–PF07; eventos `BOM.AccessDenied`, `BOM.AuditRecorded`, `BOM.ConcurrencyConflict`.  
**Problema:** `usuario_creacion`, `usuario_aprobacion`, `created_at`, `updated_at` no permiten reconstruir cada cambio. `version_concurrencia` puede permanecer en 1 sin impedir sobrescritura.  
**Acción:** crear una tabla de auditoría con entidad, ID, acción, usuario, fecha UTC, `OLD` y `NEW` en `JSONB` y correlación con transacción/evento. En servicios, comparar la versión esperada e incrementar el contador al modificar borradores. Implementar autorización por roles en la aplicación y, cuando proceda, controles de privilegios/roles en BD. Para reportar accesos denegados sin perder el log con un rollback, registrar el rechazo desde un canal fiable fuera de la transacción fallida.

### ALTA 7 — Snapshot íntegro y órdenes coherentes
**Referencias:** documento 181914 RN07/RF08, PF04; evento `BOM.OrderVersionSnapshotted`.  
**Problema:** `ordenes_produccion.parent_sku` y `bom_id` pueden referir productos diferentes. `orden_bom_snapshots` no incluye referencias FK a artículos/UOM/versiones, ni `bom_id` de cada subensamble ni un identificador de ruta/nodo que diferencie componentes iguales usados en distintas ramas. Además, los snapshots se pueden modificar y borrar mediante cascada de eliminación de órdenes.  
**Acción:** garantizar la correspondencia orden/producto/BOM mediante FK compuesta o trigger; guardar IDs de versión resueltos en todos los niveles, vínculos de jerarquía y cantidades con unidad; establecer política de inmutabilidad y retención histórica. Evaluar `ON DELETE RESTRICT` en snapshots y cancelación lógica de órdenes; prohibir la eliminación física de órdenes históricas si se exige reconstrucción.

### MEDIA 8 — Completar consultas y algoritmos
**Referencias:** documento 181914 RF03/RF07/RN07–RN08, PU04–PU09; documento general RF-03; documento 179761 RF-02 y Picking List.  
**Problema:** `schema.sql` almacena datos pero no implementa explosión por fecha, aplanamiento/agrupación, where-used o cost roll-up.  
**Acción:** definir funciones o servicios que seleccionen versiones vigentes en cada nivel y apliquen `(demanda / cantidad_base) * cantidad_componente`, conversiones UOM, merma y acumulación antes de redondear por material. Generar consulta where-used directa e indirecta y cálculo de costos multinivel. No debe confundirse ausencia de una función SQL con ausencia de implementación en Python: es necesaria una revisión aparte del backend.

### MEDIA 9 — Manejo coherente de eventos
**Referencias:** ambos `events_*.json`.  
**Problema:** los JSON describen eventos, no implementaciones. `schema.sql` no registra publicación, cambio, fallo, resolución ni consumo.  
**Acción:** diseñar eventos con `event_id`, tipo, versión del contrato, instante UTC, entidad/version BOM, usuario/causa, payload y clave de correlación; usar patrón **transactional outbox** para eventos de cambios confirmados, si los eventos deben publicarse a otros módulos. Especificar emisores externos para consultas y errores rechazados. `events_179761.json` incluye detalles de orden, lotes, consumo real, scrap, serial y costo anterior/nuevo; éstos requieren tablas o integración con módulos de ejecución, inventario y costeo, no necesariamente todas en BOM.

### MEDIA 10 — Corregir conflictos entre documentos
No son fallos exclusivamente de `schema.sql`, pero **hay decisiones que deben acordarse antes de finalizar**:

1. **Estados:** el documento 181914 usa borrador/aprobada/obsoleta; `BOM_Requirements.md` y SQL usan borrador/activo/inactivo/obsoleto. Definir un vocabulario oficial y mapear aprobación a estado `ACTIVO` si se mantiene ese diseño.
2. **Merma:** el documento 181914 exige `necesidad = teórica / (1 - merma)` y redondeo después de consolidar; `BOM_Requirements.md` contiene un ejemplo que multiplica por `1 + scrap`. Para una merma del 10%: 10 / 0.9 = 11.111..., mientras que 10 × 1.1 = 11. Definir el significado operativo de merma y unificar las pruebas.
3. **Versiones hijas:** el documento general acepta una versión activa o en borrador para ciertos despliegues; el documento 181914 exige versiones aprobadas para explosión de demanda. Separar *vista previa de ingeniería* y *planificación productiva*.
4. **Clonación:** el documento general plantea clonar una versión del mismo SKU a nueva revisión; el documento 179761 también permite copiar como base de un modelo diferente. Soportar ambos casos o documentar cuál es obligatorio.
5. **Nombres de eventos:** `events_181914.json` define eventos `BOM.Created`, `BOM.Exploded`, etc.; `events_179761.json` usa `BOM_CREATION_ALLOCATED`, `BOM_CONSUMPTION`, etc. Acordar si son contratos separados (diseño vs ejecución) y sus payloads.

## 3. Cambios SQL concretos propuestos (fragmentos orientativos)

**Estos fragmentos son un punto de partida, no una migración completa lista para producción.** Requieren pruebas, adaptación a reglas y orden de instalación.

### 3.1 Rechazo inmediato de autorreferencia

La comprobación necesita un trigger porque el SKU padre reside en otra tabla:

```sql
CREATE OR REPLACE FUNCTION validar_bom_sin_autoreferencia()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_parent_sku varchar(50);
BEGIN
  SELECT parent_sku INTO v_parent_sku
  FROM bom_cabecera WHERE bom_id = NEW.bom_id;

  IF NEW.component_sku = v_parent_sku THEN
    RAISE EXCEPTION 'BOM: un producto no puede contenerse a sí mismo';
  END IF;

  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_bom_no_autoreferencia
BEFORE INSERT OR UPDATE OF bom_id, component_sku
ON bom_detalle
FOR EACH ROW EXECUTE FUNCTION validar_bom_sin_autoreferencia();
```

Esto **solo** cubre el ciclo directo. El control multinivel exige además búsqueda recursiva y protección transaccional.

### 3.2 Unicidad de conversiones generales y específicas

```sql
-- Primero depurar duplicados ya existentes.
ALTER TABLE conversiones_uom DROP CONSTRAINT uq_conversion;

CREATE UNIQUE INDEX uq_conversion_general
ON conversiones_uom (uom_origen_id, uom_destino_id)
WHERE sku_especifico IS NULL;

CREATE UNIQUE INDEX uq_conversion_especifica
ON conversiones_uom (uom_origen_id, uom_destino_id, sku_especifico)
WHERE sku_especifico IS NOT NULL;
```

Además, `sku_especifico` debería contar con FK a `articulos(sku)` (tras crear ambas tablas o mediante `ALTER TABLE`); verificar familias dimensionales, permisos de equivalencia y dirección de las conversiones.

### 3.3 Integridad de producto para órdenes

```sql
ALTER TABLE bom_cabecera
ADD CONSTRAINT uq_bom_id_parent UNIQUE (bom_id, parent_sku);

ALTER TABLE ordenes_produccion
ADD CONSTRAINT fk_orden_bom_producto
FOREIGN KEY (bom_id, parent_sku)
REFERENCES bom_cabecera (bom_id, parent_sku);
```

La FK compuesta evita que el producto de la orden no coincida con el producto padre de la BOM. **No** sustituye la selección de versión por fecha ni el snapshot de hijos.

### 3.4 Validación de numeración de concurrencia

```sql
ALTER TABLE bom_cabecera
ADD CONSTRAINT chk_version_concurrencia_positiva
CHECK (version_concurrencia > 0);
```

El `CHECK` ayuda a integridad de dominio, **pero no implementa** la concurrencia optimista: la actualización deberá comparar la versión esperada en el `WHERE` y verificar que se modificó exactamente una fila.

## 4. Matriz breve para `events_181914.json`

| Eventos | Estado frente a este SQL | Acción requerida |
|---|---|---|
| `BOM.Created`, `BOM.TypeAssigned`, `BOM.ComponentChanged` | Parcial | Cabecera y detalle existen; no hay tipo `Sales/Assembly/Template/Production` ni emisión/auditoría completa. |
| `BOM.ValidationFailed` | Parcial | Hay `CHECK`, `FK` y `UNIQUE`; faltan UOM, ciclos y reglas de aprobación; construir evento de rechazo en la aplicación. |
| `BOM.ApprovalRequested`, `BOM.Approved` | Parcial | Existen campos de aprobador y fecha; falta solicitud de aprobación y flujo controlado. |
| `BOM.AccessDenied`, `BOM.ConcurrencyConflict` | No garantizado | Permisos y concurrencia deben implementarse y registrarse. |
| `BOM.RevisionCreated`, `BOM.Obsoleted` | Parcial | Versiones y estados existen; faltan clonación, transición y publicación atómica. |
| `BOM.VersionResolved`, `BOM.Exploded`, `BOM.ExplosionRejected` | No en SQL | Algoritmo recursivo de selección y explosión; rechazo sin parciales. |
| `BOM.OrderVersionSnapshotted` | Parcial | Existe tabla de snapshot, incompleta para trazabilidad multinivel robusta. |
| `BOM.WhereUsedQueried` | No en SQL | Consulta recursiva directa e indirecta. |
| `BOM.AuditRecorded` | No | Tabla de bitácora/eventos inmutables con cambios anteriores y posteriores. |

En `events_179761.json`, `BOM_CREATION_ALLOCATED` se alinea parcialmente con cabecera/detalle, pero `BOM_CONSUMPTION`, `BOM_DISASSEMBLY_SCRAP` y `BOM_COST_RECALCULATED` necesitan integración o persistencia adicional de trazabilidad física, lotes, consumo, scrap y recalculación monetaria.

## 5. Plan sugerido de implementación y validación

1. **P0 — Integridad de escritura:** padre PT/SE, artículos activos, UOM/dimensiones, cantidades discretas y validación DAG.
2. **P0 — Protección de historial:** inmutabilidad estructural, validación de aprobación, versiones hijas y transiciones.
3. **P0 — Órdenes y vigencias:** orden vinculada a BOM del mismo producto, publicación atómica, snapshots multinivel.
4. **P1 — Auditoría y concurrencia:** historial `OLD/NEW`, permisos, versión optimista, pruebas de carreras.
5. **P1 — Cálculos:** explosión multinivel, consolidación + redondeo final, consulta inversa, cost roll-up.
6. **P1 — Eventos:** contratos canónicos, emisores confiables, correlación con órdenes y outbox cuando corresponda.

### Pruebas mínimas antes de afirmar cumplimiento

- Rechazar padre `MP`, hijo inactivo, componente duplicado, cantidad 0 y UOM incompatible.
- Rechazar cantidades decimales para un SKU discreto y permitirlas para consumibles compatibles.
- Rechazar `A -> A` y `A -> B -> C -> A`, incluyendo dos transacciones concurrentes.
- Rechazar activación sin líneas o con subensamble sin versión válida.
- Rechazar edición de versión activa o referenciada por una orden.
- Publicar dos versiones adyacentes: fin de V1 = inicio de V2 y seleccionar V2 en el límite.
- Rechazar publicación concurrente de vigencias superpuestas.
- Explotar BOM con base 5, material compartido por ramas y merma 10%; acumular **antes** de redondear.
- Reproducir órdenes anteriores desde sus snapshots tras publicar una nueva versión.
- Registrar y comprobar eventos y auditoría, incluidos errores sin datos parcialmente confirmados.

## 6. Veredicto

**`schema.sql` está bien encaminado como modelo de datos inicial, pero NO cumple integralmente los requerimientos y eventos revisados.** Su principal fortaleza es la estructura relacional y la exclusión de vigencias activas. Sus principales riesgos son permitir datos semánticamente inválidos, editar información que debería ser histórica y carecer de mecanismos explícitos de aprobación, ciclos, auditoría y cálculo.

**No se recomienda marcar el módulo BOM como completo** hasta implementar o demostrar las garantías faltantes en el backend/BD y ejecutar las pruebas de aceptación. Algunos requisitos (explosión MRP, visualización, eventos e interfaz) **no deben exigirse a un archivo de esquema de forma aislada**, pero sí al módulo completo.
