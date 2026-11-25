"""Pruebas unitarias y funcionales para el Agente IA Auditor de Coherencia BOM."""

import importlib.util
import sys
import unittest
from pathlib import Path


MOD_PATH = Path(__file__).resolve().with_name("agente_auditor_llm.py")
spec = importlib.util.spec_from_file_location("agente_auditor_llm", MOD_PATH)
aud_mod = importlib.util.module_from_spec(spec)
sys.modules["agente_auditor_llm"] = aud_mod
spec.loader.exec_module(aud_mod)


class FakeDriver:
    def __init__(self):
        self.calls = []

    def execute_query(self, query, **params):
        self.calls.append((query, params))
        return [], None, None


class TestAgenteAuditorCoherenciaBOM(unittest.TestCase):
    def setUp(self):
        self.items = {
            "PC001": {"tipo_item": "PT", "uom_base": "PZA", "activo": True},
            "SUB-CPU": {"tipo_item": "SE", "uom_base": "PZA", "activo": True},
            "SUB-HUERFANO": {"tipo_item": "SE", "uom_base": "PZA", "activo": True},
            "CPU001": {"tipo_item": "MP", "uom_base": "PZA", "activo": True},
            "PASTA": {"tipo_item": "MP", "uom_base": "G", "activo": True},
        }
        self.boms = {
            "SUB-CPU": {"bom_id": "BOM-SUB-CPU", "estado": "ACTIVO"},
        }
        self.driver = FakeDriver()
        self.agent = aud_mod.BOMCoherenceAuditorAgent(self.items, self.boms, neo4j_driver=self.driver)

    def test_aprueba_bom_coherente(self):
        bom_ok = {
            "bom_id": "BOM-PC001-OK",
            "parent_sku": "PC001",
            "lineas": [
                {"child_sku": "SUB-CPU", "cantidad": 1, "uom": "PZA"},
                {"child_sku": "PASTA", "cantidad": 0.05, "uom": "KG"},
            ],
        }
        res = self.agent.auditar_bom("AUD-01", bom_ok)
        self.assertTrue(res["aprobado"])
        self.assertEqual(res["dictamen_llm"]["veredicto"], "APROBADO")
        self.assertTrue(any("MERGE (aud:AuditoriaBOM" in q for q, _ in self.driver.calls))

    def test_detecta_mp_como_padre_duplicados_uom_invalida_y_se_huerfano(self):
        bom_malo = {
            "bom_id": "BOM-ERR",
            "parent_sku": "CPU001",  # RN-15: MP no puede ser padre
            "lineas": [
                {"child_sku": "PASTA", "cantidad": 2, "uom": "L"},  # RN-04: L vs G incompatible
                {"child_sku": "PASTA", "cantidad": 1, "uom": "G"},  # RN-02: duplicado
                {"child_sku": "SUB-HUERFANO", "cantidad": 1, "uom": "PZA"},  # RN-05: SE sin BOM
            ],
        }
        res = self.agent.auditar_bom("AUD-02", bom_malo)
        self.assertFalse(res["aprobado"])
        reglas = {h["regla"] for h in res["hallazgos"]}
        self.assertEqual(reglas, {"RN-15", "RN-04", "RN-02", "RN-05"})
        self.assertEqual(res["dictamen_llm"]["veredicto"], "RECHAZADO")
        self.assertEqual(res["dictamen_llm"]["severidad"], "CRITICA")


if __name__ == "__main__":
    unittest.main()
