"""Pruebas individuales del ejercicio Business Partners de Cristian Godinez."""
from copy import deepcopy

import pytest

from src.business_partner_events_cristian import (
    BPValidationError,
    decide_document,
    load_catalog,
    project_events,
)


@pytest.fixture
def catalog():
    return deepcopy(load_catalog())


def test_catalog_contains_only_business_partner_events(catalog):
    assert catalog["simulated_data"] is True
    assert catalog["scope"].startswith("Business Partners")
    assert len(catalog["events"]) == 22
    assert all("card_code" in event for event in catalog["events"])


def test_partner_types_and_final_states(catalog):
    result = project_events(catalog)
    vendor = result["partners"]["BP-V-001"]
    lead_converted = result["partners"]["BP-L-001"]
    assert vendor["bp_type"] == "V"
    assert vendor["active"] is True
    assert lead_converted["bp_type"] == "C"
    assert lead_converted["active"] is False


def test_lead_conversion_preserves_contacts_and_addresses(catalog):
    result = project_events(catalog)
    customer = result["partners"]["BP-L-001"]
    assert len(customer["contacts"]) == 1
    assert len(customer["addresses"]) == 1
    assert customer["contacts"][0]["email"] == "prospecto@example.test"
    assert customer["addresses"][0]["kind"] == "SHIPPING"


def test_supplier_conditions_and_roles(catalog):
    vendor = project_events(catalog)["partners"]["BP-V-001"]
    assert vendor["payment_terms"] == "NET_30"
    assert vendor["currency"] == "MXN"
    assert vendor["tags"] == ["SUPPLIER_CRITICAL_COMPONENTS"]
    assert vendor["blocked"] == []


def test_credit_and_rejection_reasons(catalog):
    result = project_events(catalog)
    decisions = result["document_decisions"]
    assert len(decisions) == 7
    assert [(d["result"], d["reason"]) for d in decisions] == [
        ("REJECTED", "BLOCKED"),
        ("APPROVED", "NONE"),
        ("REJECTED", "PARTNER_TYPE"),
        ("APPROVED", "NONE"),
        ("REJECTED", "CREDIT_LIMIT"),
        ("REJECTED", "BLOCKED"),
        ("REJECTED", "INACTIVE"),
    ]
    assert result["partners"]["BP-L-001"]["credit_limit_cents"] == 1500000


def test_projection_is_deterministic(catalog):
    assert project_events(catalog) == project_events(catalog)
    assert project_events(catalog)["event_count"] == 22


def test_cardcode_duplicated_is_rejected(catalog):
    catalog["events"][9]["card_code"] = "BP-V-001"
    with pytest.raises(BPValidationError, match="CardCode duplicado"):
        project_events(catalog)


def test_event_ids_must_be_unique(catalog):
    catalog["events"][1]["event_id"] = catalog["events"][0]["event_id"]
    with pytest.raises(BPValidationError, match="duplicado"):
        project_events(catalog)


def test_events_must_be_chronological(catalog):
    catalog["events"][1]["timestamp_utc"] = catalog["events"][0]["timestamp_utc"]
    with pytest.raises(BPValidationError, match="desordenados"):
        project_events(catalog)


def test_events_require_utc(catalog):
    catalog["events"][1]["timestamp_utc"] = "2026-11-11T12:04:00-06:00"
    with pytest.raises(BPValidationError, match="UTC"):
        project_events(catalog)


def test_mandatory_fiscal_identifier(catalog):
    catalog["events"][0]["payload"]["tax_id"] = ""
    with pytest.raises(BPValidationError, match="tax_id"):
        project_events(catalog)


def test_invalid_cardtype(catalog):
    catalog["events"][0]["payload"]["bp_type"] = "X"
    with pytest.raises(BPValidationError, match="CardType"):
        project_events(catalog)


def test_fiscal_currency_is_validated(catalog):
    catalog["events"][0]["payload"]["currency"] = "BTC"
    with pytest.raises(BPValidationError, match="Moneda"):
        project_events(catalog)


def test_wrong_document_result_is_detected(catalog):
    catalog["events"][6]["payload"]["expected_result"] = "APPROVED"
    with pytest.raises(BPValidationError, match="inconsistente"):
        project_events(catalog)


