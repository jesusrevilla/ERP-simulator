"""Pruebas unitarias, funcionales y de integridad para Recibos y Entregas (MongoDB + Neo4j + SQL)."""

import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RECIBOS_DIR = REPO_ROOT / "Recibos y las entregas"


def _load_module(module_name: str, filename: str):
    path = RECIBOS_DIR / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


mongo_mod = _load_module("mongodb_recibos_entregas", "mongodb_recibos_entregas.py")
neo4j_mod = _load_module("neo4j_recibos_entregas", "neo4j_recibos_entregas.py")
integ_mod = _load_module("integracion_pg_neo4j_recibos", "integracion_pg_neo4j_recibos.py")


class FakeRecord:
    def __init__(self, data):
        self._data = data

    def data(self):
        return dict(self._data)


class FakeNeo4jDriver:
    """Driver simulado para validar Cypher parametrizado y flujo de grafo sin servidor externo."""

    def __init__(self):
        self.calls = []
        self.proveedores = {}
        self.clientes = {}
        self.almacenes = {}
        self.productos = {}
        self.stock = {}
        self.ocs = {}
        self.recibos = {}
        self.ovs = {}
        self.movimientos = []

    def execute_query(self, query, database_=None, **params):
        self.calls.append((query, params))

        if "MERGE (p:Proveedor" in query:
            self.proveedores[params["codigo_proveedor"]] = {
                "codigo_proveedor": params["codigo_proveedor"],
                "nombre": params["nombre"],
                "estatus": params["estatus"],
                "activo": params["estatus"] == "ACTIVO",
            }
            return [FakeRecord(self.proveedores[params["codigo_proveedor"]])], None, None

        if "MERGE (c:Cliente" in query:
            self.clientes[params["codigo_cliente"]] = dict(params)
            return [FakeRecord({"codigo_cliente": params["codigo_cliente"]})], None, None

        if "MERGE (a:Almacen" in query:
            self.almacenes[params["codigo_almacen"]] = dict(params)
            return [FakeRecord({"codigo_almacen": params["codigo_almacen"]})], None, None

        if "MERGE (pr:Producto" in query:
            self.productos[params["codigo_sku"]] = dict(params)
            self.stock.setdefault((params["codigo_almacen"], params["codigo_sku"]), {"stock_actual": 0.0, "stock_danado": 0.0})
            return [FakeRecord({"codigo_sku": params["codigo_sku"]})], None, None

        if "MERGE (oc:OrdenCompra" in query:
            self.ocs[params["codigo_oc"]] = {
                "codigo_oc": params["codigo_oc"],
                "codigo_proveedor": params["codigo_proveedor"],
                "codigo_almacen": params["codigo_almacen"],
                "estado": params["estado"],
                "lineas": [
                    {
                        "codigo_sku": l["codigo_sku"],
                        "cantidad_solicitada": float(l["cantidad_solicitada"]),
                        "cantidad_recibida": 0.0,
                    }
                    for l in params["lineas"]
                ],
            }
            return [FakeRecord({"codigo_oc": params["codigo_oc"]})], None, None

        if "SET r.estado = 'APROBADO'" in query:
            rec = self.recibos[params["codigo_recibo"]]
            oc = self.ocs[rec["codigo_oc"]]
            alm = oc["codigo_almacen"]
            for linea in rec["lineas"]:
                sku = linea["codigo_sku"]
                prev = self.stock[(alm, sku)]["stock_actual"]
                aceptada = float(linea["cantidad_aceptada"])
                danada = float(linea.get("cantidad_danada", 0.0))
                self.stock[(alm, sku)]["stock_actual"] = prev + aceptada
                self.stock[(alm, sku)]["stock_danado"] += danada
                if aceptada > 0:
                    self.movimientos.append(
                        {"sku": sku, "almacen": alm, "signo": 1, "cantidad": aceptada}
                    )
                for oc_l in oc["lineas"]:
                    if oc_l["codigo_sku"] == sku:
                        oc_l["cantidad_recibida"] += aceptada
            completo = all(l["cantidad_recibida"] >= l["cantidad_solicitada"] for l in oc["lineas"])
            oc["estado"] = "RECIBIDA" if completo else "PARCIAL"
            rec["estado"] = "APROBADO"
            return [FakeRecord({"oc_estado": oc["estado"]})], None, None

        if "RETURN oc.estado AS oc_estado" in query:
            oc = self.ocs.get(params["codigo_oc"])
            if not oc:
                return [], None, None
            prov = self.proveedores[oc["codigo_proveedor"]]
            return [
                FakeRecord(
                    {
                        "oc_estado": oc["estado"],
                        "codigo_proveedor": prov["codigo_proveedor"],
                        "proveedor_estatus": prov["estatus"],
                        "proveedor_activo": prov["activo"],
                        "codigo_almacen": oc["codigo_almacen"],
                        "lineas": oc["lineas"],
                    }
                )
            ], None, None

        if "MERGE (r:ReciboMercancia" in query:
            self.recibos[params["codigo_recibo"]] = {
                "codigo_recibo": params["codigo_recibo"],
                "codigo_oc": params["codigo_oc"],
                "lineas": params["lineas"],
                "estado": "BORRADOR",
            }
            return [FakeRecord({"codigo_recibo": params["codigo_recibo"]})], None, None

        if "MERGE (ov:OrdenVenta" in query:
            self.ovs[params["codigo_ov"]] = {
                "codigo_ov": params["codigo_ov"],
                "codigo_almacen": params["codigo_almacen"],
                "estado_pedido": params["estado_pedido"],
                "estado_pago": params["estado_pago"],
                "lineas": [
                    {
                        "codigo_sku": l["codigo_sku"],
                        "cantidad_pedida": float(l["cantidad_pedida"]),
                        "cantidad_despachada": 0.0,
                    }
                    for l in params["lineas"]
                ],
            }
            return [FakeRecord({"codigo_ov": params["codigo_ov"]})], None, None

        if "RETURN ov.estado_pedido AS estado_pedido" in query:
            ov = self.ovs.get(params["codigo_ov"])
            if not ov:
                return [], None, None
            alm = ov["codigo_almacen"]
            lineas = []
            for l in ov["lineas"]:
                sku = l["codigo_sku"]
                lineas.append(
                    {
                        "codigo_sku": sku,
                        "cantidad_pedida": l["cantidad_pedida"],
                        "cantidad_despachada": l["cantidad_despachada"],
                        "stock_actual": self.stock[(alm, sku)]["stock_actual"],
                        "peso_unitario_kg": self.productos[sku]["peso_unitario_kg"],
                    }
                )
            return [
                FakeRecord(
                    {
                        "estado_pedido": ov["estado_pedido"],
                        "estado_pago": ov["estado_pago"],
                        "codigo_almacen": alm,
                        "lineas": lineas,
                    }
                )
            ], None, None

        if "MERGE (e:EntregaMercancia" in query:
            ov = self.ovs[params["codigo_ov"]]
            alm = ov["codigo_almacen"]
            for l in params["lineas"]:
                sku = l["codigo_sku"]
                qty = float(l["cantidad_entregada"])
                self.stock[(alm, sku)]["stock_actual"] -= qty
                self.movimientos.append(
                    {"sku": sku, "almacen": alm, "signo": -1, "cantidad": qty}
                )
                for ov_l in ov["lineas"]:
                    if ov_l["codigo_sku"] == sku:
                        ov_l["cantidad_despachada"] += qty
            completo = all(l["cantidad_despachada"] >= l["cantidad_pedida"] for l in ov["lineas"])
            ov["estado_pedido"] = "DESPACHADO" if completo else "EN_DESPACHO"
            return [FakeRecord({"ov_estado": ov["estado_pedido"]})], None, None

        if "RETURN sku," in query:
            sku = params["codigo_sku"]
            alm = params["codigo_almacen"]
            entradas = sum(m["cantidad"] for m in self.movimientos if m["sku"] == sku and m["almacen"] == alm and m["signo"] == 1)
            salidas = sum(m["cantidad"] for m in self.movimientos if m["sku"] == sku and m["almacen"] == alm and m["signo"] == -1)
            actual = self.stock[(alm, sku)]["stock_actual"]
            return [
                FakeRecord(
                    {
                        "sku": sku,
                        "almacen": alm,
                        "entradas": entradas,
                        "salidas": salidas,
                        "stock_calculado": entradas - salidas,
                        "stock_actual": actual,
                        "diferencia": actual - (entradas - salidas),
                    }
                )
            ], None, None

        return [], None, None


