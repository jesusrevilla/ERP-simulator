# 03. Procedimientos y manejo de transacciones


## 1. Funciones y métodos que operan sobre la base de datos

Todos los métodos pertenecen a la clase `ComercialERP`.

### 1.1 Métodos que escriben (usan transacción)

| Método | Tablas que modifica | Estado |
| --- | --- | --- |
| `bootstrap_admin` | `commercial_users` | Implementado |
| `create_user` | `commercial_users`, `commercial_audit` | Implementado |
| `add_product` | `commercial_products`, `commercial_movements` (si hay stock inicial), `commercial_audit` | Implementado |
| `add_supplier` | `commercial_suppliers`, `commercial_audit` | Implementado |
| `add_customer` | `commercial_customers`, `commercial_audit` | Implementado |
| `create_purchase` | `commercial_purchases`, `commercial_purchase_lines`, `commercial_audit` | Implementado |
| `confirm_purchase` | `commercial_products`, `commercial_movements`, `commercial_purchases`, `commercial_audit` | Implementado |
| `create_sale` | `commercial_sales`, `commercial_sale_lines`, `commercial_audit` | Implementado |
| `confirm_sale` | `commercial_products`, `commercial_movements`, `commercial_sales`, `commercial_audit` | Implementado |
| `cancel_sale` | `commercial_products`, `commercial_movements`, `commercial_sales`, `commercial_audit` | Implementado |
| `adjust_stock` | `commercial_products`, `commercial_movements`, `commercial_audit` | Implementado |
| `deactivate_product` | `commercial_products`, `commercial_audit` | Implementado |

### 1.2 Métodos auxiliares

`_audit` y `_record_movement` insertan en `commercial_audit` y `commercial_movements`. **No abren transacción propia**: siempre se llaman desde dentro del `with self.transaction()` del método principal, así que forman parte de la misma unidad de trabajo.

### 1.3 Métodos de solo lectura (sin transacción explícita)

`login`, `product_info`, `purchase_info`, `sale_info`, `low_stock`, `search_products`, `movements` y `report`. Solo ejecutan `SELECT`, por lo que no necesitan `BEGIN`/`COMMIT`.

---

## 2. Cómo se inicia una transacción y cómo se confirman los cambios

### 2.1 Configuración de la conexión (Implementado)

```python
self.connection = sqlite3.connect(database, isolation_level=None, timeout=10, check_same_thread=False)
self.connection.execute("PRAGMA foreign_keys = ON")
self.connection.execute("PRAGMA busy_timeout = 10000")
if database != ":memory:":
    self.connection.execute("PRAGMA journal_mode = WAL")
```

| Parámetro | Efecto en las transacciones |
| --- | --- |
| `isolation_level=None` | Desactiva las transacciones implícitas del módulo `sqlite3`. Ninguna transacción empieza "sola": el código decide exactamente dónde inicia cada una. |
| `PRAGMA foreign_keys = ON` | SQLite trae las llaves foráneas apagadas por defecto; esto las activa en cada conexión. |
| `PRAGMA busy_timeout = 10000` / `timeout=10` | Si otra conexión tiene el bloqueo de escritura, se espera hasta 10 s en lugar de fallar de inmediato. |
| `PRAGMA journal_mode = WAL` | En bases en archivo, permite leer mientras otra conexión escribe y mejora la durabilidad ante interrupciones. |

### 2.2 El administrador de transacciones `transaction()` (Implementado)

Es el mecanismo central de todo el módulo:

```python
@contextmanager
def transaction(self):
    self.connection.execute("BEGIN IMMEDIATE")
    try:
        yield self.connection
        self.connection.commit()
    except BaseException:
        self.connection.rollback()
        raise
```

Funcionamiento paso a paso:

1. **`BEGIN IMMEDIATE`** abre la transacción y toma de inmediato el bloqueo de escritura de la base. A diferencia de un `BEGIN` simple, que espera al primer `UPDATE`/`INSERT`, aquí ninguna otra conexión puede empezar a escribir mientras esta transacción está abierta.
2. **`yield`** ejecuta el bloque del método que la usa (validaciones, `UPDATE`, `INSERT`).
3. Si el bloque termina sin errores, **`commit()`** confirma todos los cambios juntos.
4. Si ocurre **cualquier** excepción, **`rollback()`** descarta todos los cambios pendientes y **`raise`** vuelve a lanzar el error para que quien llamó sepa que la operación falló.

