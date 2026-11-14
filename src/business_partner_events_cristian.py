"""Validador y proyector de eventos del módulo Business Partners.

Ejercicio académico autónomo: no es una API de SAP Business One ni
se conecta a datos reales. Modelo de eventos ISA-95 a nivel conceptual.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_CATALOG = (
    Path(__file__).resolve().parents[1]
    / "Business-Partner"
    / "CristianGodinez_BP_events.json"
)

PARTNER_TYPES = {"C", "V", "L"}
CURRENCIES = {"MXN", "USD", "EUR"}
EVENT_TYPES = {
    "BP_REGISTERED",
    "ADDRESS_ADDED",
    "CONTACT_ADDED",
    "PAYMENT_TERMS_UPDATED",
    "PARTNER_TAG_ADDED",
    "PARTNER_BLOCKED",
    "PARTNER_UNBLOCKED",
    "DOCUMENT_ATTEMPTED",
    "LEAD_CONVERTED",
    "CREDIT_LIMIT_UPDATED",
    "PARTNER_DEACTIVATED",
}


class BPValidationError(ValueError):
    pass


def _require_string(obj, field):
    value = obj.get(field)
    if not isinstance(value, str) or not value.strip():
        raise BPValidationError(f"{field}: texto obligatorio")
    return value.strip()


def _require_nonnegative_int(obj, field):
    value = obj.get(field)
    if type(value) is not int or value < 0:
        raise BPValidationError(f"{field}: entero no negativo obligatorio")
    return value


def _parse_timestamp(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise BPValidationError("Marca de tiempo UTC ISO 8601 obligatoria")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise BPValidationError("Marca de tiempo inválida") from None
    if timestamp.utcoffset() != timezone.utc.utcoffset(timestamp):
        raise BPValidationError("Marca de tiempo no UTC")
    return timestamp


def load_catalog(path=DEFAULT_CATALOG):
    catalog = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(catalog, dict) or catalog.get("simulated_data") is not True:
        raise BPValidationError("Se requiere un catálogo didáctico identificado como simulado")
    if not isinstance(catalog.get("events"), list) or not catalog["events"]:
        raise BPValidationError("No hay eventos de socios de negocio")
    return catalog


def decide_document(partner, document_type, amount_cents, currency):
    if type(amount_cents) is not int or amount_cents <= 0:
        raise BPValidationError("La operación requiere un importe positivo en centavos")
    if document_type not in {"PURCHASE_ORDER", "SALES_ORDER"}:
        raise BPValidationError("Documento comercial desconocido")
    if not partner["active"]:
        return "REJECTED", "INACTIVE"
    expected_type = "V" if document_type == "PURCHASE_ORDER" else "C"
    if partner["bp_type"] != expected_type:
        return "REJECTED", "PARTNER_TYPE"
    restriction = "PURCHASES" if document_type == "PURCHASE_ORDER" else "SALES"
    if restriction in partner["blocked"]:
        return "REJECTED", "BLOCKED"
    if currency != partner["currency"]:
        return "REJECTED", "CURRENCY"
    if document_type == "SALES_ORDER":
        if amount_cents + partner["open_balance_cents"] > partner["credit_limit_cents"]:
            return "REJECTED", "CREDIT_LIMIT"
    return "APPROVED", "NONE"


def project_events(catalog):
    """Reproduce eventos ordenados, comprueba reglas y devuelve estados y decisiones.

    Los intentos de documentos no crean documentos ni modifican saldos:
    se registran solo como decisiones de validación.
    """
    if not isinstance(catalog, dict) or catalog.get("simulated_data") is not True:
        raise BPValidationError("Catálogo de simulación inválido")
    events = catalog.get("events")
    if not isinstance(events, list) or not events:
        raise BPValidationError("Sin eventos")
    partner_states = {}
    event_ids = set()
    document_results = []
    previous_time = None

    for event in events:
        if not isinstance(event, dict):
            raise BPValidationError("Evento inválido")
        event_id = _require_string(event, "event_id")
        if event_id in event_ids:
            raise BPValidationError(f"ID de evento duplicado: {event_id}")
        event_ids.add(event_id)
        current_time = _parse_timestamp(event.get("timestamp_utc"))
        if previous_time is not None and current_time <= previous_time:
            raise BPValidationError("Eventos desordenados o con la misma fecha")
        previous_time = current_time
        event_type = _require_string(event, "event_type")
        if event_type not in EVENT_TYPES:
            raise BPValidationError(f"Tipo de evento no admitido: {event_type}")
        code = _require_string(event, "card_code")
        _require_string(event, "actor_role")
        if (event.get("isa95_source_level"), event.get("isa95_target_level")) != (4, 3):
            raise BPValidationError("Se espera nivel ERP 4 a MOM 3")
        if event.get("source_system") != "ERP_LEVEL_4" or event.get("target_system") != "MOM_LEVEL_3":
            raise BPValidationError("Sistemas emisores y receptores inconsistentes")
        payload = event.get("payload")
        if not isinstance(payload, dict):
            raise BPValidationError("Payload no válido")

        if event_type == "BP_REGISTERED":
            if code in partner_states:
                raise BPValidationError(f"CardCode duplicado: {code}")
            bp_type = _require_string(payload, "bp_type")
            if bp_type not in PARTNER_TYPES:
                raise BPValidationError("CardType debe ser C, V o L")
            currency = _require_string(payload, "currency")
            if currency not in CURRENCIES:
                raise BPValidationError("Moneda no válida")
            active = payload.get("active")
            if type(active) is not bool or not active:
                raise BPValidationError("Un nuevo socio debe estar activo")
            partner_states[code] = {
                "card_code": code,
                "name": _require_string(payload, "name"),
                "bp_type": bp_type,
                "group": _require_string(payload, "group"),
                "tax_id": _require_string(payload, "tax_id"),
                "currency": currency,
                "active": True,
                "blocked": set(),
                "addresses": {},
                "contacts": {},
                "tags": set(),
                "payment_terms": "NET_0",
                "credit_limit_cents": 0,
                "open_balance_cents": 0,
            }
            continue

        if code not in partner_states:
            raise BPValidationError(f"El CardCode {code} no existe")
        partner = partner_states[code]

        if event_type == "DOCUMENT_ATTEMPTED":
            result, reason = decide_document(
                partner,
                _require_string(payload, "document_type"),
                _require_nonnegative_int(payload, "amount_cents"),
                _require_string(payload, "currency"),
            )
            if result != payload.get("expected_result") or reason != payload.get("expected_reason"):
                raise BPValidationError(f"Resultado de prueba inconsistente: {event_id}")
            document_results.append({
                "event_id": event_id,
                "card_code": code,
                "result": result,
                "reason": reason,
            })
            continue

        if not partner["active"]:
            raise BPValidationError("No se admiten modificaciones a socios inactivos")

        if event_type == "ADDRESS_ADDED":
            address_id = _require_string(payload, "address_id")
            if address_id in partner["addresses"]:
                raise BPValidationError("Dirección duplicada")
            kind = _require_string(payload, "kind")
            if kind not in {"FISCAL", "SHIPPING"}:
                raise BPValidationError("Tipo de dirección inválido")
            partner["addresses"][address_id] = {
                "address_id": address_id, "kind": kind,
                "city": _require_string(payload, "city"),
                "country": _require_string(payload, "country"),
                "description": _require_string(payload, "description"),
            }
        elif event_type == "CONTACT_ADDED":
            contact_id = _require_string(payload, "contact_id")
            if contact_id in partner["contacts"]:
                raise BPValidationError("Contacto duplicado")
            email = _require_string(payload, "email")
            if "@" not in email or email.startswith("@") or email.endswith("@"):
                raise BPValidationError("Formato de correo inválido")
            partner["contacts"][contact_id] = {
                "contact_id": contact_id,
                "name": _require_string(payload, "name"),
                "email": email,
            }
        elif event_type == "PAYMENT_TERMS_UPDATED":
            terms = _require_string(payload, "payment_terms")
            if terms not in {"NET_0", "NET_15", "NET_30", "NET_45", "NET_60"}:
                raise BPValidationError("Condiciones de pago no reconocidas")
            currency = _require_string(payload, "currency")
            if currency not in CURRENCIES:
                raise BPValidationError("Moneda no reconocida")
            partner["payment_terms"] = terms
            partner["currency"] = currency
        elif event_type == "PARTNER_TAG_ADDED":
            tag = _require_string(payload, "tag")
            if tag in partner["tags"]:
                raise BPValidationError("Etiqueta comercial repetida")
            partner["tags"].add(tag)
        elif event_type in {"PARTNER_BLOCKED", "PARTNER_UNBLOCKED"}:
            scope = _require_string(payload, "scope")
            if scope not in {"PURCHASES", "SALES", "ALL"}:
                raise BPValidationError("Alcance de bloqueo inválido")
            _require_string(payload, "reason")
            requested = {"PURCHASES", "SALES"} if scope == "ALL" else {scope}
            if event_type == "PARTNER_BLOCKED":
                partner["blocked"].update(requested)
            else:
                partner["blocked"].difference_update(requested)
        elif event_type == "LEAD_CONVERTED":
            if partner["bp_type"] != "L" or payload.get("new_type") != "C":
                raise BPValidationError("Únicamente se convierte Lead L a Cliente C")
            if payload.get("preserve_contacts") is not True or payload.get("preserve_addresses") is not True:
                raise BPValidationError("Se exige preservar contactos y direcciones")
            partner["bp_type"] = "C"
        elif event_type == "CREDIT_LIMIT_UPDATED":
            if partner["bp_type"] != "C":
                raise BPValidationError("El límite de crédito aplica a clientes")
            if payload.get("currency") != partner["currency"]:
                raise BPValidationError("Moneda de crédito no coincide con BP")
            partner["credit_limit_cents"] = _require_nonnegative_int(payload, "credit_limit_cents")
            partner["open_balance_cents"] = _require_nonnegative_int(payload, "open_balance_cents")
        elif event_type == "PARTNER_DEACTIVATED":
            _require_string(payload, "reason")
            partner["active"] = False

    normalized = {}
    for code, value in partner_states.items():
        normalized[code] = {
            **value,
            "blocked": sorted(value["blocked"]),
            "tags": sorted(value["tags"]),
            "addresses": sorted(value["addresses"].values(), key=lambda a: a["address_id"]),
            "contacts": sorted(value["contacts"].values(), key=lambda a: a["contact_id"]),
        }
    return {"partners": normalized, "document_decisions": document_results, "event_count": len(events)}


def main():
    parser = argparse.ArgumentParser(description="Validar eventos del módulo Business Partners")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    args = parser.parse_args()
    result = project_events(load_catalog(args.catalog))
    for code, partner in result["partners"].items():
        print(
            f"{code}: {partner['bp_type']}, activo={partner['active']}, "
            f"contactos={len(partner['contacts'])}, direcciones={len(partner['addresses'])}"
        )
    for decision in result["document_decisions"]:
        print(f"{decision['event_id']}: {decision['result']} ({decision['reason']})")
    print(f"Business Partners: {len(result['partners'])}; eventos validados: {result['event_count']}")


if __name__ == "__main__":
    main()
