// Ver nodos y relaciones de esta contribución, sin tocar otros alumnos.
MATCH p=(e:Decision175932)-[:REPORTS_ON]->(r:Receipt175932)
OPTIONAL MATCH (e)-[:ABOUT]->(d:Document175932)
RETURN p, d;

// Revisar decisiones de una recepción. Cambiar REC-001 si es necesario.
MATCH (e:Decision175932)-[:REPORTS_ON]->(:Receipt175932 {receipt_id:'REC-001'})
RETURN e.event_id, e.status, e.reason, e.consumed_before,
       e.consumed_after, e.available_after, e.reported_at
ORDER BY e.reported_at, e.event_id;

// Conteos para contraste futuro con eventos PostgreSQL y bitácora MongoDB.
MATCH (e:Decision175932)
RETURN e.status AS status, e.reason AS reason, count(*) AS events
ORDER BY status, reason;
