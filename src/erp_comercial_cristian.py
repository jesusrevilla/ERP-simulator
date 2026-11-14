"""Prototipo independiente de inventario, compras y ventas para ERP-Simulator.

Utiliza solo bibliotecas estándar y SQLite para permitir pruebas reproducibles.
No reemplaza el backend PostgreSQL/MRP preexistente del repositorio.
"""

import hashlib
import hmac
import os
import secrets
import sqlite3
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from pathlib import Path


SCHEMA = Path(__file__).resolve().parents[1] / "sql" / "comercial_schema_sqlite.sql"
ROLES = {"administrador", "compras", "ventas", "almacen"}


class ERPError(Exception):
    pass


class PermissionDenied(ERPError):
    pass


class StockInsufficient(ERPError):
    pass


class InvalidOperation(ERPError):
    pass


def _int_positive(value, name="Cantidad"):
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} debe ser entero positivo")
    return value


def _int_nonnegative(value, name="Valor"):
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} debe ser entero no negativo")
    return value


def _money(value, positive=False):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("Importe invalido") from None
    if not amount.is_finite() or (amount <= 0 if positive else amount < 0):
        raise ValueError("Importe fuera de rango")
    if amount.as_tuple().exponent < -2 and amount != amount.quantize(Decimal("0.01")):
        raise ValueError("Solo se admiten dos decimales")
    cents = amount * 100
    if cents != cents.to_integral_value():
        raise ValueError("Solo se admiten dos decimales")
    return int(cents)


def money_display(cents):
    return f"{Decimal(cents) / 100:.2f}"


