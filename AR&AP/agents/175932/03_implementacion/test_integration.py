"""Real PostgreSQL + Neo4j + MongoDB checks, isolated synthetic fixtures."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import os
from threading import Barrier
import unittest
from unittest.mock import patch

from neo4j import GraphDatabase
from pymongo import MongoClient
import agent


class CapacityIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getenv('CAPACITY_TEST_MODE') != '1':
            raise RuntimeError('Set CAPACITY_TEST_MODE=1 only for an isolated test database')
        agent.initialize_sql()

    def setUp(self):
        self.prefix = self._testMethodName
        self.receipt = self.prefix + '-R'
        agent.register_receipt(self.receipt, 'SUP-DEMO', 'CPU', '10')

    def event(self, key, quantity='6', **changes):
        return dict(event_id=self.prefix+'-'+key, receipt_id=self.receipt,
                    kind='INVOICE', document_id=self.prefix+'-'+key, quantity=quantity) | changes

    def consumed(self):
        with agent.connect() as conn:
            return conn.execute('SELECT consumed FROM ap_capacity_175932.receipts WHERE receipt_id=%s',
                                (self.receipt,)).fetchone()['consumed']

    def test_accumulated_excess_and_exact_boundary(self):
        self.assertEqual(agent.evaluate(self.event('1'))['status'], 'ACCEPTED')
        self.assertEqual(agent.evaluate(self.event('2'))['reason'], 'CAPACITY_EXCEEDED')
        self.assertEqual(agent.evaluate(self.event('3', '4'))['status'], 'ACCEPTED')
        self.assertEqual(self.consumed(), Decimal('10'))

    def test_credit_releases_only_original_invoice_capacity(self):
        invoice = self.event('1')
        agent.evaluate(invoice)
        credit = self.event('2','2',kind='CREDIT_QUANTITY',invoice_id=invoice['document_id'])
        self.assertEqual(agent.evaluate(credit)['reason'], 'CAPACITY_RELEASED')
        self.assertEqual(agent.evaluate(self.event('3','5',kind='CREDIT_QUANTITY',
            invoice_id=invoice['document_id']))['reason'], 'CREDIT_EXCEEDED')
        self.assertEqual(agent.evaluate(self.event('4'))['status'], 'ACCEPTED')
        self.assertEqual(self.consumed(), Decimal('10'))

    def test_replay_and_conflicting_key(self):
        event = self.event('1')
        first = agent.evaluate(event)
        self.assertTrue(agent.evaluate(event)['replay'])
        self.assertEqual(agent.evaluate(event | {'quantity':'7'})['reason'], 'EVENT_KEY_CONFLICT')
        self.assertEqual(self.consumed(), Decimal('6'))
        with agent.connect() as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM ap_capacity_175932.events WHERE event_id=%s',
                                         (first['event_id'],)).fetchone()['n'], 1)

    def test_duplicate_document_does_not_consume_twice(self):
        event = self.event('1','4')
        agent.evaluate(event)
        self.assertEqual(agent.evaluate(event | {'event_id':self.prefix+'-retry'})['reason'], 'DOCUMENT_EXISTS')
        self.assertEqual(self.consumed(), Decimal('4'))

    def test_invalid_contract_missing_and_inactive_receipts(self):
        self.assertEqual(agent.evaluate(self.event('1',receipt_id='missing'))['reason'], 'RECEIPT_NOT_FOUND')
        for n, qty in enumerate(('0','-1','NaN','1.0001',2)):
            self.assertEqual(agent.evaluate(self.event(str(n+10),qty))['reason'], 'INVALID_EVENT')
        self.assertEqual(agent.evaluate(self.event('extra') | {'unknown':True})['reason'], 'INVALID_EVENT')
        with agent.connect() as conn:
            conn.execute('UPDATE ap_capacity_175932.receipts SET active=false WHERE receipt_id=%s',(self.receipt,))
        self.assertEqual(agent.evaluate(self.event('inactive'))['reason'], 'INACTIVE_RECEIPT')

    def test_credit_requires_invoice_from_same_receipt(self):
        agent.evaluate(self.event('original','5'))
        other = self.receipt+'2'
        agent.register_receipt(other,'SUP-DEMO','CPU','10')
        self.assertEqual(agent.evaluate(self.event('credit','1',kind='CREDIT_QUANTITY',
            invoice_id=self.prefix+'-original',receipt_id=other))['reason'], 'INVOICE_NOT_FOUND')

    def test_concurrent_invoices_cannot_overbook(self):
        barrier = Barrier(2)
        def process(key):
            barrier.wait(timeout=15)
            return agent.evaluate(self.event(key))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(process,['one','two']))
        self.assertEqual(sorted(r['status'] for r in results), ['ACCEPTED','REJECTED'])
        self.assertEqual(self.consumed(), Decimal('6'))

    def test_concurrent_same_event_is_idempotent(self):
        barrier = Barrier(2)
        def process(_):
            barrier.wait(timeout=15)
            return agent.evaluate(self.event('same'))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(process,range(2)))
        self.assertEqual(sum(r['replay'] for r in results), 1)
        self.assertEqual(self.consumed(), Decimal('6'))

    def test_rejected_replay_does_not_change_with_new_state(self):
        rejected = self.event('rejected','11')
        agent.evaluate(rejected)
        replay = agent.evaluate(rejected)
        self.assertTrue(replay['replay'])
        self.assertEqual(replay['reason'], 'CAPACITY_EXCEEDED')
        self.assertEqual(self.consumed(), Decimal('0'))

    def test_fractional_quantities_remain_exact(self):
        agent.evaluate(self.event('one','0.125'))
        agent.evaluate(self.event('two','0.375'))
        self.assertEqual(self.consumed(), Decimal('0.500'))

    def test_projection_failure_keeps_outbox_and_retry_deduplicates(self):
        event = self.event('projection')
        agent.evaluate(event)
        with MongoClient(os.environ['MONGO_URI']) as client:
            collection = client[os.getenv('MONGO_DATABASE','erp_agent_demo')]['capacity_reports_175932']
            with patch.object(type(collection), 'update_one', side_effect=RuntimeError('Injected Mongo write failure')):
                with self.assertRaises(RuntimeError):
                    agent.export_pending(1000)
            with agent.connect() as conn:
                self.assertIsNone(conn.execute('SELECT sent_at FROM ap_capacity_175932.outbox WHERE event_id=%s',
                                               (event['event_id'],)).fetchone()['sent_at'])
            agent.export_pending(1000)
            self.assertEqual(agent.export_pending(1000)['exported'],0)
            self.assertEqual(collection.count_documents({'_id':event['event_id']}),1)
        with GraphDatabase.driver(os.environ['NEO4J_URI'],auth=(os.environ['NEO4J_USERNAME'],os.environ['NEO4J_PASSWORD'])) as graph:
            result=graph.execute_query('MATCH (e:Decision175932 {event_id:$id}) RETURN count(e) AS n',
                                       id=event['event_id'],database_='neo4j')
            self.assertEqual(result.records[0]['n'],1)

    def test_sql_invariant_and_receipt_adapter_conflict(self):
        with self.assertRaises(ValueError):
            agent.register_receipt(self.receipt,'SUP-DEMO','CPU','20')
        with self.assertRaises(Exception):
            with agent.connect() as conn:
                conn.execute('UPDATE ap_capacity_175932.receipts SET consumed=11 WHERE receipt_id=%s',(self.receipt,))
        self.assertEqual(self.consumed(), Decimal('0'))
        with agent.connect() as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM ap_capacity_175932.balance_discrepancies').fetchone()['n'],0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
