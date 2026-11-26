MERGE (e:Decision175932 {event_id: $event_id})
ON CREATE SET e.status = $status, e.reason = $reason, e.agent = $agent,
              e.activity = $activity, e.reported_at = $reported_at,
              e.quantity = $quantity, e.consumed_before = $consumed_before,
              e.consumed_after = $consumed_after, e.available_after = $available_after
FOREACH (_ IN CASE WHEN $receipt_id IS NOT NULL THEN [1] ELSE [] END |
    MERGE (r:Receipt175932 {receipt_id: $receipt_id})
    MERGE (e)-[:REPORTS_ON]->(r)
    FOREACH (_ IN CASE WHEN $supplier_id IS NOT NULL THEN [1] ELSE [] END |
        MERGE (s:Supplier175932 {supplier_id: $supplier_id})
        MERGE (r)-[:RECEIVED_FROM]->(s)
    )
)
FOREACH (_ IN CASE WHEN $document_id IS NOT NULL AND $kind IS NOT NULL THEN [1] ELSE [] END |
    MERGE (d:Document175932 {document_id: $document_id, kind: $kind})
    MERGE (e)-[:ABOUT]->(d)
    FOREACH (_ IN CASE WHEN $kind = 'CREDIT_QUANTITY' AND $invoice_id IS NOT NULL THEN [1] ELSE [] END |
        MERGE (i:Document175932 {document_id: $invoice_id, kind: 'INVOICE'})
        MERGE (d)-[:CREDITS]->(i)
    )
)
RETURN e.event_id AS event_id;
