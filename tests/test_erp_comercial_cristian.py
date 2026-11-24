"""Pruebas automatizadas para la aportacion comercial de Cristian Godinez."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest

from src.erp_comercial_cristian import (
    ComercialERP, InvalidOperation, PermissionDenied, StockInsufficient,
)


@pytest.fixture
def setup_erp():
    erp = ComercialERP()
    erp.bootstrap_admin("admin@example.test", "Admin123!")
    admin = erp.login("admin@example.test", "Admin123!")
    erp.create_user(admin, "ventas@example.test", "Ventas123!", "ventas")
    erp.create_user(admin, "compras@example.test", "Compras123!", "compras")
    erp.create_user(admin, "almacen@example.test", "Almacen123!", "almacen")
    ventas = erp.login("ventas@example.test", "Ventas123!")
    compras = erp.login("compras@example.test", "Compras123!")
    almacen = erp.login("almacen@example.test", "Almacen123!")
    erp.add_product(admin, "ERP-001", "Pieza", "125.00", "75.00", 10, 5)
    supplier = erp.add_supplier(compras, "Proveedor Demo")
    customer = erp.add_customer(ventas, "Cliente Demo")
    yield erp, admin, ventas, compras, almacen, supplier, customer
    erp.close()


def test_pu01_sku_duplicado(setup_erp):
    e, admin, *_ = setup_erp
    with pytest.raises(sqlite3.IntegrityError):
        e.add_product(admin, "ERP-001", "Copia", "99")
    assert len(e.search_products(admin, "ERP-001")) == 1


def test_pu02_precio_negativo(setup_erp):
    e, admin, *_ = setup_erp
    with pytest.raises(ValueError):
        e.add_product(admin, "ERP-002", "Pieza 2", "-1")


def test_pu03_cantidad_cero(setup_erp):
    e, _, ventas, _, _, _, customer = setup_erp
    with pytest.raises(ValueError):
        e.create_sale(ventas, customer, [{"sku": "ERP-001", "quantity": 0}])


def test_pu04_stock_insuficiente(setup_erp):
    e, _, ventas, _, _, _, customer = setup_erp
    sale = e.create_sale(ventas, customer, [{"sku": "ERP-001", "quantity": 12}])
    with pytest.raises(StockInsufficient):
        e.confirm_sale(ventas, sale)
    assert e.product_info(ventas, "ERP-001")["stock"] == 10
    assert e.sale_info(ventas, sale)["status"] == "Borrador"


def test_pu05_recepcion_suma_stock(setup_erp):
    e, _, _, compras, _, supplier, _ = setup_erp
    purchase = e.create_purchase(compras, supplier, [{"sku": "ERP-001", "quantity": 8, "unit_cost": "75"}])
    assert e.product_info(compras, "ERP-001")["stock"] == 10
    assert e.confirm_purchase(compras, purchase)["status"] == "Confirmada"
    assert e.product_info(compras, "ERP-001")["stock"] == 18


def test_pu06_venta_resta_stock(setup_erp):
    e, _, ventas, compras, _, supplier, customer = setup_erp
    purchase = e.create_purchase(compras, supplier, [{"sku": "ERP-001", "quantity": 8}])
    e.confirm_purchase(compras, purchase)
    sale = e.create_sale(ventas, customer, [{"sku": "ERP-001", "quantity": 3}])
    e.confirm_sale(ventas, sale)
    assert e.product_info(ventas, "ERP-001")["stock"] == 15


def test_pu07_total_375(setup_erp):
    e, _, ventas, _, _, _, customer = setup_erp
    sale = e.create_sale(ventas, customer, [{"sku": "ERP-001", "quantity": 3}])
    assert e.sale_info(ventas, sale)["total"] == "375.00"


def test_pu08_cancelar_reintegra_stock(setup_erp):
    e, _, ventas, _, _, _, customer = setup_erp
    sale = e.create_sale(ventas, customer, [{"sku": "ERP-001", "quantity": 3}])
    e.confirm_sale(ventas, sale)
    assert e.cancel_sale(ventas, sale, "Error de cliente")["status"] == "Cancelada"
    assert e.product_info(ventas, "ERP-001")["stock"] == 10


def test_pu09_doble_cancelacion_rechazada(setup_erp):
    e, _, ventas, _, _, _, customer = setup_erp
    sale = e.create_sale(ventas, customer, [{"sku": "ERP-001", "quantity": 3}])
    e.confirm_sale(ventas, sale)
    e.cancel_sale(ventas, sale, "Duplicada")
    with pytest.raises(InvalidOperation):
        e.cancel_sale(ventas, sale, "Segundo intento")
    assert e.product_info(ventas, "ERP-001")["stock"] == 10


def test_pu10_rol_ventas_no_ajusta(setup_erp):
    e, _, ventas, *_ = setup_erp
    with pytest.raises(PermissionDenied):
        e.adjust_stock(ventas, "ERP-001", -1, "Ajuste")
    assert e.product_info(ventas, "ERP-001")["stock"] == 10


def test_pu11_alerta_inventario_minimo(setup_erp):
    e, admin, *_ = setup_erp
    e.adjust_stock(admin, "ERP-001", -5, "Salida de prueba")
    assert [x["sku"] for x in e.low_stock(admin)] == ["ERP-001"]


def test_pu12_rollback_si_falla_movimiento(setup_erp):
    e, _, _, compras, _, supplier, _ = setup_erp
    purchase = e.create_purchase(compras, supplier, [{"sku": "ERP-001", "quantity": 8}])
    e.connection.execute("""CREATE TRIGGER test_fail_receipt BEFORE INSERT ON commercial_movements
        WHEN NEW.movement_type = 'RECEPCION' BEGIN SELECT RAISE(ABORT, 'simulated failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        e.confirm_purchase(compras, purchase)
    assert e.product_info(compras, "ERP-001")["stock"] == 10
    assert e.purchase_info(compras, purchase)["status"] == "Borrador"


def test_pf01_catalogo_y_validacion(setup_erp):
    e, admin, *_ = setup_erp
    assert e.product_info(admin, "ERP-001")["price_cents"] == 12500
    with pytest.raises(sqlite3.IntegrityError):
        e.add_product(admin, "ERP-001", "Duplicado", "125")


def test_pf02_recepcion_confirmada(setup_erp):
    e, _, _, compras, _, supplier, _ = setup_erp
    purchase = e.create_purchase(compras, supplier, [{"sku": "ERP-001", "quantity": 8}])
    assert e.product_info(compras, "ERP-001")["stock"] == 10
    e.confirm_purchase(compras, purchase)
    assert e.product_info(compras, "ERP-001")["stock"] == 18


def test_pf03_venta_exitosa(setup_erp):
    e, _, ventas, compras, _, supplier, customer = setup_erp
    e.confirm_purchase(compras, e.create_purchase(compras, supplier, [{"sku": "ERP-001", "quantity": 8}]))
    sale = e.create_sale(ventas, customer, [{"sku": "ERP-001", "quantity": 3}])
    assert e.confirm_sale(ventas, sale)["total"] == "375.00"
    assert e.product_info(ventas, "ERP-001")["stock"] == 15
    assert any(x["movement_type"] == "VENTA" for x in e.movements(ventas, "ERP-001"))


def test_pf04_bloqueo_sin_existencias(setup_erp):
    e, _, ventas, _, _, _, customer = setup_erp
    sale = e.create_sale(ventas, customer, [{"sku": "ERP-001", "quantity": 16}])
    with pytest.raises(StockInsufficient):
        e.confirm_sale(ventas, sale)
    assert e.product_info(ventas, "ERP-001")["stock"] == 10


def test_pf05_cancelacion(setup_erp):
    e, _, ventas, _, _, _, customer = setup_erp
    sale = e.create_sale(ventas, customer, [{"sku": "ERP-001", "quantity": 3}])
    e.confirm_sale(ventas, sale)
    e.cancel_sale(ventas, sale, "Cliente desiste")
    with pytest.raises(InvalidOperation):
        e.cancel_sale(ventas, sale, "Repetida")
    assert e.product_info(ventas, "ERP-001")["stock"] == 10


def test_pf06_permisos(setup_erp):
    e, _, ventas, *_ = setup_erp
    with pytest.raises(PermissionDenied):
        e.adjust_stock(ventas, "ERP-001", 1, "No autorizado")


def test_pf07_reportes_por_sku(setup_erp):
    e, _, ventas, compras, _, supplier, customer = setup_erp
    e.confirm_purchase(compras, e.create_purchase(compras, supplier, [{"sku": "ERP-001", "quantity": 8}]))
    e.confirm_sale(ventas, e.create_sale(ventas, customer, [{"sku": "ERP-001", "quantity": 3}]))
    report = e.report(ventas, sku="ERP-001")
    assert len(report["ventas"]) == 1
    assert len(report["compras"]) == 1
    assert report["ventas"][0]["amount_cents"] == 37500


def test_pi01_integridad_sku_unico(setup_erp):
    e, admin, *_ = setup_erp
    with pytest.raises(sqlite3.IntegrityError):
        e.add_product(admin, "ERP-001", "Producto", "2")


def test_pi02_integridad_referencial(setup_erp):
    e, *_ = setup_erp
    with pytest.raises(sqlite3.IntegrityError):
        e.connection.execute("INSERT INTO commercial_sale_lines (sale_id,product_id,quantity,unit_price_cents) VALUES (999,999,1,100)")


def test_pi03_venta_multilinea_atomicidad(setup_erp):
    e, admin, ventas, _, _, _, customer = setup_erp
    e.add_product(admin, "ERP-002", "Sin Stock", "200.00")
    sale = e.create_sale(ventas, customer, [
        {"sku": "ERP-001", "quantity": 3},
        {"sku": "ERP-002", "quantity": 2},
    ])
    with pytest.raises(StockInsufficient):
        e.confirm_sale(ventas, sale)
    assert e.product_info(ventas, "ERP-001")["stock"] == 10
    assert e.product_info(ventas, "ERP-002")["stock"] == 0
    assert e.sale_info(ventas, sale)["status"] == "Borrador"
    assert not any(m["movement_type"] == "VENTA" for m in e.movements(ventas))


def test_pi04_concurrencia_venta_stock(tmp_path):
    file = str(tmp_path / "erp_parallel.db")
    creator = ComercialERP(file)
    creator.bootstrap_admin("admin@example.test", "Admin123!")
    session = creator.login("admin@example.test", "Admin123!")
    creator.add_product(session, "ERP-001", "Pieza", "125", stock=10)
    customer = creator.add_customer(session, "Cliente")
    first = creator.create_sale(session, customer, [{"sku": "ERP-001", "quantity": 7}])
    second = creator.create_sale(session, customer, [{"sku": "ERP-001", "quantity": 7}])
    creator.close()
    def perform(sale_id):
        instance = ComercialERP(file)
        token = instance.login("admin@example.test", "Admin123!")
        try:
            instance.confirm_sale(token, sale_id)
            return "OK"
        except StockInsufficient:
            return "DENEGADO"
        finally:
            instance.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(perform, [first, second]))
    checker = ComercialERP(file)
    token = checker.login("admin@example.test", "Admin123!")
    assert sorted(outcomes) == ["DENEGADO", "OK"]
    assert checker.product_info(token, "ERP-001")["stock"] == 3
    checker.close()