Uso típico en los métodos:

```python
with self.transaction():
    # todas las lecturas, validaciones y escrituras de la operación
    ...
```

---

## 3. Uso de BEGIN, COMMIT y ROLLBACK

| Instrucción | Dónde aparece | Estado |
| --- | --- | --- |
| `BEGIN IMMEDIATE` | Primera línea de `transaction()` | Implementado |
| `COMMIT` | `self.connection.commit()` al terminar el bloque sin errores | Implementado |
| `ROLLBACK` | `self.connection.rollback()` en el `except BaseException` | Implementado |

Ningún método escribe en la base fuera de `transaction()`. Por eso no hay escrituras "sueltas" que puedan quedar confirmadas sin el resto de la operación.

Ejemplo de vida de una transacción en `confirm_sale` con dos renglones:

```
BEGIN IMMEDIATE
  SELECT status FROM commercial_sales ...            -- validar estado
  SELECT * FROM commercial_sale_lines ...            -- leer renglones
  UPDATE commercial_products ... (renglón 1)  OK
  INSERT INTO commercial_movements ... (renglón 1)
  UPDATE commercial_products ... (renglón 2)  sin stock → StockInsufficient
ROLLBACK                                             -- se deshace también el renglón 1
```

---

## 4. Manejo de errores para evitar operaciones incompletas

### 4.1 Excepciones propias (Implementado)

```python
class ERPError(Exception): pass
class PermissionDenied(ERPError): pass
class StockInsufficient(ERPError): pass
class InvalidOperation(ERPError): pass
```

Además se usan `ValueError` para datos inválidos y se dejan pasar los `sqlite3.IntegrityError` que lanza la base cuando se viola una restricción.

### 4.2 Dos niveles de validación

| Nivel | Cuándo ocurre | Ejemplo | Efecto |
| --- | --- | --- | --- |
| **Antes de la transacción** | Antes de `BEGIN IMMEDIATE` | `_require` (permisos), `_money` y `_int_nonnegative` en `add_product`, validar que `lines` sea lista | Se rechaza sin tocar la base ni tomar el bloqueo. |
| **Dentro de la transacción** | Entre `BEGIN` y `COMMIT` | `_active_partner`, `_active_product`, estado `Borrador`, `stock >= ?`, restricciones `CHECK` y `FOREIGN KEY` | El `rollback()` deshace lo que ya se haya escrito en esa operación. |

### 4.3 Por qué se captura `BaseException`

Se usa `except BaseException` y no solo `except Exception`. Así también se revierte la transacción ante interrupciones como `KeyboardInterrupt` y ante errores que el código no esperaba.

Se comprobó con una prueba manual: en `create_purchase` se mandó un renglón válido y otro con `unit_cost: "abc"`. El error fue un `decimal.InvalidOperation` (un tipo que el código no tenía previsto, ver 4.4) y, aun así, **no quedó ni el encabezado de la compra ni el primer renglón**:

```
decimal InvalidOperation
compras: 0 renglones: 0
```

### 4.4 Observación encontrada en el código

En el módulo se importa `InvalidOperation` desde `decimal`, pero después se define una clase propia con el **mismo nombre**:

```python
from decimal import Decimal, InvalidOperation
...
class InvalidOperation(ERPError):
    pass
```

La clase propia reemplaza a la de `decimal`, así que en `_money` la línea `except (InvalidOperation, ValueError)` ya no atrapa el error de un importe con texto (por ejemplo `"abc"`). En lugar del `ValueError("Importe invalido")` esperado, sale un `decimal.InvalidOperation`.

- **Impacto en la integridad: ninguno.** Si ocurre dentro de una transacción, el `except BaseException` la revierte igual (como se vio en 4.3).
- **Impacto en el manejo de errores:** quien use el módulo recibe un tipo de error distinto al documentado.
- **Propuesta (no aplicada):** importar con otro nombre, por ejemplo `from decimal import InvalidOperation as DecimalInvalidOperation`, y usarlo en `_money`.

---

## 5. Operaciones de compras y ventas: qué debe ir en la misma transacción

Cada operación de confirmación cambia varias tablas. Si solo se guardara una parte, el stock, los movimientos, el estado del documento y la auditoría dejarían de coincidir.

