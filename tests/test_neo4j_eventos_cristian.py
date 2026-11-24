"""Validación de catálogo ISA-95 y consultas Neo4j sin servidor externo."""
import copy
import json

import pytest

from neo4j_tutorial_cristian.erp_graph import (
    CATALOG_PATH,
    EVENTS_CYPHER,
    MATERIALS_CYPHER,
    SHORTAGE_CYPHER,
    calculate_shortages,
    load_events,
    load_graph,
    materials_for_product,
    query_shortages,
)


class FakeRecord:
    def __init__(self, data):
        self.values = data

    def data(self):
        return dict(self.values)


class FakeDriver:
    def __init__(self):
        self.calls = []

    def execute_query(self, query, **params):
        self.calls.append((query, params))
        if "RETURN m.name AS material" in query:
            return [FakeRecord(x) for x in calculate_shortages(params["quantity"])], None, None
        return [], None, None


def test_events_catalog_validity():
    catalog = load_events()
    assert catalog["enterprise"] == "TechAssembly S.A."
    assert catalog["example_data"] is True
    assert len(catalog["events"]) == 9
    assert catalog["events"][0]["event_type"] == "PRODUCT_INITIAL_STOCK"


def test_events_stock_sequence():
    events = load_events()["events"]
    assert [(e["stock_before"], e["stock_after"]) for e in events if e["stock_delta"] != 0] == [
        (0, 10), (10, 18), (18, 15), (15, 18), (18, 5)
    ]
    assert events[-1]["stock_after"] == 5
    assert events[-1]["event_type"] == "STOCK_MINIMUM_ALERT"


def test_events_rejected_sale_does_not_reduce_stock():
    event = next(e for e in load_events()["events"] if e["event_type"] == "SALE_REJECTED_INSUFFICIENT_STOCK")
    assert event["quantity"] == 19
    assert event["stock_before"] == event["stock_after"] == 18
    assert event["stock_delta"] == 0


def test_events_duplicate_ids_detected(tmp_path):
    catalog = load_events()
    catalog["events"][1]["event_id"] = catalog["events"][0]["event_id"]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")
    with pytest.raises(ValueError, match="repetido"):
        load_events(path)


def test_events_invalid_stock_detected(tmp_path):
    catalog = load_events()
    catalog["events"][4]["stock_after"] = 999
    path = tmp_path / "bad_stock.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")
    with pytest.raises(ValueError, match="stock inconsistente"):
        load_events(path)


def test_mrp_shortages_for_thirty_gaming_pcs():
    rows = calculate_shortages(30)
    assert len(rows) == 6
    assert [x for x in rows if x["shortage"] > 0] == [
        {"material": "Graphics Card RTX", "required": 30, "stock": 20, "shortage": 10}
    ]
    ram = next(x for x in rows if x["material"] == "RAM 16GB DDR5")
    assert ram["required"] == 60


@pytest.mark.parametrize("quantity", [0, -1, 2.3, True, "30"])
def test_mrp_quantity_validation(quantity):
    with pytest.raises(ValueError):
        calculate_shortages(quantity)


def test_graph_load_uses_merge_and_parameters():
    fake = FakeDriver()
    load_graph(fake, load_events())
    assert len(fake.calls) == 6
    assert "MERGE" in MATERIALS_CYPHER and "UNWIND $rows" in MATERIALS_CYPHER
    assert "MERGE" in EVENTS_CYPHER and "UNWIND $events" in EVENTS_CYPHER
    assert not any("DETACH DELETE" in query for query, _ in fake.calls)
    assert fake.calls[4][1]["rows"] == materials_for_product()
    assert len(fake.calls[5][1]["events"]) == 9


def test_neo4j_shortage_query_uses_safe_parameters():
    fake = FakeDriver()
    data = query_shortages(fake, 30)
    assert data == calculate_shortages(30)
    query, params = fake.calls[-1]
    assert "$quantity" in query and "$product_code" in query
    assert params["quantity"] == 30
    assert params["product_code"] == "PC001"
