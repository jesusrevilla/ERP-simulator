"""Tutorial Neo4j: grafo de socios de negocio (Business Partners).

Usa eventos y datos de prueba creados para TechAssembly. Carga idempotente
mediante MERGE; no elimina nodos ni toca inventarios o materiales de otros.
"""
import argparse
import os

from src.business_partner_events_cristian import load_catalog, project_events


SCOPE = "CristianGodinez-ERP-BP-2026"

BP_QUERY = """
UNWIND $rows AS row
MERGE (bp:CGBPartner {card_code: row.card_code})
SET bp.name = row.name,
    bp.bp_type = row.bp_type,
    bp.group_name = row.group_name,
    bp.currency = row.currency,
    bp.active = row.active,
    bp.credit_limit_cents = row.credit_limit_cents,
    bp.scope = $scope
"""

EVENT_QUERY = """
UNWIND $rows AS row
MATCH (bp:CGBPartner {card_code: row.card_code, scope: $scope})
MERGE (e:CGBPartnerEvent {event_id: row.event_id})
SET e.event_type = row.event_type,
    e.occurred_at = datetime(row.timestamp_utc),
    e.scope = $scope
MERGE (e)-[:CG_REFERS_TO_BP]->(bp)
"""

CONTACT_QUERY = """
UNWIND $rows AS row
MATCH (bp:CGBPartner {card_code: row.card_code, scope: $scope})
MERGE (c:CGBPartnerContact {contact_key: row.contact_key})
SET c.name = row.name, c.scope = $scope
MERGE (bp)-[:CG_HAS_CONTACT]->(c)
"""

ADDRESS_QUERY = """
UNWIND $rows AS row
MATCH (bp:CGBPartner {card_code: row.card_code, scope: $scope})
MERGE (a:CGBPartnerAddress {address_key: row.address_key})
SET a.kind = row.kind, a.city = row.city, a.country = row.country, a.scope = $scope
MERGE (bp)-[:CG_HAS_ADDRESS]->(a)
"""

COUNT_QUERY = """
MATCH (bp:CGBPartner {scope: $scope})
WITH count(bp) AS business_partners
MATCH (e:CGBPartnerEvent {scope: $scope})
RETURN business_partners, count(e) AS events
"""

GRAPH_QUERIES = (BP_QUERY, EVENT_QUERY, CONTACT_QUERY, ADDRESS_QUERY)


def graph_rows(catalog):
    projected = project_events(catalog)
    partners, contacts, addresses, events = [], [], [], []
    for code, bp in projected["partners"].items():
        partners.append({
            "card_code": code,
            "name": bp["name"],
            "bp_type": bp["bp_type"],
            "group_name": bp["group"],
            "currency": bp["currency"],
            "active": bp["active"],
            "credit_limit_cents": bp["credit_limit_cents"],
        })
        for contact in bp["contacts"]:
            contacts.append({
                "card_code": code,
                "contact_key": f"{code}:{contact['contact_id']}",
                "name": contact["name"],
            })
        for address in bp["addresses"]:
            addresses.append({
                "card_code": code,
                "address_key": f"{code}:{address['address_id']}",
                "kind": address["kind"],
                "city": address["city"],
                "country": address["country"],
            })
    for event in catalog["events"]:
        events.append({
            "event_id": event["event_id"],
            "card_code": event["card_code"],
            "event_type": event["event_type"],
            "timestamp_utc": event["timestamp_utc"],
        })
    return {
        "partners": partners,
        "contacts": contacts,
        "addresses": addresses,
        "events": events,
    }


def load_graph(driver, catalog, database="neo4j"):
    rows = graph_rows(catalog)
    constraints = [
        "CREATE CONSTRAINT cg_bp_code IF NOT EXISTS FOR (n:CGBPartner) REQUIRE n.card_code IS UNIQUE",
        "CREATE CONSTRAINT cg_bp_event IF NOT EXISTS FOR (n:CGBPartnerEvent) REQUIRE n.event_id IS UNIQUE",
        "CREATE CONSTRAINT cg_bp_contact IF NOT EXISTS FOR (n:CGBPartnerContact) REQUIRE n.contact_key IS UNIQUE",
        "CREATE CONSTRAINT cg_bp_address IF NOT EXISTS FOR (n:CGBPartnerAddress) REQUIRE n.address_key IS UNIQUE",
    ]
    for query in constraints:
        driver.execute_query(query, database_=database)
    for query, key in zip(GRAPH_QUERIES, ("partners", "events", "contacts", "addresses")):
        driver.execute_query(query, rows=rows[key], scope=SCOPE, database_=database)
    return rows


def count_graph(driver, database="neo4j"):
    records, _, _ = driver.execute_query(COUNT_QUERY, scope=SCOPE, database_=database)
    if not records:
        return 0, 0
    row = records[0]
    return int(row["business_partners"]), int(row["events"])


def main():
    parser = argparse.ArgumentParser(description="Tutorial de Neo4j: Business Partners")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    catalog = load_catalog()
    rows = graph_rows(catalog)
    print(
        f"Socios: {len(rows['partners'])}; "
        f"contactos: {len(rows['contacts'])}; "
        f"direcciones: {len(rows['addresses'])}; "
        f"eventos: {len(rows['events'])}"
    )
    if args.offline:
        print("Validación del catálogo BP sin Neo4j: OK")
        return

    from neo4j import GraphDatabase

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    username = os.getenv("NEO4J_USERNAME", os.getenv("NEO4J_USER", "neo4j"))
    password = os.getenv("NEO4J_PASSWORD")
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    if not password:
        raise ValueError("Define NEO4J_PASSWORD como variable de entorno")

    with GraphDatabase.driver(uri, auth=(username, password)) as driver:
        driver.verify_connectivity()
        load_graph(driver, catalog, database)
        partner_count, event_count = count_graph(driver, database)
        if (partner_count, event_count) != (len(rows["partners"]), len(rows["events"])):
            raise AssertionError("Neo4j no coincide con el catálogo BP")
        load_graph(driver, catalog, database)
        again = count_graph(driver, database)
        if again != (partner_count, event_count):
            raise AssertionError("La carga MERGE no fue idempotente")
        print(f"Neo4j OK: {partner_count} Business Partners, {event_count} eventos; MERGE idempotente")


if __name__ == "__main__":
    main()