### 5.1 Compras

| Operación | Cambios dentro de la misma transacción | Protección del estado |
| --- | --- | --- |
| `create_purchase` | 1. `INSERT` en `commercial_purchases` (estado `Borrador`) · 2. `INSERT` de cada renglón en `commercial_purchase_lines` · 3. `INSERT` en `commercial_audit` (`COMPRA_BORRADOR`) | Si un renglón falla, no queda un encabezado sin detalles. **No modifica stock.** |
| `confirm_purchase` | 1. `UPDATE commercial_products SET stock = stock + ?` por renglón · 2. `INSERT` en `commercial_movements` (`RECEPCION`) por renglón · 3. `UPDATE commercial_purchases SET status = 'Confirmada', confirmed_at` · 4. `INSERT` en `commercial_audit` (`CONFIRMAR_COMPRA`) | Solo procede si el estado es `Borrador` y hay renglones; una segunda confirmación lanza `InvalidOperation`. |

```python
def confirm_purchase(self, token, purchase_id):
    user_id = self._require(token, "administrador", "compras")
    with self.transaction():
        purchase = self.connection.execute(
            "SELECT status FROM commercial_purchases WHERE id = ?", (purchase_id,)).fetchone()
        if not purchase or purchase["status"] != "Borrador":
            raise InvalidOperation("Compra inexistente o confirmada")
        ...
        for line in lines:
            self.connection.execute(
                "UPDATE commercial_products SET stock = stock + ? WHERE id = ?",
                (line["quantity"], line["product_id"]))
            self._record_movement(line["product_id"], user_id, "RECEPCION",
                                  line["quantity"], "COMPRA", purchase_id)
        self.connection.execute(
            "UPDATE commercial_purchases SET status = 'Confirmada', confirmed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (purchase_id,))
        self._audit(user_id, "CONFIRMAR_COMPRA", "compra", purchase_id)
    return self.purchase_info(token, purchase_id)
```

La validación del estado se hace **dentro** de la transacción y después de `BEGIN IMMEDIATE`. Así, dos confirmaciones simultáneas de la misma compra no pueden leer las dos `Borrador`: la segunda espera el bloqueo y ya encuentra `Confirmada`.

### 5.2 Ventas

| Operación | Cambios dentro de la misma transacción | Protección del estado |
| --- | --- | --- |
| `create_sale` | 1. `INSERT` en `commercial_sales` (`Borrador`) · 2. `INSERT` de renglones con el precio vigente · 3. `INSERT` en auditoría (`VENTA_BORRADOR`) | No modifica stock. |
| `confirm_sale` | 1. `UPDATE` condicionado del stock por renglón · 2. `INSERT` en `commercial_movements` (`VENTA`, cantidad negativa) · 3. `UPDATE` del estado a `Confirmada` · 4. auditoría (`CONFIRMAR_VENTA`) | Solo desde `Borrador`; si **un** renglón no tiene stock, se revierte **toda** la venta. |
| `cancel_sale` | 1. `UPDATE ... stock = stock + ?` por renglón · 2. movimiento `CANCELACION` · 3. estado `Cancelada` con `cancelled_at` y `cancellation_reason` · 4. auditoría (`CANCELAR_VENTA`) | Solo desde `Confirmada`; una segunda cancelación se rechaza y no reintegra stock dos veces. |
| `adjust_stock` | 1. `UPDATE` del stock · 2. movimiento `AJUSTE` · 3. auditoría (`AJUSTAR_STOCK`) | Rechaza ajustes que dejarían el stock negativo. |

El punto clave de `confirm_sale` es la **actualización condicionada**:

```python
cur = self.connection.execute(
    "UPDATE commercial_products SET stock = stock - ? WHERE id = ? AND stock >= ?",
    (line["quantity"], line["product_id"], line["quantity"]),
)
if cur.rowcount != 1:
    raise StockInsufficient("Existencias insuficientes")
```

- La comprobación de existencias y el descuento ocurren en **una sola sentencia**, sin un `SELECT` previo que pudiera quedar desactualizado.
- Si no hay stock suficiente, el `UPDATE` no afecta ninguna fila (`rowcount = 0`), se lanza `StockInsufficient` y `transaction()` ejecuta el `ROLLBACK`.
- Como respaldo, el esquema tiene `CHECK (stock >= 0)` en `commercial_products`: aunque el código fallara, la base rechazaría un stock negativo.

