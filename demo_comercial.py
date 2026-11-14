"""Demostracion reproducible en consola del ERP de inventario, compras y ventas."""
from src.erp_comercial_cristian import ComercialERP


def main():
    erp = ComercialERP()
    erp.bootstrap_admin("admin@techassembly.test", "Demo123!")
    admin = erp.login("admin@techassembly.test", "Demo123!")
    erp.add_product(admin, "ERP-001", "Componente Gaming PC", "125.00", "80.00", 10, 5)
    supplier = erp.add_supplier(admin, "Componentes del Bajio")
    customer = erp.add_customer(admin, "TechAssembly S.A.")

    purchase = erp.create_purchase(admin, supplier, [
        {"sku": "ERP-001", "quantity": 8, "unit_cost": "80.00"},
    ])
    print("Compra borrador | Stock:", erp.product_info(admin, "ERP-001")["stock"])
    erp.confirm_purchase(admin, purchase)
    print("Compra confirmada | Stock:", erp.product_info(admin, "ERP-001")["stock"])

    sale = erp.create_sale(admin, customer, [{"sku": "ERP-001", "quantity": 3}])
    sale_details = erp.confirm_sale(admin, sale)
    print("Venta confirmada | Total: $", sale_details["total"], sep="")
    print("Stock tras venta:", erp.product_info(admin, "ERP-001")["stock"])

    erp.cancel_sale(admin, sale, "Demostracion de cancelacion")
    print("Venta cancelada | Stock:", erp.product_info(admin, "ERP-001")["stock"])
    print("Movimientos registrados:", len(erp.movements(admin, "ERP-001")))
    print("Ventas en reporte:", len(erp.report(admin, sku="ERP-001")["ventas"]))
    erp.close()


if __name__ == "__main__":
    main()