class TestComponentesUnitarios(unittest.TestCase):
    """Pruebas unitarias aisladas de cálculo y validación."""

    def test_pu01_suma_inventario_aislada(self):
        self.assertEqual(mongo_mod.sumar_inventario(10, 15), 25.0)
        with self.assertRaises(mongo_mod.ERPValidationError):
            mongo_mod.sumar_inventario(-1, 5)
        with self.assertRaises(mongo_mod.ERPValidationError):
            mongo_mod.sumar_inventario(True, 5)

    def test_pu02_resta_inventario_aislada_y_bloqueo(self):
        self.assertEqual(mongo_mod.restar_inventario(20, 8), 12.0)
        with self.assertRaises(mongo_mod.BusinessRuleError):
            mongo_mod.restar_inventario(5, 6)

    def test_pu03_calculo_peso_paquete(self):
        peso = mongo_mod.calcular_peso_paquete(
            [
                {"peso_unitario_kg": 1.25, "cantidad": 4},
                {"peso_unitario_kg": 0.50, "cantidad": 3},
            ]
        )
        self.assertEqual(peso, 6.5)

    def test_pu04_clasificacion_recepcion_exacta_faltante_danada(self):
        exacto = mongo_mod.clasificar_recepcion_linea(10, 10, 0)
        self.assertEqual(exacto["estado_calidad"], "EXACTO")
        self.assertEqual(exacto["cantidad_faltante"], 0.0)

        parcial_danado = mongo_mod.clasificar_recepcion_linea(10, 6, 2)
        self.assertEqual(parcial_danado["estado_calidad"], "PARCIAL_DANADO")
        self.assertEqual(parcial_danado["cantidad_recibida"], 8.0)
        self.assertEqual(parcial_danado["cantidad_faltante"], 2.0)

    def test_pu05_json_schema_rechaza_cantidad_negativa(self):
        db = mongo_mod.InMemoryDatabase()
        erp = mongo_mod.RecibosEntregasMongoDB(db)
        with self.assertRaises(mongo_mod.ERPValidationError):
            erp.registrar_producto("GPU-1", "RTX", peso_unitario_kg=-2.0)