def test_unknown_partner_is_rejected(catalog):
    catalog["events"][1]["card_code"] = "BP-DOES-NOT-EXIST"
    with pytest.raises(BPValidationError, match="no existe"):
        project_events(catalog)


def test_invalid_credit_limit_is_rejected(catalog):
    catalog["events"][14]["payload"]["credit_limit_cents"] = -2
    with pytest.raises(BPValidationError, match="credit_limit_cents"):
        project_events(catalog)


def test_invalid_block_scope_is_rejected(catalog):
    catalog["events"][5]["payload"]["scope"] = "CUSTOMERS"
    with pytest.raises(BPValidationError, match="Alcance"):
        project_events(catalog)


def test_only_lead_can_convert_to_customer(catalog):
    catalog["events"][13]["payload"]["new_type"] = "V"
    with pytest.raises(BPValidationError, match="Lead"):
        project_events(catalog)


def test_inactive_partner_cannot_be_modified(catalog):
    final = catalog["events"][21]
    final["event_type"] = "CONTACT_ADDED"
    final["payload"] = {
        "contact_id": "CONT-L-99",
        "name": "Contacto simulado",
        "email": "simulado@example.test",
    }
    with pytest.raises(BPValidationError, match="inactivos"):
        project_events(catalog)


def test_duplicate_contact_is_rejected(catalog):
    catalog["events"][3]["event_type"] = "CONTACT_ADDED"
    catalog["events"][3]["payload"] = {
        "contact_id": "CONT-V-01",
        "name": "Contacto simulado",
        "email": "simulado@example.test",
    }
    with pytest.raises(BPValidationError, match="Contacto duplicado"):
        project_events(catalog)


def test_duplicate_address_is_rejected(catalog):
    catalog["events"][2]["event_type"] = "ADDRESS_ADDED"
    catalog["events"][2]["payload"] = {
        "address_id": "DIR-V-01",
        "kind": "FISCAL",
        "city": "San Luis Potosí",
        "country": "MX",
        "description": "Duplicado",
    }
    with pytest.raises(BPValidationError, match="Dirección duplicada"):
        project_events(catalog)


def test_mismatch_currency_blocks_purchase(catalog):
    catalog["events"][8]["payload"]["currency"] = "USD"
    catalog["events"][8]["payload"]["expected_result"] = "REJECTED"
    catalog["events"][8]["payload"]["expected_reason"] = "CURRENCY"
    results = project_events(catalog)["document_decisions"]
    assert results[1]["reason"] == "CURRENCY"


@pytest.mark.parametrize("invalid_amount", [0, -1, True, 2.5, "100"])
def test_purchase_amount_must_be_positive_integer(invalid_amount):
    partner = {
        "active": True, "bp_type": "V", "blocked": set(), "currency": "MXN",
        "open_balance_cents": 0, "credit_limit_cents": 0,
    }
    with pytest.raises(BPValidationError):
        decide_document(partner, "PURCHASE_ORDER", invalid_amount, "MXN")


def test_purchase_does_not_require_customer_credit_limit():
    partner = {
        "active": True, "bp_type": "V", "blocked": set(), "currency": "MXN",
        "open_balance_cents": 0, "credit_limit_cents": 0,
    }
    assert decide_document(partner, "PURCHASE_ORDER", 10_000, "MXN") == ("APPROVED", "NONE")


def test_blocked_partner_does_not_authorize_document():
    partner = {
        "active": True, "bp_type": "C", "blocked": {"SALES"}, "currency": "MXN",
        "open_balance_cents": 0, "credit_limit_cents": 100_000,
    }
    assert decide_document(partner, "SALES_ORDER", 10_000, "MXN") == ("REJECTED", "BLOCKED")


def test_empty_event_catalog_is_rejected(catalog):
    catalog["events"] = []
    with pytest.raises(BPValidationError, match="Sin eventos"):
        project_events(catalog)


def test_isa95_levels_are_consistent(catalog):
    catalog["events"][1]["isa95_target_level"] = 2
    with pytest.raises(BPValidationError, match="ERP 4"):
        project_events(catalog)