def test_pi05_cancelacion_sin_duplicados(setup_erp):
    e, _, ventas, _, _, _, customer = setup_erp
    sale = e.create_sale(ventas, customer, [{"sku": "ERP-001", "quantity": 7}])
    e.confirm_sale(ventas, sale)
    e.cancel_sale(ventas, sale, "Motivo")
    with pytest.raises(InvalidOperation):
        e.cancel_sale(ventas, sale, "Motivo")
    assert [m["movement_type"] for m in e.movements(ventas)].count("CANCELACION") == 1


def test_pi06_desactivacion_preserva_historial(setup_erp):
    e, admin, ventas, _, _, _, customer = setup_erp
    sale = e.create_sale(ventas, customer, [{"sku": "ERP-001", "quantity": 2}])
    e.confirm_sale(ventas, sale)
    e.deactivate_product(admin, "ERP-001")
    assert e.sale_info(ventas, sale)["status"] == "Confirmada"
    assert len(e.movements(ventas, "ERP-001")) > 0
    with pytest.raises(InvalidOperation):
        e.create_sale(ventas, customer, [{"sku": "ERP-001", "quantity": 1}])


def test_sesion_incorrecta(setup_erp):
    e, admin, *_ = setup_erp
    e.logout(admin)
    with pytest.raises(PermissionDenied):
        e.low_stock(admin)


