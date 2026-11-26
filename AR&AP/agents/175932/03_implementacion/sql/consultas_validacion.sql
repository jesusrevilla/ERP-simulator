-- Consultas para la fase de pruebas futura. No son resultados de ejecución.
SELECT receipt_id, received, consumed, received-consumed AS available
FROM ap_capacity_175932.receipts ORDER BY receipt_id;

-- Debe devolver cero filas si coinciden el acumulado y el ledger.
SELECT * FROM ap_capacity_175932.balance_discrepancies;

SELECT event_id, result->>'status' AS status, result->>'reason' AS reason,
       result->>'consumed_before' AS consumed_before,
       result->>'consumed_after' AS consumed_after
FROM ap_capacity_175932.events ORDER BY created_at, event_id;

SELECT event_id, sent_at FROM ap_capacity_175932.outbox ORDER BY event_id;
