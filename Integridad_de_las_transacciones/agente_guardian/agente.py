"""Agente de conciliación de integridad para el módulo comercial de ERP-Simulator.

Este agente NO registra ventas ni modifica inventario. Revisa los datos ya
confirmados del esquema SQLite `commercial_*` y devuelve alertas concretas
cuando detecta inconsistencias entre documentos, movimientos y auditoría.

Es complementario a GestorTransaccionalERP: aquel ejecuta transacciones;
este detecta discrepancias posteriores (RF-12).
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


# Tablas y columnas existentes en sql/comercial_schema_sqlite.sql.
# No se crean tablas nuevas ni se altera la base de datos.
_COLUMNAS = {
    "commercial_products": {"id", "sku", "stock"},
    "commercial_movements": {
        "id", "product_id", "quantity_delta", "movement_type",
        "document_type", "document_id",
    },
    "commercial_sales": {"id", "status"},
    "commercial_sale_lines": {"sale_id", "product_id", "quantity"},
    "commercial_purchases": {"id", "status"},
    "commercial_purchase_lines": {"purchase_id", "product_id", "quantity"},
    "commercial_audit": {"action", "entity", "entity_id"},
}


class EsquemaNoCompatible(Exception):
    """La base no tiene las tablas esperadas del módulo comercial."""


def _alertar(alertas: list[dict[str, Any]], codigo: str,
             entidad: str, referencia: Any, detalle: str) -> None:
    alertas.append({
        "codigo": codigo,
        "entidad": entidad,
        "referencia": referencia,
        "detalle": detalle,
    })


def _comprobar_esquema(conn: sqlite3.Connection) -> None:
    tablas = {fila[0] for fila in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    )}
    faltantes = sorted(set(_COLUMNAS) - tablas)
    if faltantes:
        raise EsquemaNoCompatible("Faltan tablas comerciales: " + ", ".join(faltantes))

    for tabla, requeridas in _COLUMNAS.items():
        # tabla proviene de un conjunto constante del código, no del usuario.
        existentes = {fila[1] for fila in conn.execute(f"PRAGMA table_info({tabla})")}
        ausentes = sorted(requeridas - existentes)
        if ausentes:
            raise EsquemaNoCompatible(
                f"Faltan columnas de {tabla}: " + ", ".join(ausentes)
            )


def _revisar_existencias(conn: sqlite3.Connection, alertas: list[dict]) -> int:
    """El stock actual debe coincidir con la suma histórica de movimientos."""
    filas = conn.execute("""
        SELECT p.id, p.sku, p.stock,
               COALESCE(SUM(m.quantity_delta), 0) AS calculado
        FROM commercial_products AS p
        LEFT JOIN commercial_movements AS m ON m.product_id = p.id
        GROUP BY p.id, p.sku, p.stock
        ORDER BY p.id
    """).fetchall()
    for producto_id, sku, stock, calculado in filas:
        if stock != calculado:
            _alertar(alertas, "STOCK_NO_CONCILIADO", "producto", producto_id,
                     f"{sku}: stock registrado={stock}; movimientos={calculado}")
    return len(filas)


def _totales_lineas(conn: sqlite3.Connection, tabla: str, fk: str) -> dict:
    """Agrupa cantidades; también admite varias líneas del mismo producto."""
    return {
        (doc_id, product_id): cantidad
        for doc_id, product_id, cantidad in conn.execute(
            f"SELECT {fk}, product_id, SUM(quantity) FROM {tabla} "
            f"GROUP BY {fk}, product_id"
        )
    }


def _totales_movimientos(conn: sqlite3.Connection, doc_tipo: str) -> dict:
    return {
        (doc_id, product_id, movimiento): cantidad
        for doc_id, product_id, movimiento, cantidad in conn.execute("""
            SELECT document_id, product_id, movement_type, SUM(quantity_delta)
            FROM commercial_movements
            WHERE document_type = ?
            GROUP BY document_id, product_id, movement_type
        """, (doc_tipo,))
    }


def _revisar_documentos(conn: sqlite3.Connection,
                        alertas: list[dict]) -> tuple[int, int]:
    ventas = dict(conn.execute("SELECT id, status FROM commercial_sales"))
    compras = dict(conn.execute("SELECT id, status FROM commercial_purchases"))
    venta_lineas = _totales_lineas(conn, "commercial_sale_lines", "sale_id")
    compra_lineas = _totales_lineas(conn, "commercial_purchase_lines", "purchase_id")
    mov_ventas = _totales_movimientos(conn, "VENTA")
    mov_compras = _totales_movimientos(conn, "COMPRA")

    for (doc_id, product_id, tipo), cantidad in mov_ventas.items():
        if doc_id not in ventas:
            _alertar(alertas, "MOVIMIENTO_SIN_VENTA", "venta", doc_id,
                     f"Producto {product_id}; movimiento {tipo}={cantidad}")
        elif tipo not in {"VENTA", "CANCELACION"}:
            _alertar(alertas, "TIPO_MOVIMIENTO_INVALIDO", "venta", doc_id,
                     f"Movimiento {tipo} no corresponde a una venta")

    for (doc_id, product_id, tipo), cantidad in mov_compras.items():
        if doc_id not in compras:
            _alertar(alertas, "MOVIMIENTO_SIN_COMPRA", "compra", doc_id,
                     f"Producto {product_id}; movimiento {tipo}={cantidad}")
        elif tipo != "RECEPCION":
            _alertar(alertas, "TIPO_MOVIMIENTO_INVALIDO", "compra", doc_id,
                     f"Movimiento {tipo} no corresponde a una compra")

    for venta_id, estado in ventas.items():
        productos = {p for (v, p) in venta_lineas if v == venta_id}
        productos |= {p for (v, p, _) in mov_ventas if v == venta_id}
        if not productos and estado != "Borrador":
            _alertar(alertas, "VENTA_SIN_PARTIDAS", "venta", venta_id,
                     "Documento procesado sin productos")
        for producto_id in sorted(productos):
            cantidad = venta_lineas.get((venta_id, producto_id), 0)
            venta_real = mov_ventas.get((venta_id, producto_id, "VENTA"), 0)
            cancel_real = mov_ventas.get((venta_id, producto_id, "CANCELACION"), 0)
            venta_esperada = -cantidad if estado in {"Confirmada", "Cancelada"} else 0
            cancel_esperada = cantidad if estado == "Cancelada" else 0
            if venta_real != venta_esperada:
                _alertar(alertas, "SALIDA_VENTA_INCONSISTENTE", "venta", venta_id,
                         f"Producto {producto_id}: salida={venta_real}; "
                         f"esperada={venta_esperada}; estado={estado}")
            if cancel_real != cancel_esperada:
                _alertar(alertas, "REVERSION_INCONSISTENTE", "venta", venta_id,
                         f"Producto {producto_id}: devolución={cancel_real}; "
                         f"esperada={cancel_esperada}; estado={estado}")

    for compra_id, estado in compras.items():
        productos = {p for (c, p) in compra_lineas if c == compra_id}
        productos |= {p for (c, p, _) in mov_compras if c == compra_id}
        if not productos and estado == "Confirmada":
            _alertar(alertas, "COMPRA_SIN_PARTIDAS", "compra", compra_id,
                     "Documento confirmado sin productos")
        for producto_id in sorted(productos):
            cantidad = compra_lineas.get((compra_id, producto_id), 0)
            recibido = mov_compras.get((compra_id, producto_id, "RECEPCION"), 0)
            esperado = cantidad if estado == "Confirmada" else 0
            if recibido != esperado:
                _alertar(alertas, "RECEPCION_INCONSISTENTE", "compra", compra_id,
                         f"Producto {producto_id}: recibido={recibido}; "
                         f"esperado={esperado}; estado={estado}")

    return len(ventas), len(compras)


def _revisar_bitacora(conn: sqlite3.Connection, alertas: list[dict]) -> None:
    contadores = {
        (entidad, entidad_id, accion): cantidad
        for entidad, entidad_id, accion, cantidad in conn.execute("""
            SELECT entity, entity_id, action, COUNT(*)
            FROM commercial_audit
            WHERE action IN ('CONFIRMAR_VENTA', 'CANCELAR_VENTA', 'CONFIRMAR_COMPRA')
            GROUP BY entity, entity_id, action
        """)
    }

    for venta_id, estado in conn.execute("SELECT id, status FROM commercial_sales"):
        esperado = {"CONFIRMAR_VENTA": int(estado in {"Confirmada", "Cancelada"}),
                    "CANCELAR_VENTA": int(estado == "Cancelada")}
        for accion, cantidad_esperada in esperado.items():
            real = contadores.get(("venta", venta_id, accion), 0)
            if real != cantidad_esperada:
                _alertar(alertas, "BITACORA_INCONSISTENTE", "venta", venta_id,
                         f"{accion}: registros={real}; esperados={cantidad_esperada}")

    for compra_id, estado in conn.execute("SELECT id, status FROM commercial_purchases"):
        real = contadores.get(("compra", compra_id, "CONFIRMAR_COMPRA"), 0)
        esperado = int(estado == "Confirmada")
        if real != esperado:
            _alertar(alertas, "BITACORA_INCONSISTENTE", "compra", compra_id,
                     f"CONFIRMAR_COMPRA: registros={real}; esperados={esperado}")

    for (entidad, documento_id, accion), cantidad in contadores.items():
        if ((entidad == "venta" and not conn.execute(
                "SELECT 1 FROM commercial_sales WHERE id=?", (documento_id,)
             ).fetchone()) or
            (entidad == "compra" and not conn.execute(
                "SELECT 1 FROM commercial_purchases WHERE id=?", (documento_id,)
             ).fetchone())):
            _alertar(alertas, "AUDITORIA_SIN_DOCUMENTO", entidad, documento_id,
                     f"{accion} registra {cantidad} evento(s) sin documento")


def _revisar_referencias(conn: sqlite3.Connection, alertas: list[dict]) -> None:
    for tabla, fila, padre, _ in conn.execute("PRAGMA foreign_key_check"):
        _alertar(alertas, "REFERENCIA_ROTA", tabla, fila,
                 f"Falta un registro relacionado en {padre}")


class AgenteGuardian:
    """Agente de solo lectura que detecta diferencias en el ERP comercial."""

    def __init__(self, base_datos: str | Path | sqlite3.Connection):
        """Acepta la ruta de un SQLite existente o una conexión ya abierta."""
        self.base_datos = base_datos

    def analizar(self) -> dict[str, Any]:
        """Devuelve las alertas; no cambia existencias, pedidos ni auditorías."""
        if isinstance(self.base_datos, sqlite3.Connection):
            return self._analizar_conexion(self.base_datos)

        # Solo lectura: no crea una base nueva por error si la ruta no existe.
        uri = Path(self.base_datos).expanduser().resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=10)) as conn:
            conn.execute("PRAGMA query_only=ON")
            conn.execute("BEGIN")  # Instantánea consistente durante el análisis.
            try:
                return self._analizar_conexion(conn)
            finally:
                conn.rollback()  # Solo cierra la lectura; no hay cambios que revertir.

    @staticmethod
    def _analizar_conexion(conn: sqlite3.Connection) -> dict[str, Any]:
        _comprobar_esquema(conn)
        alertas: list[dict[str, Any]] = []
        productos = _revisar_existencias(conn, alertas)
        ventas, compras = _revisar_documentos(conn, alertas)
        _revisar_bitacora(conn, alertas)
        _revisar_referencias(conn, alertas)
        alertas.sort(key=lambda a: (a["codigo"], a["entidad"], str(a["referencia"]), a["detalle"]))
        return {
            "integridad_ok": not alertas,
            "total_alertas": len(alertas),
            "registros_revisados": {"productos": productos, "ventas": ventas, "compras": compras},
            "alertas": alertas,
        }


def _principal() -> int:
    """Presenta las alertas por consola, sin crear un archivo JSON."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Conciliación de integridad del ERP comercial (solo lectura)"
    )
    parser.add_argument("base_datos", help="Ruta del archivo SQLite comercial")
    argumentos = parser.parse_args()
    try:
        resultado = AgenteGuardian(argumentos.base_datos).analizar()
    except (sqlite3.Error, EsquemaNoCompatible, OSError) as error:
        parser.exit(1, f"No se pudo revisar la base de datos: {error}\n")

    print("Integridad correcta" if resultado["integridad_ok"] else "Se detectaron inconsistencias")
    print("Registros revisados:", resultado["registros_revisados"])
    print("Alertas:", resultado["total_alertas"])
    for alerta in resultado["alertas"]:
        print(f"- [{alerta['codigo']}] {alerta['entidad']} "
              f"{alerta['referencia']}: {alerta['detalle']}")
    return 0 if resultado["integridad_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(_principal())