class TestFlujoFuncionalMongoDB(unittest.TestCase):
    """Pruebas funcionales End-to-End sobre MongoDB (reglas de negocio e integridad)."""

    def setUp(self):
        self.erp = mongo_mod.RecibosEntregasMongoDB(mongo_mod.InMemoryDatabase())
        self.erp.registrar_almacen("ALM-01", "Almacén Central SLP")
        self.erp.registrar_proveedor("PROV-01", "Componentes del Norte", estatus="ACTIVO")
        self.erp.registrar_proveedor("PROV-BAJA", "Proveedor Suspendido", estatus="SUSPENDIDO")
        self.erp.registrar_cliente("CLI-01", "TechCliente S.A.", credito_autorizado=True, limite_credito=50000)
        self.erp.registrar_producto("GPU001", "Graphics Card RTX", "PZA", peso_unitario_kg=1.40)

    def test_pf01_ciclo_completo_recibo_actualiza_stock_y_oc(self):
        self.erp.crear_orden_compra(
            "OC-100",
            "PROV-01",
            "ALM-01",
            [{"codigo_sku": "GPU001", "cantidad_solicitada": 20, "costo_unitario": 8500}],
        )
        # Llega entrega parcial con 2 piezas dañadas y 15 buenas (faltaron 3)
        recibo = self.erp.registrar_recibo(
            "REC-100",
            "OC-100",
            [{"codigo_sku": "GPU001", "cantidad_aceptada": 15, "cantidad_danada": 2}],
            usuario_registro="ailton.182234",
        )
        self.assertEqual(recibo["estado"], "BORRADOR")
        self.assertEqual(self.erp.consultar_stock("GPU001", "ALM-01")["stock_actual"], 0.0)

        aprobado = self.erp.aprobar_recibo("REC-100", "supervisor.almacen")
        self.assertEqual(aprobado["estado"], "APROBADO")
        stock = self.erp.consultar_stock("GPU001", "ALM-01")
        self.assertEqual(stock["stock_actual"], 15.0)
        self.assertEqual(stock["stock_danado"], 2.0)

        oc = self.erp.db["ordenes_compra"].find_one({"codigo_oc": "OC-100"})
        self.assertEqual(oc["estado"], "PARCIAL")

    def test_pf02_bloqueo_proveedor_suspendido_o_baja(self):
        self.erp.crear_orden_compra(
            "OC-101",
            "PROV-BAJA",
            "ALM-01",
            [{"codigo_sku": "GPU001", "cantidad_solicitada": 5}],
        )
        with self.assertRaises(mongo_mod.BusinessRuleError):
            self.erp.registrar_recibo(
                "REC-101",
                "OC-101",
                [{"codigo_sku": "GPU001", "cantidad_aceptada": 5}],
                usuario_registro="ailton.182234",
            )

    def test_pf03_no_recibir_de_mas_sin_y_con_autorizacion_gerencial(self):
        self.erp.crear_orden_compra(
            "OC-102",
            "PROV-01",
            "ALM-01",
            [{"codigo_sku": "GPU001", "cantidad_solicitada": 10}],
        )
        with self.assertRaises(mongo_mod.BusinessRuleError):
            self.erp.registrar_recibo(
                "REC-102-ERR",
                "OC-102",
                [{"codigo_sku": "GPU001", "cantidad_aceptada": 12}],
                usuario_registro="ailton.182234",
            )

        self.erp.registrar_autorizacion_gerencial(
            "AUTH-GER-01",
            "EXCESO_RECIBO",
            "Ing. Jesús Revilla",
            "Reposición sin costo acordada con proveedor",
            cantidad_extra_autorizada=2,
        )
        rec = self.erp.registrar_recibo(
            "REC-102-OK",
            "OC-102",
            [{"codigo_sku": "GPU001", "cantidad_aceptada": 12}],
            usuario_registro="ailton.182234",
            autorizacion_gerencial="AUTH-GER-01",
        )
        self.assertEqual(rec["lineas"][0]["estado_calidad"], "EXCESO_AUTORIZADO")
        self.erp.aprobar_recibo("REC-102-OK", "gerente")
        self.assertEqual(self.erp.consultar_stock("GPU001", "ALM-01")["stock_actual"], 12.0)

    def test_pf04_entregas_validan_pago_stock_y_generan_nota_salida(self):
        self.erp.crear_orden_compra(
            "OC-200",
            "PROV-01",
            "ALM-01",
            [{"codigo_sku": "GPU001", "cantidad_solicitada": 10}],
        )
        self.erp.registrar_recibo(
            "REC-200",
            "OC-200",
            [{"codigo_sku": "GPU001", "cantidad_aceptada": 10}],
            usuario_registro="operador",
        )
        self.erp.aprobar_recibo("REC-200", "supervisor")

        # Pedido sin pago ni crédito autorizado debe rechazarse
        self.erp.crear_orden_venta(
            "OV-PEND",
            "CLI-01",
            "ALM-01",
            [{"codigo_sku": "GPU001", "cantidad_pedida": 4}],
            estado_pedido="APROBADO",
            estado_pago="PENDIENTE",
        )
        with self.assertRaises(mongo_mod.BusinessRuleError):
            self.erp.registrar_entrega(
                "ENT-NO-PAGO",
                "OV-PEND",
                [{"codigo_sku": "GPU001", "cantidad_entregada": 4}],
                usuario_despacho="despachador",
            )

        # Pedido pagado pero con stock insuficiente (pide 15, solo hay 10)
        self.erp.crear_orden_venta(
            "OV-SIN-STOCK",
            "CLI-01",
            "ALM-01",
            [{"codigo_sku": "GPU001", "cantidad_pedida": 15}],
            estado_pedido="APROBADO",
            estado_pago="PAGADO",
        )
        with self.assertRaises(mongo_mod.BusinessRuleError):
            self.erp.registrar_entrega(
                "ENT-SIN-STOCK",
                "OV-SIN-STOCK",
                [{"codigo_sku": "GPU001", "cantidad_entregada": 15}],
                usuario_despacho="despachador",
            )

        # Entrega exitosa con crédito autorizado
        self.erp.crear_orden_venta(
            "OV-OK",
            "CLI-01",
            "ALM-01",
            [{"codigo_sku": "GPU001", "cantidad_pedida": 4}],
            estado_pedido="APROBADO",
            estado_pago="CREDITO_AUTORIZADO",
        )
        entrega = self.erp.registrar_entrega(
            "ENT-200",
            "OV-OK",
            [{"codigo_sku": "GPU001", "cantidad_entregada": 4}],
            usuario_despacho="despachador",
        )
        self.assertEqual(entrega["numero_nota_salida"], "NS-ENT-200")
        self.assertEqual(entrega["peso_total_kg"], 5.6)

        confirmada = self.erp.confirmar_entrega("ENT-200", "despachador")
        self.assertEqual(confirmada["estado"], "CONFIRMADA")
        self.assertEqual(self.erp.consultar_stock("GPU001", "ALM-01")["stock_actual"], 6.0)

        # Cuadre de integridad: Entradas (10) - Salidas (4) = Stock actual (6)
        cuadre = self.erp.verificar_cuadre_inventario("GPU001", "ALM-01")
        self.assertTrue(cuadre["cuadra"])
        self.assertEqual(cuadre["entradas"], 10.0)
        self.assertEqual(cuadre["salidas"], 4.0)
        self.assertEqual(cuadre["stock_actual"], 6.0)

    def test_pi01_inmutabilidad_registros_cerrados_y_kardex(self):
        self.erp.crear_orden_compra(
            "OC-300",
            "PROV-01",
            "ALM-01",
            [{"codigo_sku": "GPU001", "cantidad_solicitada": 5}],
        )
        self.erp.registrar_recibo(
            "REC-300",
            "OC-300",
            [{"codigo_sku": "GPU001", "cantidad_aceptada": 5}],
            usuario_registro="operador",
        )
        self.erp.aprobar_recibo("REC-300", "supervisor")

        with self.assertRaises(mongo_mod.DataIntegrityError):
            self.erp.modificar_recibo("REC-300", {"observaciones": "Alteración indebida"})
        with self.assertRaises(mongo_mod.DataIntegrityError):
            self.erp.eliminar_documento("recibos_mercancia", "codigo_recibo", "REC-300")
        with self.assertRaises(mongo_mod.DataIntegrityError):
            self.erp.eliminar_documento("movimientos_inventario", "codigo_movimiento", "MOV-REC-300-GPU001")