def test_credenciales_invalidas(setup_erp):
    e, *_ = setup_erp
    with pytest.raises(PermissionDenied):
        e.login("admin@example.test", "incorrecta")


def test_decimales_exactos(setup_erp):
    e, admin, *_ = setup_erp
    with pytest.raises(ValueError):
        e.add_product(admin, "ERP-004", "Malo", "2.999")
    pid = e.add_product(admin, "ERP-005", "Exacto", "1.20")
    assert pid > 0
    assert e.product_info(admin, "ERP-005")["price_cents"] == 120


def test_compra_doble_confirmacion_no_duplica_stock(setup_erp):
    e, _, _, compras, _, supplier, _ = setup_erp
    pid = e.create_purchase(compras, supplier, [{"sku": "ERP-001", "quantity": 8}])
    e.confirm_purchase(compras, pid)
    with pytest.raises(InvalidOperation):
        e.confirm_purchase(compras, pid)
    assert e.product_info(compras, "ERP-001")["stock"] == 18


def test_ajuste_excesivo_rechazado(setup_erp):
    e, _, _, _, almacen, _, _ = setup_erp
    with pytest.raises(StockInsufficient):
        e.adjust_stock(almacen, "ERP-001", -11, "Error")
    assert e.product_info(almacen, "ERP-001")["stock"] == 10


def test_rollback_venta_por_error_de_movimientos(setup_erp):
    e, _, ventas, _, _, _, customer = setup_erp
    sale = e.create_sale(ventas, customer, [{"sku": "ERP-001", "quantity": 3}])
    e.connection.execute("""CREATE TRIGGER test_fail_sale BEFORE INSERT ON commercial_movements
        WHEN NEW.movement_type = 'VENTA' BEGIN SELECT RAISE(ABORT, 'simulated failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        e.confirm_sale(ventas, sale)
    assert e.sale_info(ventas, sale)["status"] == "Borrador"
    assert e.product_info(ventas, "ERP-001")["stock"] == 10
