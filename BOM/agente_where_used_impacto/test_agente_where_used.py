"""Pruebas unitarias y funcionales para el Agente IA de Implosión Where-Used BOM."""

import importlib.util
import sys
import unittest
from pathlib import Path


MOD_PATH = Path(__file__).resolve().with_name("agente_where_used_llm.py")
spec = importlib.util.spec_from_file_location("agente_where_used_llm", MOD_PATH)
wu_mod = importlib.util.module_from_spec(spec)
sys.modules["agente_where_used_llm"] = wu_mod
spec.loader.exec_module(wu_mod)


class FakeDriver:
    def __init__(self):
        self.calls = []

    def execute_query(self, query, **params):
        self.calls.append((query, params))
        return [], None, None


class TestAgenteWhereUsedImpacto(unittest.TestCase):
    def setUp(self):
        self.items = {
            "PC001": {"tipo_item": "PT"},
            "WS001": {"tipo_item": "PT"},
            "SUB-GPU": {"tipo_item": "SE"},
            "GPU001": {"tipo_item": "MP"},
        }
        self.edges = [
            {"parent_sku": "PC001", "child_sku": "SUB-GPU", "cantidad": 1, "estado": "ACTIVO"},
            {"parent_sku": "SUB-GPU", "child_sku": "GPU001", "cantidad": 1, "estado": "ACTIVO"},
            {"parent_sku": "WS001", "child_sku": "GPU001", "cantidad": 2, "estado": "ACTIVO"},
            {"parent_sku": "OLD-PC", "child_sku": "GPU001", "cantidad": 1, "estado": "INACTIVO"},
        ]
        self.driver = FakeDriver()
        self.agent = wu_mod.BOMWhereUsedImpactAgent(self.items, self.edges, neo4j_driver=self.driver)

    def test_implosion_multinivel_solo_activos_e_inactivos(self):
        activos = self.agent.implosion_where_used("GPU001", incluir_inactivos=False)
        skus_activos = [u["sku_afectado"] for u in activos]
        self.assertEqual(skus_activos, ["SUB-GPU", "WS001", "PC001"])
        ws_uso = next(u for u in activos if u["sku_afectado"] == "WS001")
        self.assertEqual(ws_uso["consumo_unitario_total"], 2.0)

        todos = self.agent.implosion_where_used("GPU001", incluir_inactivos=True)
        self.assertIn("OLD-PC", [u["sku_afectado"] for u in todos])

    def test_analisis_impacto_desabasto_y_plan_llm(self):
        res = self.agent.analizar_impacto_desabasto(
            alerta_id="ALT-GPU-01",
            component_sku="GPU001",
            stock_actual=20,
            demanda_componente=30,
        )
        self.assertEqual(res["deficit_unidades"], 10.0)
        self.assertEqual(res["productos_terminados"], ["PC001", "WS001"])
        self.assertEqual(res["subensambles"], ["SUB-GPU"])
        self.assertEqual(res["recomendacion_llm"]["nivel_riesgo"], "CRITICO")
        self.assertTrue(any("MERGE (al:AlertaDesabasto" in q for q, _ in self.driver.calls))


if __name__ == "__main__":
    unittest.main()
