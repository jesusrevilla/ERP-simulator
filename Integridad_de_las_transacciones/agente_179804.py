import sqlite3
import time
from contextlib import closing
from pathlib import Path


class ErrorTransaccion(Exception):
    """Error cuando una operación no cumple las reglas del negocio."""


class AgenteIntegridadTransaccional:
    """Agente que ejecuta compras y cancelaciones de venta cuidando que
    el inventario, los movimientos y la bitácora siempre cuadren.
    """

    def __init__(self, base_datos, max_reintentos=3):
        self.base_datos = base_datos
        self.max_reintentos = max_reintentos

    def confirmar_compra(self, purchase_id):
        return self._ejecutar_seguro(
            "CONFIRMAR_COMPRA",
            purchase_id,
            lambda conn: self._procesar_compra(conn, purchase_id),
        )

    def cancelar_venta(self, sale_id):
        return self._ejecutar_seguro(
            "CANCELAR_VENTA",
            sale_id,
            lambda conn: self._procesar_cancelacion_venta(conn, sale_id),
        )

    def _ejecutar_seguro(self, operacion, documento_id, funcion_tx):
        # Si la base está ocupada por otro proceso, reintenta esperando un poco más cada vez
        for intento in range(self.max_reintentos + 1):
            try:
                if isinstance(self.base_datos, sqlite3.Connection):
                    return self._correr_transaccion(self.base_datos, funcion_tx)

                ruta = Path(self.base_datos).expanduser().resolve()
                with closing(sqlite3.connect(ruta, timeout=5.0, isolation_level=None)) as conn:
                    conn.execute("PRAGMA foreign_keys = ON;")
                    return self._correr_transaccion(conn, funcion_tx)

            except sqlite3.OperationalError as err:
                if "locked" in str(err).lower() and intento < self.max_reintentos:
                    time.sleep(0.05 * (2 ** intento))
                    continue
                return {
                    "status": "error",
                    "operacion": operacion,
                    "documento_id": documento_id,
                    "mensaje": f"La base de datos estuvo ocupada: {err}",
                }
            except (ErrorTransaccion, sqlite3.Error) as err:
                return {
                    "status": "error",
                    "operacion": operacion,
                    "documento_id": documento_id,
                    "mensaje": f"Operación cancelada (ROLLBACK): {err}",
                }

    def _correr_transaccion(self, conn, funcion_tx):
        # Abrimos la transacción bloqueando escritura para que nadie más modifique al mismo tiempo
        conn.execute("BEGIN IMMEDIATE;")
        try:
            resultado = funcion_tx(conn)
            conn.execute("COMMIT;")
            return resultado
        except Exception:
            # Si cualquier paso falla, deshacemos todos los cambios
            if conn.in_transaction:
                conn.execute("ROLLBACK;")
            raise

    def _procesar_compra(self, conn, purchase_id):
        fila = conn.execute(
            "SELECT status FROM commercial_purchases WHERE id = ?;",
            (purchase_id,),
        ).fetchone()

        if not fila:
            raise ErrorTransaccion(f"La compra #{purchase_id} no existe.")

        estado = fila[0]
        # Si ya estaba confirmada, no hacemos nada para no sumar stock dos veces
        if estado == "Confirmada":
            return {
                "status": "omitida",
                "operacion": "CONFIRMAR_COMPRA",
                "documento_id": purchase_id,
                "mensaje": f"La compra #{purchase_id} ya estaba confirmada.",
            }

        if estado != "Borrador":
            raise ErrorTransaccion(
                f"La compra #{purchase_id} está en estado '{estado}', debe ser 'Borrador'."
            )

        partidas = conn.execute(
            "SELECT product_id, SUM(quantity) FROM commercial_purchase_lines WHERE purchase_id = ? GROUP BY product_id;",
            (purchase_id,),
        ).fetchall()

        if not partidas:
            raise ErrorTransaccion(f"La compra #{purchase_id} no tiene productos.")

        total_unidades = 0
        productos = []

        for product_id, cantidad in partidas:
            if not cantidad or cantidad <= 0:
                raise ErrorTransaccion(f"Cantidad inválida para el producto #{product_id}.")

            existe = conn.execute(
                "SELECT 1 FROM commercial_products WHERE id = ?;", (product_id,)
            ).fetchone()
            if not existe:
                raise ErrorTransaccion(f"El producto #{product_id} no existe.")

            # Sumamos al inventario y guardamos el movimiento de entrada
            conn.execute(
                "UPDATE commercial_products SET stock = stock + ? WHERE id = ?;",
                (cantidad, product_id),
            )
            conn.execute(
                """INSERT INTO commercial_movements
                   (product_id, quantity_delta, movement_type, document_type, document_id)
                   VALUES (?, ?, 'RECEPCION', 'COMPRA', ?);""",
                (product_id, cantidad, purchase_id),
            )
            total_unidades += cantidad
            productos.append(product_id)

        conn.execute(
            "UPDATE commercial_purchases SET status = 'Confirmada' WHERE id = ?;",
            (purchase_id,),
        )
        conn.execute(
            "INSERT INTO commercial_audit (action, entity, entity_id) VALUES ('CONFIRMAR_COMPRA', 'compra', ?);",
            (purchase_id,),
        )

        # Revisamos que todo cuadre antes de guardar definitivamente
        self._validar_compra(conn, purchase_id, total_unidades, productos)

        return {
            "status": "exito",
            "operacion": "CONFIRMAR_COMPRA",
            "documento_id": purchase_id,
            "mensaje": f"Compra #{purchase_id} confirmada (+{total_unidades} unidades).",
        }

    def _procesar_cancelacion_venta(self, conn, sale_id):
        fila = conn.execute(
            "SELECT status FROM commercial_sales WHERE id = ?;",
            (sale_id,),
        ).fetchone()

        if not fila:
            raise ErrorTransaccion(f"La venta #{sale_id} no existe.")

        estado = fila[0]
        # Si ya se había cancelado antes, evitamos devolver el producto otra vez
        if estado == "Cancelada":
            return {
                "status": "omitida",
                "operacion": "CANCELAR_VENTA",
                "documento_id": sale_id,
                "mensaje": f"La venta #{sale_id} ya estaba cancelada.",
            }

        if estado != "Confirmada":
            raise ErrorTransaccion(
                f"Solo se pueden cancelar ventas confirmadas (estado actual: '{estado}')."
            )

        partidas = conn.execute(
            "SELECT product_id, SUM(quantity) FROM commercial_sale_lines WHERE sale_id = ? GROUP BY product_id;",
            (sale_id,),
        ).fetchall()

        if not partidas:
            raise ErrorTransaccion(f"La venta #{sale_id} no tiene productos.")

        productos = []

        for product_id, cantidad in partidas:
            if not cantidad or cantidad <= 0:
                raise ErrorTransaccion(f"Cantidad inválida para el producto #{product_id}.")

            # Verificamos que realmente haya salido ese stock cuando se hizo la venta
            salida_previa = conn.execute(
                """SELECT COALESCE(SUM(quantity_delta), 0)
                   FROM commercial_movements
                   WHERE document_type = 'VENTA' AND document_id = ?
                     AND product_id = ? AND movement_type = 'VENTA';""",
                (sale_id, product_id),
            ).fetchone()[0]

            if salida_previa != -cantidad:
                raise ErrorTransaccion(
                    f"Los movimientos previos de la venta #{sale_id} no coinciden con la cantidad."
                )

            # Regresamos los productos al inventario y registramos la cancelación
            conn.execute(
                "UPDATE commercial_products SET stock = stock + ? WHERE id = ?;",
                (cantidad, product_id),
            )
            conn.execute(
                """INSERT INTO commercial_movements
                   (product_id, quantity_delta, movement_type, document_type, document_id)
                   VALUES (?, ?, 'CANCELACION', 'VENTA', ?);""",
                (product_id, cantidad, sale_id),
            )
            productos.append(product_id)

        conn.execute(
            "UPDATE commercial_sales SET status = 'Cancelada' WHERE id = ?;",
            (sale_id,),
        )
        conn.execute(
            "INSERT INTO commercial_audit (action, entity, entity_id) VALUES ('CANCELAR_VENTA', 'venta', ?);",
            (sale_id,),
        )

        # Revisamos que la salida y la devolución queden en cero antes de guardar
        self._validar_cancelacion(conn, sale_id, productos)

        return {
            "status": "exito",
            "operacion": "CANCELAR_VENTA",
            "documento_id": sale_id,
            "mensaje": f"Venta #{sale_id} cancelada y stock devuelto.",
        }

    def _validar_compra(self, conn, purchase_id, total_esperado, productos):
        for pid in productos:
            stock = conn.execute(
                "SELECT stock FROM commercial_products WHERE id = ?;", (pid,)
            ).fetchone()[0]
            if stock < 0:
                raise ErrorTransaccion(f"El producto #{pid} quedó con stock negativo.")

        movido = conn.execute(
            """SELECT COALESCE(SUM(quantity_delta), 0)
               FROM commercial_movements
               WHERE document_type = 'COMPRA' AND document_id = ? AND movement_type = 'RECEPCION';""",
            (purchase_id,),
        ).fetchone()[0]
        if movido != total_esperado:
            raise ErrorTransaccion("La suma de movimientos no coincide con la compra.")

    def _validar_cancelacion(self, conn, sale_id, productos):
        # La suma de la venta (-X) y la cancelación (+X) debe dar 0
        neto = conn.execute(
            "SELECT COALESCE(SUM(quantity_delta), 0) FROM commercial_movements WHERE document_type = 'VENTA' AND document_id = ?;",
            (sale_id,),
        ).fetchone()[0]
        if neto != 0:
            raise ErrorTransaccion("La cancelación no anuló por completo el movimiento de la venta.")

        for pid in productos:
            stock = conn.execute(
                "SELECT stock FROM commercial_products WHERE id = ?;", (pid,)
            ).fetchone()[0]
            if stock < 0:
                raise ErrorTransaccion(f"El producto #{pid} quedó con stock negativo.")