class ComercialERP:
    def __init__(self, database=":memory:"):
        self.connection = sqlite3.connect(database, isolation_level=None, timeout=10, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA busy_timeout = 10000")
        if database != ":memory:":
            self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        self.sessions = {}

    def close(self):
        self.connection.close()

    @contextmanager
    def transaction(self):
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield self.connection
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def _audit(self, user_id, action, entity, entity_id, details=""):
        self.connection.execute(
            "INSERT INTO commercial_audit (user_id,action,entity,entity_id,details) VALUES (?,?,?,?,?)",
            (user_id, action, entity, entity_id, details),
        )

    def _record_movement(self, product_id, user_id, movement_type, delta, doc_type, doc_id, reason=""):
        self.connection.execute(
            """INSERT INTO commercial_movements
            (product_id,user_id,movement_type,quantity_delta,document_type,document_id,reason)
            VALUES (?,?,?,?,?,?,?)""",
            (product_id, user_id, movement_type, delta, doc_type, doc_id, reason),
        )

    def _hash(self, password, salt):
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000).hex()

    def bootstrap_admin(self, email, password):
        email = str(email).strip().lower()
        if not email or len(password) < 8:
            raise ValueError("Correo y contrasena de al menos 8 caracteres obligatorios")
        with self.transaction():
            if self.connection.execute("SELECT COUNT(*) FROM commercial_users").fetchone()[0]:
                raise InvalidOperation("El administrador inicial ya existe")
            salt = os.urandom(16)
            result = self.connection.execute(
                "INSERT INTO commercial_users (email,salt,password_hash,role) VALUES (?,?,?,?)",
                (email, salt.hex(), self._hash(password, salt), "administrador"),
            )
            return result.lastrowid

    def login(self, email, password):
        user = self.connection.execute(
            "SELECT * FROM commercial_users WHERE email = ? AND active = 1", (str(email).strip().lower(),)
        ).fetchone()
        if not user or not hmac.compare_digest(self._hash(password, bytes.fromhex(user["salt"])), user["password_hash"]):
            raise PermissionDenied("Credenciales invalidas")
        token = secrets.token_urlsafe(32)
        self.sessions[token] = user["id"]
        return token

    def logout(self, token):
        self.sessions.pop(token, None)

    def _require(self, token, *roles):
        user_id = self.sessions.get(token)
        if user_id is None:
            raise PermissionDenied("Sesion no valida")
        user = self.connection.execute(
            "SELECT id,role FROM commercial_users WHERE id = ? AND active = 1", (user_id,)
        ).fetchone()
        if not user or (roles and user["role"] not in roles):
            raise PermissionDenied("Permisos insuficientes")
        return user["id"]

    def create_user(self, token, email, password, role):
        admin_id = self._require(token, "administrador")
        if role not in ROLES or len(password) < 8 or not str(email).strip():
            raise ValueError("Usuario, contrasena o rol invalidos")
        with self.transaction():
            salt = os.urandom(16)
            cur = self.connection.execute(
                "INSERT INTO commercial_users (email,salt,password_hash,role) VALUES (?,?,?,?)",
                (str(email).strip().lower(), salt.hex(), self._hash(password, salt), role),
            )
            self._audit(admin_id, "CREAR_USUARIO", "usuario", cur.lastrowid, role)
            return cur.lastrowid

    def add_product(self, token, sku, name, price, cost=0, stock=0, minimum_stock=0):
        user_id = self._require(token, "administrador")
        sku, name = str(sku).strip().upper(), str(name).strip()
        if not sku or not name:
            raise ValueError("SKU y nombre son obligatorios")
        price_cents, cost_cents = _money(price, positive=True), _money(cost)
        _int_nonnegative(stock, "Stock")
        _int_nonnegative(minimum_stock, "Stock minimo")
        with self.transaction():
            cur = self.connection.execute(
                """INSERT INTO commercial_products (sku,name,price_cents,cost_cents,stock,minimum_stock)
                VALUES (?,?,?,?,?,?)""", (sku, name, price_cents, cost_cents, stock, minimum_stock)
            )
            pid = cur.lastrowid
            if stock:
                self._record_movement(pid, user_id, "ALTA", stock, "PRODUCTO", pid, "Inventario inicial")
            self._audit(user_id, "ALTA_PRODUCTO", "producto", pid, sku)
            return pid

    def add_supplier(self, token, name, email=""):
        user_id = self._require(token, "administrador", "compras")
        if not str(name).strip():
            raise ValueError("Nombre obligatorio")
        with self.transaction():
            cur = self.connection.execute(
                "INSERT INTO commercial_suppliers (name,email) VALUES (?,?)", (str(name).strip(), str(email).strip())
            )
            self._audit(user_id, "ALTA_PROVEEDOR", "proveedor", cur.lastrowid)
            return cur.lastrowid

    def add_customer(self, token, name, email=""):
        user_id = self._require(token, "administrador", "ventas")
        if not str(name).strip():
            raise ValueError("Nombre obligatorio")
        with self.transaction():
            cur = self.connection.execute(
                "INSERT INTO commercial_customers (name,email) VALUES (?,?)", (str(name).strip(), str(email).strip())
            )
            self._audit(user_id, "ALTA_CLIENTE", "cliente", cur.lastrowid)
            return cur.lastrowid

    def _active_partner(self, table, partner_id):
        if type(partner_id) is not int:
            raise ValueError("ID invalido")
        if not self.connection.execute(f"SELECT id FROM {table} WHERE id = ? AND active = 1", (partner_id,)).fetchone():
            raise InvalidOperation("Cliente o proveedor inexistente o inactivo")

    def _active_product(self, sku):
        row = self.connection.execute("SELECT * FROM commercial_products WHERE sku = ? AND active = 1", (str(sku).strip().upper(),)).fetchone()
        if not row:
            raise InvalidOperation("Producto inexistente o inactivo")
        return row

    def create_purchase(self, token, supplier_id, lines):
        user_id = self._require(token, "administrador", "compras")
        if not lines or not isinstance(lines, list):
            raise ValueError("La compra requiere renglones")
        with self.transaction():
            self._active_partner("commercial_suppliers", supplier_id)
            cur = self.connection.execute(
                "INSERT INTO commercial_purchases (supplier_id,user_id) VALUES (?,?)", (supplier_id, user_id)
            )
            purchase_id = cur.lastrowid
            for line in lines:
                product = self._active_product(line["sku"])
                qty = _int_positive(line["quantity"])
                cost = _money(line.get("unit_cost", money_display(product["cost_cents"])))
                self.connection.execute(
                    "INSERT INTO commercial_purchase_lines (purchase_id,product_id,quantity,unit_cost_cents) VALUES (?,?,?,?)",
                    (purchase_id, product["id"], qty, cost),
                )
            self._audit(user_id, "COMPRA_BORRADOR", "compra", purchase_id)
            return purchase_id

    def confirm_purchase(self, token, purchase_id):
        user_id = self._require(token, "administrador", "compras")
        with self.transaction():
            purchase = self.connection.execute("SELECT status FROM commercial_purchases WHERE id = ?", (purchase_id,)).fetchone()
            if not purchase or purchase["status"] != "Borrador":
                raise InvalidOperation("Compra inexistente o confirmada")
            lines = self.connection.execute("SELECT * FROM commercial_purchase_lines WHERE purchase_id = ?", (purchase_id,)).fetchall()
            if not lines:
                raise InvalidOperation("Compra sin detalles")
            for line in lines:
                self.connection.execute(
                    "UPDATE commercial_products SET stock = stock + ? WHERE id = ?", (line["quantity"], line["product_id"])
                )
                self._record_movement(line["product_id"], user_id, "RECEPCION", line["quantity"], "COMPRA", purchase_id)
            self.connection.execute(
                "UPDATE commercial_purchases SET status = 'Confirmada', confirmed_at = CURRENT_TIMESTAMP WHERE id = ?", (purchase_id,)
            )
            self._audit(user_id, "CONFIRMAR_COMPRA", "compra", purchase_id)
        return self.purchase_info(token, purchase_id)

    def create_sale(self, token, customer_id, lines):
        user_id = self._require(token, "administrador", "ventas")
        if not lines or not isinstance(lines, list):
            raise ValueError("La venta requiere renglones")
        with self.transaction():
            self._active_partner("commercial_customers", customer_id)
            cur = self.connection.execute(
                "INSERT INTO commercial_sales (customer_id,user_id) VALUES (?,?)", (customer_id, user_id)
            )
            sale_id = cur.lastrowid
            for line in lines:
                product = self._active_product(line["sku"])
                qty = _int_positive(line["quantity"])
                self.connection.execute(
                    "INSERT INTO commercial_sale_lines (sale_id,product_id,quantity,unit_price_cents) VALUES (?,?,?,?)",
                    (sale_id, product["id"], qty, product["price_cents"]),
                )
            self._audit(user_id, "VENTA_BORRADOR", "venta", sale_id)
            return sale_id

    def confirm_sale(self, token, sale_id):
        user_id = self._require(token, "administrador", "ventas")
        with self.transaction():
            sale = self.connection.execute("SELECT status FROM commercial_sales WHERE id = ?", (sale_id,)).fetchone()
            if not sale or sale["status"] != "Borrador":
                raise InvalidOperation("Venta inexistente o procesada")
            lines = self.connection.execute("SELECT * FROM commercial_sale_lines WHERE sale_id = ?", (sale_id,)).fetchall()
            if not lines:
                raise InvalidOperation("Venta sin detalles")
            for line in lines:
                cur = self.connection.execute(
                    "UPDATE commercial_products SET stock = stock - ? WHERE id = ? AND stock >= ?",
                    (line["quantity"], line["product_id"], line["quantity"]),
                )
                if cur.rowcount != 1:
                    raise StockInsufficient("Existencias insuficientes")
                self._record_movement(line["product_id"], user_id, "VENTA", -line["quantity"], "VENTA", sale_id)
            self.connection.execute(
                "UPDATE commercial_sales SET status = 'Confirmada', confirmed_at = CURRENT_TIMESTAMP WHERE id = ?", (sale_id,)
            )
            self._audit(user_id, "CONFIRMAR_VENTA", "venta", sale_id)
        return self.sale_info(token, sale_id)

    def cancel_sale(self, token, sale_id, reason):
        user_id = self._require(token, "administrador", "ventas")
        if not str(reason).strip():
            raise ValueError("Motivo de cancelacion obligatorio")
        with self.transaction():
            sale = self.connection.execute("SELECT status FROM commercial_sales WHERE id = ?", (sale_id,)).fetchone()
            if not sale or sale["status"] != "Confirmada":
                raise InvalidOperation("Solo es posible cancelar una vez una venta confirmada")
            lines = self.connection.execute("SELECT * FROM commercial_sale_lines WHERE sale_id = ?", (sale_id,)).fetchall()
            for line in lines:
                self.connection.execute("UPDATE commercial_products SET stock = stock + ? WHERE id = ?", (line["quantity"], line["product_id"]))
                self._record_movement(line["product_id"], user_id, "CANCELACION", line["quantity"], "VENTA", sale_id, reason)
            self.connection.execute(
                "UPDATE commercial_sales SET status = 'Cancelada', cancelled_at = CURRENT_TIMESTAMP, cancellation_reason = ? WHERE id = ?",
                (str(reason).strip(), sale_id),
            )
            self._audit(user_id, "CANCELAR_VENTA", "venta", sale_id, str(reason).strip())
        return self.sale_info(token, sale_id)

    def adjust_stock(self, token, sku, delta, reason):
        user_id = self._require(token, "administrador", "almacen")
        if type(delta) is not int or delta == 0 or not str(reason).strip():
            raise ValueError("Ajuste y motivo obligatorios")
        with self.transaction():
            product = self._active_product(sku)
            if product["stock"] + delta < 0:
                raise StockInsufficient("Un ajuste no puede dejar stock negativo")
            self.connection.execute("UPDATE commercial_products SET stock = stock + ? WHERE id = ?", (delta, product["id"]))
            self._record_movement(product["id"], user_id, "AJUSTE", delta, "PRODUCTO", product["id"], str(reason).strip())
            self._audit(user_id, "AJUSTAR_STOCK", "producto", product["id"], str(reason).strip())
        return self.product_info(token, sku)

    def deactivate_product(self, token, sku):
        user_id = self._require(token, "administrador")
        with self.transaction():
            product = self._active_product(sku)
            self.connection.execute("UPDATE commercial_products SET active = 0 WHERE id = ?", (product["id"],))
            self._audit(user_id, "DESACTIVAR_PRODUCTO", "producto", product["id"])

    def product_info(self, token, sku):
        self._require(token, *ROLES)
        row = self.connection.execute("SELECT * FROM commercial_products WHERE sku = ?", (str(sku).strip().upper(),)).fetchone()
        if not row:
            raise InvalidOperation("Producto desconocido")
        return dict(row)

    def purchase_info(self, token, purchase_id):
        self._require(token, *ROLES)
        row = self.connection.execute("SELECT * FROM commercial_purchases WHERE id = ?", (purchase_id,)).fetchone()
        if not row:
            raise InvalidOperation("Compra desconocida")
        return dict(row)

    def sale_info(self, token, sale_id):
        self._require(token, *ROLES)
        row = self.connection.execute("SELECT * FROM commercial_sales WHERE id = ?", (sale_id,)).fetchone()
        if not row:
            raise InvalidOperation("Venta desconocida")
        total = self.connection.execute(
            "SELECT COALESCE(SUM(quantity * unit_price_cents),0) FROM commercial_sale_lines WHERE sale_id = ?", (sale_id,)
        ).fetchone()[0]
        return {**dict(row), "total_cents": total, "total": money_display(total)}

    def low_stock(self, token):
        self._require(token, *ROLES)
        return [dict(r) for r in self.connection.execute(
            "SELECT sku,name,stock,minimum_stock FROM commercial_products WHERE active = 1 AND stock <= minimum_stock ORDER BY sku"
        ).fetchall()]

    def search_products(self, token, keyword=""):
        self._require(token, *ROLES)
        term = "%" + str(keyword).lower().replace("%", "\\%").replace("_", "\\_") + "%"
        return [dict(r) for r in self.connection.execute(
            "SELECT sku,name,stock,price_cents,active FROM commercial_products WHERE lower(sku) LIKE ? ESCAPE '\\' OR lower(name) LIKE ? ESCAPE '\\' ORDER BY sku",
            (term, term),
        ).fetchall()]

    def movements(self, token, sku=None):
        self._require(token, *ROLES)
        if sku is None:
            rows = self.connection.execute("""SELECT m.*,p.sku FROM commercial_movements m
                JOIN commercial_products p ON p.id=m.product_id ORDER BY m.id""").fetchall()
        else:
            rows = self.connection.execute("""SELECT m.*,p.sku FROM commercial_movements m
                JOIN commercial_products p ON p.id=m.product_id WHERE p.sku=? ORDER BY m.id""",
                (str(sku).strip().upper(),)).fetchall()
        return [dict(r) for r in rows]

    def report(self, token, since=None, until=None, sku=None):
        self._require(token, *ROLES)
        for field in (since, until):
            if field is not None and (len(field) != 10 or field[4] != "-" or field[7] != "-"):
                raise ValueError("Usar fecha YYYY-MM-DD")
        filters = []
        params = []
        if since:
            filters.append("date(h.created_at) >= ?")
            params.append(since)
        if until:
            filters.append("date(h.created_at) <= ?")
            params.append(until)
        if sku:
            filters.append("p.sku = ?")
            params.append(str(sku).strip().upper())
        def query(kind):
            if kind == "ventas":
                table, details, fk, amount = "commercial_sales", "commercial_sale_lines", "sale_id", "unit_price_cents"
            else:
                table, details, fk, amount = "commercial_purchases", "commercial_purchase_lines", "purchase_id", "unit_cost_cents"
            sql = f"""SELECT h.id,p.sku,h.status,h.created_at,d.quantity,
                (d.quantity * d.{amount}) AS amount_cents FROM {table} h
                JOIN {details} d ON d.{fk} = h.id
                JOIN commercial_products p ON p.id = d.product_id"""
            if filters:
                sql += " WHERE " + " AND ".join(filters)
            sql += " ORDER BY h.id,d.id"
            return [dict(r) for r in self.connection.execute(sql, params).fetchall()]
        return {"ventas": query("ventas"), "compras": query("compras"), "alertas": self.low_stock(token)}
