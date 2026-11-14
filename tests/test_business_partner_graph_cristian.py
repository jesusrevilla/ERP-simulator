"""Pruebas de consultas Cypher del modelo Business Partners, sin Neo4j externo."""
from src.business_partner_events_cristian import load_catalog
from src.neo4j_business_partners_cristian import (
    ADDRESS_QUERY,
    BP_QUERY,
    CONTACT_QUERY,
    EVENT_QUERY,
    SCOPE,
    count_graph,
    graph_rows,
    load_graph,
)


class FakeRecord:
    def __init__(self, data):
        self.values = data

    def __getitem__(self, key):
        return self.values[key]


class FakeDriver:
    def __init__(self):
        self.calls = []

    def execute_query(self, query, **params):
        self.calls.append((query, params))
        if "RETURN business_partners" in query:
            return [FakeRecord({"business_partners": 2, "events": 22})], None, None
        return [], None, None


def test_graph_rows_include_only_business_partner_domain():
    rows = graph_rows(load_catalog())
    assert len(rows["partners"]) == 2
    assert len(rows["events"]) == 22
    assert len(rows["contacts"]) == 2
    assert len(rows["addresses"]) == 2
    assert {p["bp_type"] for p in rows["partners"]} == {"V", "C"}


def test_graph_loading_has_explicit_scope_and_merge():
    driver = FakeDriver()
    rows = load_graph(driver, load_catalog())
    assert len(driver.calls) == 8
    assert all("MERGE" in query for query in (BP_QUERY, EVENT_QUERY, CONTACT_QUERY, ADDRESS_QUERY))
    assert not any("DETACH DELETE" in query for query, _ in driver.calls)
    assert driver.calls[4][1]["scope"] == SCOPE
    assert driver.calls[4][1]["rows"] == rows["partners"]
    assert driver.calls[5][1]["rows"] == rows["events"]
    assert driver.calls[6][1]["rows"] == rows["contacts"]
    assert driver.calls[7][1]["rows"] == rows["addresses"]


def test_graph_count_query_is_parameterized():
    driver = FakeDriver()
    assert count_graph(driver) == (2, 22)
    query, params = driver.calls[0]
    assert "$scope" in query
    assert params["scope"] == SCOPE
    assert params["database_"] == "neo4j"