class TestGrafoNeo4j(unittest.TestCase):
    """Pruebas del modelo de grafo Neo4j y consultas Cypher parametrizadas."""

    def test_neo4j_flujo_completo_y_seguridad_cypher(self):
        driver = FakeNeo4jDriver()
        graph = neo4j_mod.RecibosEntregasNeo4j(driver)
        graph.inicializar_esquema()
        graph.registrar_maestros(
            proveedor={"codigo_proveedor": "PROV-01", "nombre": "Proveedor Uno", "estatus": "ACTIVO"},
            cliente={"codigo_cliente": "CLI-01", "nombre": "Cliente Uno", "credito_autorizado": True},
            almacen={"codigo_almacen": "ALM-01", "nombre": "Almacén SLP"},
            productos=[{"codigo_sku": "CPU001", "nombre": "CPU Ryzen 7", "peso_unitario_kg": 0.5}],
        )
        graph.crear_orden_compra(
            "OC-N1",
            "PROV-01",
            "ALM-01",
            [{"codigo_sku": "CPU001", "cantidad_solicitada": 10, "costo_unitario": 4500}],
        )
        res_rec = graph.registrar_y_aprobar_recibo(
            "REC-N1",
            "OC-N1",
            [
                {
                    "codigo_sku": "CPU001",
                    "cantidad_esperada": 10,
                    "cantidad_recibida": 10,
                    "cantidad_aceptada": 10,
                    "cantidad_faltante": 0,
                    "cantidad_danada": 0,
                    "estado_calidad": "EXACTO",
                }
            ],
            usuario_registro="ramoes12",
        )
        self.assertEqual(res_rec["oc_estado"], "RECIBIDA")

        graph.crear_orden_venta(
            "OV-N1",
            "CLI-01",
            "ALM-01",
            [{"codigo_sku": "CPU001", "cantidad_pedida": 3}],
            estado_pedido="APROBADO",
            estado_pago="PAGADO",
        )
        res_ent = graph.confirmar_entrega(
            "ENT-N1",
            "OV-N1",
            [{"codigo_sku": "CPU001", "cantidad_entregada": 3}],
            usuario_despacho="ramoes12",
        )
        self.assertEqual(res_ent["ov_estado"], "DESPACHADO")

        cuadre = graph.verificar_cuadre_inventario("CPU001", "ALM-01")
        self.assertTrue(cuadre["cuadra"])
        self.assertEqual(cuadre["stock_actual"], 7.0)

        # Verifica que ninguna consulta ejecute DETACH DELETE global
        self.assertFalse(any("DETACH DELETE" in q for q, _ in driver.calls))

    def test_neo4j_bloquea_exceso_y_stock_insuficiente(self):
        driver = FakeNeo4jDriver()
        graph = neo4j_mod.RecibosEntregasNeo4j(driver)
        graph.registrar_maestros(
            proveedor={"codigo_proveedor": "PROV-01", "nombre": "Proveedor Uno", "estatus": "ACTIVO"},
            cliente={"codigo_cliente": "CLI-01", "nombre": "Cliente Uno", "credito_autorizado": False},
            almacen={"codigo_almacen": "ALM-01", "nombre": "Almacén SLP"},
            productos=[{"codigo_sku": "CPU001", "nombre": "CPU Ryzen 7", "peso_unitario_kg": 0.5}],
        )
        graph.crear_orden_compra(
            "OC-N2",
            "PROV-01",
            "ALM-01",
            [{"codigo_sku": "CPU001", "cantidad_solicitada": 5, "costo_unitario": 4500}],
        )
        with self.assertRaises(neo4j_mod.Neo4jBusinessError):
            graph.registrar_y_aprobar_recibo(
                "REC-N2",
                "OC-N2",
                [
                    {
                        "codigo_sku": "CPU001",
                        "cantidad_esperada": 5,
                        "cantidad_recibida": 8,
                        "cantidad_aceptada": 8,
                        "cantidad_faltante": 0,
                        "cantidad_danada": 0,
                        "estado_calidad": "EXCESO_AUTORIZADO",
                    }
                ],
                usuario_registro="ramoes12",
            )


