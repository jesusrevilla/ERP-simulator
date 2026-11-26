"""APReceiptCapacityAgent: transactional accumulated receipt capacity."""
import argparse
from decimal import Decimal
from functools import partial
import json
import os
from pathlib import Path
from contract import parse_quantity

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb, set_json_loads
from neo4j import GraphDatabase
from pymongo import MongoClient

HERE = Path(__file__).resolve().parent


def required(name):
    value = os.getenv(name)
    if not value:
        raise ValueError(f'Missing environment variable: {name}')
    return value


def connect():
    conn = psycopg.connect(required('PG_DSN'), row_factory=dict_row)
    set_json_loads(partial(json.loads, parse_float=Decimal), conn)
    return conn


def serializable(value):
    """Preserve decimal quantities as strings in projections and reports."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: serializable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serializable(item) for item in value]
    return value


def initialize_sql():
    with connect() as conn:
        conn.execute((HERE / 'sql/schema.sql').read_text(encoding='utf-8'))


def register_receipt(receipt_id, supplier_id, item_id, quantity):
    """Explicit adapter for prevalidated receipt lines, not an ERP importer."""
    parse_quantity(quantity)
    with connect() as conn:
        conn.execute('''INSERT INTO ap_capacity_175932.receipts
            (receipt_id, supplier_id, item_id, received) VALUES (%s,%s,%s,%s)
            ON CONFLICT (receipt_id) DO NOTHING''',
            (receipt_id, supplier_id, item_id, Decimal(quantity)))
        row = conn.execute('''SELECT supplier_id,item_id,received
            FROM ap_capacity_175932.receipts WHERE receipt_id=%s''', (receipt_id,)).fetchone()
        if row != dict(supplier_id=supplier_id, item_id=item_id, received=Decimal(quantity)):
            raise ValueError('Receipt already registered with different contents')


def evaluate(payload):
    # Transaction commits the ledger, decision and durable outbox together.
    with connect() as conn:
        result = conn.execute('SELECT ap_capacity_175932.evaluate(%s) AS result',
                              (Jsonb(payload),)).fetchone()['result']
    return serializable(result)


def export_pending(limit=100):
    """At-least-once delivery with destination idempotency; no distributed commit."""
    if limit < 1:
        raise ValueError('Limit must be positive')
    database = os.getenv('NEO4J_DATABASE', 'neo4j')
    exported = 0
    with GraphDatabase.driver(required('NEO4J_URI'), auth=(
            required('NEO4J_USERNAME'), required('NEO4J_PASSWORD'))) as graph, \
            MongoClient(required('MONGO_URI'), serverSelectionTimeoutMS=5000) as mongo:
        graph.verify_connectivity()
        mongo.admin.command('ping')
        collection = mongo[os.getenv('MONGO_DATABASE', 'erp_agent_demo')]['capacity_reports_175932']
        # _id is MongoDB's built-in unique idempotency key.
        for statement in (
            'CREATE CONSTRAINT decision_175932 IF NOT EXISTS FOR (e:Decision175932) REQUIRE e.event_id IS UNIQUE',
            'CREATE CONSTRAINT receipt_175932 IF NOT EXISTS FOR (r:Receipt175932) REQUIRE r.receipt_id IS UNIQUE',
            'CREATE CONSTRAINT supplier_175932 IF NOT EXISTS FOR (s:Supplier175932) REQUIRE s.supplier_id IS UNIQUE',
            'CREATE CONSTRAINT document_175932 IF NOT EXISTS FOR (d:Document175932) REQUIRE (d.kind,d.document_id) IS UNIQUE',
        ):
            graph.execute_query(statement, database_=database)
        cypher = (HERE / 'graph.cypher').read_text(encoding='utf-8')
        for _ in range(limit):
            with connect() as conn:
                row = conn.execute('''SELECT event_id,body FROM ap_capacity_175932.outbox
                    WHERE sent_at IS NULL ORDER BY event_id
                    LIMIT 1 FOR UPDATE SKIP LOCKED''').fetchone()
                if row is None:
                    break
                body = serializable(row['body'])
                params = {key: body.get(key) for key in (
                    'event_id','status','reason','agent','activity','reported_at','quantity',
                    'consumed_before','consumed_after','available_after','receipt_id',
                    'supplier_id','document_id','kind','invoice_id')}
                graph.execute_query(cypher, parameters_=params, database_=database)
                collection.update_one({'_id': row['event_id']},
                                      {'$setOnInsert': body}, upsert=True)
                conn.execute('''UPDATE ap_capacity_175932.outbox
                    SET sent_at=clock_timestamp() WHERE event_id=%s''', (row['event_id'],))
                exported += 1
    return {'exported': exported}


def inspect_state():
    with connect() as conn:
        receipts = conn.execute('''SELECT receipt_id,received,consumed,
            received-consumed AS available FROM ap_capacity_175932.receipts
            ORDER BY receipt_id''').fetchall()
        pending = conn.execute('''SELECT count(*) AS count FROM
            ap_capacity_175932.outbox WHERE sent_at IS NULL''').fetchone()['count']
        mismatches = conn.execute('SELECT * FROM ap_capacity_175932.balance_discrepancies').fetchall()
    return serializable(dict(receipts=receipts, pending_reports=pending, discrepancies=mismatches))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init', help='Create only the isolated PostgreSQL schema')
    seed = sub.add_parser('add-receipt', help='Register a prevalidated receipt line')
    for field in ('receipt', 'supplier', 'item', 'quantity'):
        seed.add_argument('--' + field, required=True)
    run = sub.add_parser('evaluate')
    run.add_argument('event_file', type=Path)
    export = sub.add_parser('export')
    export.add_argument('--limit', type=int, default=100)
    sub.add_parser('status')
    args = parser.parse_args()
    if args.command == 'init':
        initialize_sql()
        result = {'schema': 'ap_capacity_175932', 'initialized': True}
    elif args.command == 'add-receipt':
        register_receipt(args.receipt, args.supplier, args.item, args.quantity)
        result = {'receipt_id': args.receipt, 'registered': True}
    elif args.command == 'evaluate':
        payload = json.loads(args.event_file.read_text(encoding='utf-8'))
        result = evaluate(payload)
    elif args.command == 'export':
        result = export_pending(args.limit)
    else:
        result = inspect_state()
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