# Ejemplo rápido de prueba
if __name__ == "__main__":
    db = sqlite3.connect(":memory:", isolation_level=None)
    db.executescript("""
        CREATE TABLE commercial_products (id INTEGER PRIMARY KEY, sku TEXT, stock INTEGER);
        CREATE TABLE commercial_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER,
            quantity_delta INTEGER, movement_type TEXT, document_type TEXT, document_id INTEGER
        );
        CREATE TABLE commercial_sales (id INTEGER PRIMARY KEY, status TEXT);
        CREATE TABLE commercial_sale_lines (sale_id INTEGER, product_id INTEGER, quantity INTEGER);
        CREATE TABLE commercial_purchases (id INTEGER PRIMARY KEY, status TEXT);
        CREATE TABLE commercial_purchase_lines (purchase_id INTEGER, product_id INTEGER, quantity INTEGER);
        CREATE TABLE commercial_audit (action TEXT, entity TEXT, entity_id INTEGER);

        INSERT INTO commercial_products VALUES (1, 'PROD-01', 10);
        INSERT INTO commercial_purchases VALUES (101, 'Borrador');
        INSERT INTO commercial_purchase_lines VALUES (101, 1, 15);

        INSERT INTO commercial_sales VALUES (201, 'Confirmada');
        INSERT INTO commercial_sale_lines VALUES (201, 1, 4);
        INSERT INTO commercial_movements (product_id, quantity_delta, movement_type, document_type, document_id)
        VALUES (1, -4, 'VENTA', 'VENTA', 201);
        INSERT INTO commercial_audit VALUES ('CONFIRMAR_VENTA', 'venta', 201);
    """)

    agente = AgenteIntegridadTransaccional(db)
    print(agente.confirmar_compra(101))
    print(agente.confirmar_compra(101))  # Prueba que no duplica si se llama dos veces
    print(agente.cancelar_venta(201))    # Devuelve las 4 unidades vendidas
    print(agente.cancelar_venta(999))    # Prueba de error y ROLLBACK

    stock_final = db.execute("SELECT stock FROM commercial_products WHERE id = 1").fetchone()[0]
    print("Stock final (10 + 15 + 4):", stock_final)