class TestArtefactosSQLyCypher(unittest.TestCase):
    """Verifica la existencia y completitud de los scripts SQL y Cypher."""

    def test_sql_y_cypher_contienen_reglas_clave(self):
        sql_text = (RECIBOS_DIR / "schema_recibos_entregas.sql").read_text(encoding="utf-8")
        for tabla in (
            "proveedores",
            "clientes",
            "productos",
            "inventario_stock",
            "ordenes_compra",
            "ordenes_compra_detalle",
            "recibos_mercancia",
            "recibos_detalle",
            "ordenes_venta",
            "ordenes_venta_detalle",
            "entregas_mercancia",
            "entregas_detalle",
            "movimientos_inventario",
            "vw_cuadre_inventario",
        ):
            self.assertIn(tabla, sql_text)

        cypher_text = (RECIBOS_DIR / "neo4j_recibos_entregas.cypher").read_text(encoding="utf-8")
        self.assertIn("CREATE CONSTRAINT erp_recibo_codigo", cypher_text)
        self.assertIn("CREATE CONSTRAINT erp_entrega_codigo", cypher_text)

        proc_sql = (RECIBOS_DIR / "consultas_y_procedimientos_recibos.sql").read_text(encoding="utf-8")
        for obj in (
            "sp_aprobar_recibo_mercancia",
            "sp_reservar_stock_picking",
            "sp_confirmar_entrega_salida",
            "vw_cuadre_inventario",
        ):
            self.assertIn(obj, proc_sql)


