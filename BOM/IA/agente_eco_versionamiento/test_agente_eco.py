"""Pruebas unitarias y funcionales para el Agente IA de ECO y Versionado BOM."""

import importlib.util
import sys
import unittest
from pathlib import Path


MOD_PATH = Path(__file__).resolve().with_name("agente_eco_llm.py")
spec = importlib.util.spec_from_file_location("agente_eco_llm", MOD_PATH)
eco_mod = importlib.util.module_from_spec(spec)
sys.modules["agente_eco_llm"] = eco_mod
spec.loader.exec_module(eco_mod)


class FakeRecord:
    def __init__(self, data):
        self._data = data

    def data(self):
        return dict(self._data)


class FakeDriver:
    def __init__(self):
        self.calls = []

    def execute_query(self, query, **params):
        self.calls.append((query, params))
        if "RETURN eco.eco_id" in query:
            return [FakeRecord({"eco_id": params["eco_id"], "version": params["version"]})], None, None
        return [], None, None


class TestAgenteECOVersionamiento(unittest.TestCase):
    def setUp(self):
        self.driver = FakeDriver()
        self.agent = eco_mod.BOMECOLifecycleAgent(neo4j_driver=self.driver)
        self.v1 = eco_mod.BOMVersion(
            bom_id="BOM-PC001-V1",
            parent_sku="PC001",
            version="v1.0",
            estado="ACTIVO",
            fecha_inicio="2026-01-01T00:00:00",
            fecha_fin="2026-12-31T23:59:59",
            componentes=[{"sku": "RAM001", "qty": 2}],
            tiene_ordenes_produccion=True,
        )
        self.agent.registrar_version(self.v1)

    def test_bloquea_edicion_bom_activo_y_permite_clonar(self):
        with self.assertRaises(eco_mod.ECOBusinessError):
            self.agent.editar_componentes("BOM-PC001-V1", [{"sku": "RAM001", "qty": 4}])

        v2 = self.agent.clonar_version("BOM-PC001-V1", "BOM-PC001-V2", "v2.0", "2027-01-01T00:00:00")
        self.assertEqual(v2.estado, "BORRADOR")
        self.agent.editar_componentes("BOM-PC001-V2", [{"sku": "RAM001", "qty": 4}])
        res = self.agent.procesar_eco_y_transicionar("ECO-001", "BOM-PC001-V2", "ACTIVO", "Upgrade RAM 32GB")
        self.assertEqual(res["estado"], "ACTIVO")
        self.assertEqual(res["dictamen_llm"]["decision"], "APROBAR")
        self.assertTrue(any("MERGE (eco:OrdenCambioECO" in q for q, _ in self.driver.calls))

    def test_bloquea_traslape_vigencia_activa_y_obsoleto_terminal(self):
        v_overlap = eco_mod.BOMVersion(
            bom_id="BOM-PC001-V1B",
            parent_sku="PC001",
            version="v1.1",
            estado="BORRADOR",
            fecha_inicio="2026-06-01T00:00:00",
            fecha_fin=None,
            componentes=[{"sku": "RAM001", "qty": 2}],
        )
        self.agent.registrar_version(v_overlap)
        with self.assertRaises(eco_mod.ECOBusinessError):
            self.agent.procesar_eco_y_transicionar("ECO-002", "BOM-PC001-V1B", "ACTIVO", "Traslape indebido")

        self.agent.procesar_eco_y_transicionar("ECO-003", "BOM-PC001-V1", "OBSOLETO", "Fin de vida")
        with self.assertRaises(eco_mod.ECOBusinessError):
            self.agent.procesar_eco_y_transicionar("ECO-004", "BOM-PC001-V1", "ACTIVO", "Reactivar obsoleto")


if __name__ == "__main__":
    unittest.main()