---

## 6. Cómo se comprueba que los cambios se guardaron correctamente

### 6.1 Lectura posterior al COMMIT (Implementado)

`confirm_purchase`, `confirm_sale`, `cancel_sale` y `adjust_stock` regresan el resultado con `purchase_info`, `sale_info` o `product_info`, llamados **después** de salir del bloque `with`. Es decir, devuelven lo que realmente quedó guardado y no un valor armado en memoria.

### 6.2 Pruebas automatizadas (Implementado)

Se ejecutó `pytest` sobre `tests/test_erp_comercial_cristian.py`:

```
31 passed in 4.77s
```

Las pruebas que verifican directamente el manejo transaccional son:

| Prueba | Qué provoca | Qué comprueba |
| --- | --- | --- |
| `test_pu04_stock_insuficiente` | Venta de 12 con stock 10 | Stock sigue en 10 y la venta sigue en `Borrador`. |
| `test_pu12_rollback_si_falla_movimiento` | Un *trigger* hace fallar el `INSERT` del movimiento `RECEPCION`, **después** de que ya se sumó el stock | El stock vuelve a 10 y la compra sigue en `Borrador`: el `ROLLBACK` deshizo el `UPDATE` previo. |
| `test_rollback_venta_por_error_de_movimientos` | Lo mismo, pero en el movimiento `VENTA` | La venta sigue en `Borrador` y el stock en 10. |
| `test_pi03_venta_multilinea_atomicidad` | Venta con un renglón con stock y otro sin stock | No se descuenta ninguno, la venta sigue en `Borrador` y no se registra ningún movimiento `VENTA`. |
| `test_pi04_concurrencia_venta_stock` | Dos hilos, cada uno con su conexión a la misma base en archivo, confirman ventas de 7 con stock 10 | Una termina `OK`, la otra `DENEGADO` y el stock final es 3. |
| `test_compra_doble_confirmacion_no_duplica_stock` | Confirmar dos veces la misma compra | La segunda falla y el stock solo sube una vez (18). |
| `test_pi05_cancelacion_sin_duplicados` | Cancelar dos veces la misma venta | Solo existe un movimiento `CANCELACION`. |
| `test_ajuste_excesivo_rechazado` | Ajuste de −11 con stock 10 | El stock sigue en 10. |

La técnica de `pu12` es la más importante para probar un `ROLLBACK`: se fuerza un fallo **a la mitad** de la operación, cuando ya hay un cambio escrito, y luego se revisa que ese cambio desapareció.

```python
e.connection.execute("""CREATE TRIGGER test_fail_receipt BEFORE INSERT ON commercial_movements
    WHEN NEW.movement_type = 'RECEPCION' BEGIN SELECT RAISE(ABORT, 'simulated failure'); END""")
with pytest.raises(sqlite3.IntegrityError):
    e.confirm_purchase(compras, purchase)
assert e.product_info(compras, "ERP-001")["stock"] == 10
assert e.purchase_info(compras, purchase)["status"] == "Borrador"
```

### 6.3 Relación con `control y pruebas transaccionales.md`

Ese documento dejó como **no verificado** el uso de `COMMIT`, `ROLLBACK`, bloqueos, auditoría y pruebas de reversión y concurrencia. Para el prototipo `erp_comercial_cristian.py` quedan comprobados así:

| Pendiente del documento previo | Resultado en este prototipo |
| --- | --- |
| Uso de `COMMIT` y `ROLLBACK` | Implementado en `transaction()`. |
| Control de concurrencia y bloqueos | `BEGIN IMMEDIATE` + `busy_timeout` + `UPDATE` condicionado; probado en `test_pi04`. |
| Auditoría | Tabla `commercial_audit` y movimientos en `commercial_movements`, escritos dentro de la misma transacción. |
| Prueba de reversión por error | `test_pu12` y `test_rollback_venta_por_error_de_movimientos`. |
| Prueba de operación repetida | `test_compra_doble_confirmacion_no_duplica_stock` y `test_pi05`. |

Esto **solo aplica al prototipo SQLite**. Los archivos del backend PostgreSQL (`create_schema.py`, `seed_data.py`) no se revisaron en esta entrega.