class FakePGCursor:
    def __init__(self, rows):
        self._rows = rows
        self.queries = []

    def execute(self, query):
        self.queries.append(query)

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class FakePGConnection:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return FakePGCursor(self._rows)


class FakeSyncNeo4jDriver:
    def __init__(self):
        self.calls = []

    def execute_query(self, query, database_=None, **params):
        self.calls.append((query, params))
        if "movimientos_sincronizados" in query:
            return [FakeRecord({"movimientos_sincronizados": len(params["rows"])})], None, None
        if "collect(DISTINCT prov.codigo_proveedor)" in query:
            return [
                FakeRecord(
                    {
                        "sku": params["codigo_sku"],
                        "proveedores": ["PROV-01"],
                        "ordenes_compra": ["OC-100"],
                        "recibos": ["REC-100"],
                        "entregas": ["ENT-200"],
                    }
                )
            ], None, None
        if "porcentaje_cumplimiento" in query:
            return [
                FakeRecord(
                    {
                        "codigo_proveedor": "PROV-01",
                        "nombre": "Componentes del Norte",
                        "estatus": "ACTIVO",
                        "total_solicitado": 20.0,
                        "total_recibido": 20.0,
                        "porcentaje_cumplimiento": 100.0,
                    }
                )
            ], None, None
        return [], None, None


