"""Pruebas unitarias y funcionales para el Agente IA de Costeo y Mermas BOM."""

import importlib.util
import sys
import unittest
from pathlib import Path


MOD_PATH = Path(__file__).resolve().with_name("agente_costeo_llm.py")
spec = importlib.util.spec_from_file_location("agente_costeo_llm", MOD_PATH)
cost_mod = importlib.util.module_from_spec(spec)
sys.modules["agente_costeo_llm"] = cost_mod
spec.loader.exec_module(cost_mod)


class FakeDriver:
    def __init__(self):
        self.calls = []

    def execute_query(self, query, **params):
        self.calls.append((query, params))
        return [], None, None


class TestAgenteCosteoMermasBOM(unittest.TestCase):
    def setUp(self):
        self.items = {
            "PC001": {"tipo_item": "PT", "es_discreto": True},
            "SUB-A": {"tipo_item": "SE", "es_discreto": True},
            "SUB-B": {"tipo_item": "SE", "es_discreto": True},
            "TORN01": {"tipo_item": "MP", "es_discreto": True, "costo_estandar": 2.0},
            "GPU001": {"tipo_item": "MP", "es_discreto": True, "costo_estandar": 8000.0},
        }
        self.headers = {
            "PC001": {"cantidad_base": 1.0},
            "SUB-A": {"cantidad_base": 1.0},
            "SUB-B": {"cantidad_base": 1.0},
        }
        self.lines = {
            "PC001": [
                {"child_sku": "SUB-A", "cantidad": 1.0, "scrap_merma": 0.0},
                {"child_sku": "SUB-B", "cantidad": 1.0, "scrap_merma": 0.0},
                {"child_sku": "GPU001", "cantidad": 1.0, "scrap_merma": 0.0},
            ],
            "SUB-A": [{"child_sku": "TORN01", "cantidad": 0.4, "scrap_merma": 0.0}],
            "SUB-B": [{"child_sku": "TORN01", "cantidad": 0.4, "scrap_merma": 0.12}],
        }
        self.driver = FakeDriver()
        self.agent = cost_mod.BOMCostingScrapAgent(
            self.items, self.headers, self.lines, neo4j_driver=self.driver, umbral_merma_alerta=0.08
        )

    def test_redondeo_final_y_alerta_merma(self):
        # 0.4 + 0.4/(1-0.12) = 0.4 + 0.454545 = 0.854545 -> ceil(0.854545) = 1 (PU09)
        res = self.agent.calcular_costeo_lote("AN-COST-01", "PC001", cantidad_lote=1)
        torn = next(x for x in res["desglose_mp"] if x["sku"] == "TORN01")
        self.assertEqual(torn["cantidad_final"], 1.0)
        self.assertEqual(res["costo_total_lote"], 8002.0)
        self.assertEqual(res["top_driver"]["sku"], "GPU001")
        self.assertEqual(res["analisis_llm"]["estado_costo"], "ALERTA_MERMA")
        self.assertTrue(any("MERGE (an:AnalisisCosteoBOM" in q for q, _ in self.driver.calls))

    def test_rechaza_merma_invalida_igual_o_mayor_a_100_por_ciento(self):
        self.lines["SUB-A"][0]["scrap_merma"] = 1.0
        with self.assertRaises(cost_mod.CostingValidationError):
            self.agent.calcular_costeo_lote("AN-ERR", "PC001", cantidad_lote=1)


if __name__ == "__main__":
    unittest.main()