---

## 7. Implementación mediante procedimientos almacenados SQL (Propuesta)

> **Importante:** en el repositorio **no existe ningún procedimiento almacenado**. Además, **SQLite no soporta procedimientos almacenados**, así que en el prototipo actual la lógica transaccional solo puede vivir en Python (o, de forma limitada, en *triggers*). Lo siguiente es una **propuesta** para PostgreSQL, el motor principal del proyecto, usando los mismos nombres de tablas del esquema comercial.

### 7.1 Por qué moverlo a la base

- La operación completa queda en un solo lugar y cualquier cliente (Python, otra aplicación) la ejecuta igual.
- La base garantiza la atomicidad aunque el cliente se desconecte a mitad de la operación.
- En PostgreSQL, si ocurre un `RAISE EXCEPTION`, se revierte automáticamente todo lo que hizo el procedimiento.

### 7.2 Equivalencias entre lo implementado y lo propuesto

| Implementado en Python | Procedimiento propuesto |
| --- | --- |
| `confirm_purchase` | `sp_confirmar_compra(p_purchase_id, p_user_id)` |
| `confirm_sale` | `sp_confirmar_venta(p_sale_id, p_user_id)` |
| `cancel_sale` | `sp_cancelar_venta(p_sale_id, p_user_id, p_motivo)` |
| `BEGIN IMMEDIATE` (bloquea toda la base) | `SELECT ... FOR UPDATE` (bloquea solo la fila del documento) |
| `raise StockInsufficient` | `RAISE EXCEPTION` |

### 7.3 Propuesta: `sp_confirmar_venta`

```sql
CREATE OR REPLACE PROCEDURE sp_confirmar_venta(p_sale_id INTEGER, p_user_id INTEGER)
LANGUAGE plpgsql
AS $$
DECLARE
    v_status TEXT;
    v_line   RECORD;
BEGIN
    -- Bloquea la venta para que nadie la confirme o cancele al mismo tiempo
    SELECT status INTO v_status
    FROM commercial_sales
    WHERE id = p_sale_id
    FOR UPDATE;

    IF v_status IS NULL OR v_status <> 'Borrador' THEN
        RAISE EXCEPTION 'Venta inexistente o procesada';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM commercial_sale_lines WHERE sale_id = p_sale_id) THEN
        RAISE EXCEPTION 'Venta sin detalles';
    END IF;

    FOR v_line IN
        SELECT product_id, quantity FROM commercial_sale_lines WHERE sale_id = p_sale_id
    LOOP
        -- Misma idea que en Python: validar y descontar en una sola sentencia
        UPDATE commercial_products
        SET stock = stock - v_line.quantity
        WHERE id = v_line.product_id AND stock >= v_line.quantity;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Existencias insuficientes para el producto %', v_line.product_id;
        END IF;

        INSERT INTO commercial_movements
            (product_id, user_id, movement_type, quantity_delta, document_type, document_id)
        VALUES
            (v_line.product_id, p_user_id, 'VENTA', -v_line.quantity, 'VENTA', p_sale_id);
    END LOOP;

    UPDATE commercial_sales
    SET status = 'Confirmada', confirmed_at = CURRENT_TIMESTAMP
    WHERE id = p_sale_id;

    INSERT INTO commercial_audit (user_id, action, entity, entity_id)
    VALUES (p_user_id, 'CONFIRMAR_VENTA', 'venta', p_sale_id);
END;
$$;
```

### 7.4 Propuesta: `sp_confirmar_compra`