class TestIntegracionPGNeo4j(unittest.TestCase):
    """Pruebas del puente PostgreSQL -> Neo4j y consultas analíticas para agentes."""

    def test_inventarios_criticos_y_sync_neo4j(self):
        pg_crit = FakePGConnection([("GPU001", "Graphics Card RTX", "ALM-01", 3.0, 1.0, 2.0, 5.0)])
        neo_drv = FakeSyncNeo4jDriver()
        bridge = integ_mod.IntegracionPGNeo4j(pg_crit, neo_drv)
        criticos = bridge.obtener_inventarios_criticos()
        self.assertEqual(len(criticos), 1)
        self.assertEqual(criticos[0]["stock_disponible"], 2.0)

        pg_movs = FakePGConnection(
            [("MOV-1", "GPU001", "Graphics Card RTX", "ALM-01", "ENTRADA_RECIBO", "RECIBO", 10.0, 1, 0.0, 10.0, "2026-11-25T10:00:00")]
        )
        bridge_sync = integ_mod.IntegracionPGNeo4j(pg_movs, neo_drv)
        self.assertEqual(bridge_sync.sincronizar_movimientos_a_neo4j(), 1)
        traza = bridge_sync.consultar_trazabilidad_grafo("gpu001")
        self.assertEqual(traza["sku"], "GPU001")
        self.assertEqual(traza["recibos"], ["REC-100"])
        ranking = bridge_sync.consultar_proveedores_confiables()
        self.assertEqual(ranking[0]["porcentaje_cumplimiento"], 100.0)


if __name__ == "__main__":
    unittest.main()
