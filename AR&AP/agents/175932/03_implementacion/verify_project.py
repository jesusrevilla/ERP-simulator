"""Produce real evidence only after the test suite and backend checks succeed."""
import io
import json
import os
from pathlib import Path
import platform
import sys
import unittest
from datetime import datetime, timezone

from neo4j import GraphDatabase
from pymongo import MongoClient
import agent
import test_unit
import test_integration


class EvidenceResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.cases.append({'test':test.id(),'status':'passed'})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.cases.append({'test':test.id(),'status':'failed'})

    def addError(self, test, err):
        super().addError(test, err)
        self.cases.append({'test':test.id(),'status':'error'})


def main():
    output = Path('evidence')
    output.mkdir(exist_ok=True)
    suite = unittest.TestSuite([
        unittest.defaultTestLoader.loadTestsFromModule(test_unit),
        unittest.defaultTestLoader.loadTestsFromModule(test_integration)])
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=EvidenceResult).run(suite)
    (output/'tests.log').write_text(stream.getvalue(),encoding='utf-8')
    print(stream.getvalue(),flush=True)
    if not result.wasSuccessful():
        raise SystemExit(1)

    agent.register_receipt('REC-DEMO','PROV-DEMO','CPU','10')
    demo = []
    for event in [
        dict(event_id='DEMO-01',receipt_id='REC-DEMO',kind='INVOICE',document_id='FP-DEMO-01',quantity='6'),
        dict(event_id='DEMO-02',receipt_id='REC-DEMO',kind='INVOICE',document_id='FP-DEMO-02',quantity='6'),
        dict(event_id='DEMO-03',receipt_id='REC-DEMO',kind='CREDIT_QUANTITY',document_id='NC-DEMO-01',invoice_id='FP-DEMO-01',quantity='2'),
        dict(event_id='DEMO-04',receipt_id='REC-DEMO',kind='INVOICE',document_id='FP-DEMO-02',quantity='6'),
    ]:
        demo.append(agent.evaluate(event))
    assert [r['status'] for r in demo] == ['ACCEPTED','REJECTED','ACCEPTED','ACCEPTED']
    agent.export_pending(1000)
    state=agent.inspect_state()
    assert not state['discrepancies'] and state['pending_reports']==0
    with agent.connect() as conn:
        pg_version=conn.execute('SHOW server_version').fetchone()['server_version']
        event_count=conn.execute('SELECT count(*) AS n FROM ap_capacity_175932.events').fetchone()['n']
        postgres_events=conn.execute('SELECT event_id,result FROM ap_capacity_175932.events ORDER BY event_id').fetchall()
    with GraphDatabase.driver(os.environ['NEO4J_URI'],auth=(os.environ['NEO4J_USERNAME'],os.environ['NEO4J_PASSWORD'])) as graph:
        def query(statement,**params):
            return [r.data() for r in graph.execute_query(statement,database_='neo4j',**params).records]
        nodes=query('MATCH (n) WHERE n:Decision175932 OR n:Receipt175932 OR n:Supplier175932 OR n:Document175932 RETURN elementId(n) AS id, labels(n) AS labels, properties(n) AS props')
        links=query('MATCH (a)-[r]->(b) WHERE a:Decision175932 OR a:Receipt175932 OR a:Document175932 RETURN elementId(a) AS source, type(r) AS type, elementId(b) AS target')
        decisions=query('MATCH (e:Decision175932) RETURN e.event_id AS event_id,e.status AS status,e.reason AS reason ORDER BY event_id')
        graph_version=query('CALL dbms.components() YIELD versions RETURN versions')[0]['versions'][0]
    with MongoClient(os.environ['MONGO_URI']) as client:
        mongo_version=client.server_info()['version']
        collection=client[os.getenv('MONGO_DATABASE','erp_agent_demo')]['capacity_reports_175932']
        mongo_events=list(collection.find({}, {'_id':0}).sort('event_id',1))
    assert event_count==len(decisions)==len(mongo_events)
    assert [(r['event_id'],r['result']['status'],r['result']['reason']) for r in postgres_events] == [
        (r['event_id'],r['status'],r['reason']) for r in decisions] == [
        (r['event_id'],r['status'],r['reason']) for r in mongo_events]
    evidence=dict(status='passed',executed_at_utc=datetime.now(timezone.utc).isoformat(),
        source_commit=os.getenv('GITHUB_SHA'),
        run_url=f"https://github.com/{os.getenv('GITHUB_REPOSITORY')}/actions/runs/{os.getenv('GITHUB_RUN_ID')}",
        tests_run=result.testsRun,tests=result.cases,
        versions=dict(python=platform.python_version(),postgresql=pg_version,neo4j=graph_version,mongodb=mongo_version),
        demo=demo,state=state,events_postgresql=event_count,events_neo4j=len(decisions),events_mongodb=len(mongo_events),
        graph=dict(nodes=nodes,relationships=links),mongo_events=mongo_events)
    rendered=json.dumps(agent.serializable(evidence),ensure_ascii=False,indent=2)
    (output/'results.json').write_text(rendered+'\n',encoding='utf-8')
    print('EVIDENCE_JSON_BEGIN\n'+rendered+'\nEVIDENCE_JSON_END',flush=True)
    summary=os.getenv('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a',encoding='utf-8') as file:
            file.write(f'## APReceiptCapacityAgent\n\n{result.testsRun} pruebas correctas. '+
                f'Eventos reconciliados: PostgreSQL {event_count}, Neo4j {len(decisions)}, MongoDB {len(mongo_events)}.\n\n'+
                '| Evento | Estado | Motivo | Consumido después |\n|---|---|---|---|\n')
            for row in demo:
                file.write(f"| {row['event_id']} | {row['status']} | {row['reason']} | {row['consumed_after']} |\n")


if __name__=='__main__':
    main()