```sql
CREATE OR REPLACE PROCEDURE sp_confirmar_compra(p_purchase_id INTEGER, p_user_id INTEGER)
LANGUAGE plpgsql
AS $$
DECLARE
    v_status TEXT;
BEGIN
    SELECT status INTO v_status
    FROM commercial_purchases
    WHERE id = p_purchase_id
    FOR UPDATE;

    IF v_status IS NULL OR v_status <> 'Borrador' THEN
        RAISE EXCEPTION 'Compra inexistente o confirmada';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM commercial_purchase_lines WHERE purchase_id = p_purchase_id) THEN
        RAISE EXCEPTION 'Compra sin detalles';
    END IF;

    UPDATE commercial_products p
    SET stock = p.stock + l.quantity
    FROM commercial_purchase_lines l
    WHERE l.purchase_id = p_purchase_id AND p.id = l.product_id;

    INSERT INTO commercial_movements
        (product_id, user_id, movement_type, quantity_delta, document_type, document_id)
    SELECT product_id, p_user_id, 'RECEPCION', quantity, 'COMPRA', p_purchase_id
    FROM commercial_purchase_lines
    WHERE purchase_id = p_purchase_id;

    UPDATE commercial_purchases
    SET status = 'Confirmada', confirmed_at = CURRENT_TIMESTAMP
    WHERE id = p_purchase_id;

    INSERT INTO commercial_audit (user_id, action, entity, entity_id)
    VALUES (p_user_id, 'CONFIRMAR_COMPRA', 'compra', p_purchase_id);
END;
$$;
```

> Si una compra tuviera el mismo producto en dos renglones, el `UPDATE ... FROM` solo aplicaría uno. En ese caso habría que agrupar antes con `SUM(quantity) ... GROUP BY product_id`.

### 7.5 Propuesta: `sp_cancelar_venta`

```sql
CREATE OR REPLACE PROCEDURE sp_cancelar_venta(p_sale_id INTEGER, p_user_id INTEGER, p_motivo TEXT)
LANGUAGE plpgsql
AS $$
DECLARE
    v_status TEXT;
BEGIN
    IF p_motivo IS NULL OR length(trim(p_motivo)) = 0 THEN
        RAISE EXCEPTION 'Motivo de cancelacion obligatorio';
    END IF;

    SELECT status INTO v_status
    FROM commercial_sales
    WHERE id = p_sale_id
    FOR UPDATE;

    IF v_status IS NULL OR v_status <> 'Confirmada' THEN
        RAISE EXCEPTION 'Solo es posible cancelar una vez una venta confirmada';
    END IF;

    UPDATE commercial_products p
    SET stock = p.stock + l.quantity
    FROM commercial_sale_lines l
    WHERE l.sale_id = p_sale_id AND p.id = l.product_id;

    INSERT INTO commercial_movements
        (product_id, user_id, movement_type, quantity_delta, document_type, document_id, reason)
    SELECT product_id, p_user_id, 'CANCELACION', quantity, 'VENTA', p_sale_id, trim(p_motivo)
    FROM commercial_sale_lines
    WHERE sale_id = p_sale_id;

    UPDATE commercial_sales
    SET status = 'Cancelada', cancelled_at = CURRENT_TIMESTAMP, cancellation_reason = trim(p_motivo)
    WHERE id = p_sale_id;

    INSERT INTO commercial_audit (user_id, action, entity, entity_id, details)
    VALUES (p_user_id, 'CANCELAR_VENTA', 'venta', p_sale_id, trim(p_motivo));
END;
$$;
```

### 7.6 Cómo se llamarían desde Python (Propuesta)

```python
import psycopg2

def confirmar_venta(conn, sale_id, user_id):
    try:
        with conn.cursor() as cur:
            cur.execute("CALL sp_confirmar_venta(%s, %s)", (sale_id, user_id))
        conn.commit()      # confirma lo que hizo el procedimiento
    except psycopg2.Error:
        conn.rollback()    # el procedimiento falló: no queda nada a medias
        raise
```

Los **permisos** (`_require`) y las validaciones de formato (`_money`, `_int_positive`) seguirían en Python, porque dependen de la sesión del usuario; el procedimiento se encargaría solo de la parte que debe ser atómica.

### 7.7 Diferencias a considerar al migrar

| Aspecto | Actual (SQLite + Python) | Propuesto (PostgreSQL) |
| --- | --- | --- |
| Alcance del bloqueo | `BEGIN IMMEDIATE` bloquea las escrituras de **toda la base** | `FOR UPDATE` bloquea solo las filas involucradas; otras ventas pueden avanzar en paralelo |
| Dónde vive la lógica | En los métodos de `ComercialERP` | En la base de datos |
| Reversión ante error | `except BaseException` → `rollback()` | `RAISE EXCEPTION` revierte el procedimiento; el cliente hace `rollback()` |
| Pruebas | `pytest` con SQLite en memoria | Habría que adaptar las pruebas para correr contra PostgreSQL (por ejemplo, el servicio `postgres` del workflow `ci.yml`) |
