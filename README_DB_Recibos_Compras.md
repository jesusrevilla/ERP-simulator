# Base de Datos: Compras, Recibos, Entregas e Inventario (Neo4j y MongoDB + SQL 3FN)

Implementación de tablas, esquemas documentales, modelo de grafos, reglas de negocio, integridad de datos y pruebas para el módulo de **Recibos y Entregas** del simulador ERP (`TechAssembly S.A.`), alineada con [Primera entrega.md](./Primera%20entrega.md), [Schema1.sql](./Schema1.sql) y la retroalimentación del proyecto (`requirements/feedback.md`).

---

## 1. Archivos entregados

| Archivo | Tecnología | Propósito |
| :--- | :--- | :--- |
| `schema_recibos_entregas.sql` | PostgreSQL (3FN) | Tablas normalizadas completas, llaves foráneas, `CHECK`, índices case-insensitive, triggers de reglas de negocio e inmutabilidad, y vista `vw_cuadre_inventario`. |
| `mongodb_recibos_entregas.py` | MongoDB (`pymongo`) | Validadores `$jsonSchema` estrictos, índices únicos, servicio transaccional con reglas de negocio y adaptador en memoria para pruebas offline. |
| `neo4j_recibos_entregas.cypher` | Neo4j (Cypher) | Restricciones `UNIQUE`, índices de grafo y consulta de cuadre de inventario (`Entradas - Salidas = Stock`). |
| `neo4j_recibos_entregas.py` | Neo4j (`neo4j`) | Modelo de grafo parametrizado con `MERGE`, validación de reglas de negocio sobre nodos/relaciones y reconciliación de stock. |
| `tests/test_recibos_entregas_177576.py` | Python (`unittest` / `pytest`) | Pruebas unitarias, funcionales (E2E) y de integridad de datos. |

---

## 2. Normalización y Estructura de Datos (3FN)

Partiendo de `Schema1.sql` (que solo incluía `proveedores` y `ordenes_compra`), se normalizó el modelo separando catálogos, cabeceras, detalles y kardex para evitar redundancia y anomalías de actualización:

- **Catálogos independientes:** `unidades_medida`, `almacenes`, `ubicaciones_almacen`, `proveedores`, `clientes`, `productos`, `autorizaciones_gerenciales`.
- **Inventario desacoplado (`inventario_stock`):** Relación `(producto_id, almacen_id)` con `stock_actual >= 0`, `stock_danado >= 0` y `stock_reservado <= stock_actual`.
- **Documentos cabecera / detalle:**
  - Compras y Recibos: `ordenes_compra` $\rightarrow$ `ordenes_compra_detalle`, `recibos_mercancia` $\rightarrow$ `recibos_detalle`.
  - Ventas y Entregas: `ordenes_venta` $\rightarrow$ `ordenes_venta_detalle`, `entregas_mercancia` $\rightarrow$ `entregas_detalle`.
- **Kardex inmutable:** `movimientos_inventario` y `auditoria_operaciones`.

---

## 3. Reglas de Negocio Validadas

### Módulo de Recibos (Inbound)
1. **Proveedor activo:** Bloquea cualquier recibo si el proveedor tiene estatus `SUSPENDIDO` o `BAJA` (`activo = FALSE`).
2. **OC válida:** Solo permite recibir contra una Orden de Compra en estado `APROBADA` o `PARCIAL`.
3. **No recibir de más:** Impide recibir más unidades de las solicitadas en la OC, salvo que exista una `autorizacion_gerenciales` vigente de tipo `EXCESO_RECIBO` dentro del límite extra autorizado.
4. **Control de calidad y discrepancias:** Registra piezas aceptadas, faltantes y dañadas (`cantidad_aceptada + cantidad_danada = cantidad_recibida`). Solo `cantidad_aceptada` suma al stock disponible; las piezas dañadas se aíslan en `stock_danado`.
5. **Actualización automática al aprobar:** El stock y el estatus de la OC (`PARCIAL` / `RECIBIDA`) se actualizan automáticamente al pasar el recibo a `APROBADO`.

### Módulo de Entregas (Outbound)
1. **Estado del pedido:** Solo permite despachar pedidos en estado `APROBADO` (o `EN_DESPACHO`) cuyo `estado_pago` sea `PAGADO` o `CREDITO_AUTORIZADO`.
2. **Validación de inventario físico:** Bloquea la creación y confirmación de entregas si `stock_actual < cantidad_entregada` (evita inventario negativo).
3. **Nota de salida y descuento automático:** Genera `numero_nota_salida`, calcula el peso total del paquete en kg y descuenta el inventario automáticamente al confirmar.

### Integridad de Datos
- **Cuadre de inventario:** $\text{Entradas} - \text{Salidas} = \text{Stock actual}$ (verificable en `vw_cuadre_inventario` en SQL, `verificar_cuadre_inventario()` en MongoDB y `CUADRE_INVENTARIO_CYPHER` en Neo4j).
- **Inmutabilidad:** Los recibos `APROBADO`/`CERRADO`, entregas `CONFIRMADA`/`CERRADA` y los registros en `movimientos_inventario` no pueden modificarse ni eliminarse.

---

## 4. Ejecución de Pruebas

```bash
python -m unittest tests/test_recibos_entregas_177576.py -v
```

o con `pytest`:

```bash
pytest tests/test_recibos_entregas_177576.py -v
```
