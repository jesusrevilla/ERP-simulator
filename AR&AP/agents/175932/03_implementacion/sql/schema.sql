-- Prototipo aislado. No reemplaza tablas ni funciones compartidas del ERP.
CREATE SCHEMA IF NOT EXISTS ap_capacity_175932;

CREATE TABLE IF NOT EXISTS ap_capacity_175932.receipts (
    receipt_id text PRIMARY KEY CHECK (length(receipt_id) BETWEEN 1 AND 100),
    supplier_id text NOT NULL CHECK (length(supplier_id) BETWEEN 1 AND 100),
    item_id text NOT NULL CHECK (length(item_id) BETWEEN 1 AND 100),
    received numeric(18,3) NOT NULL CHECK (received > 0),
    consumed numeric(18,3) NOT NULL DEFAULT 0,
    active boolean NOT NULL DEFAULT true,
    CHECK (consumed >= 0 AND consumed <= received)
);
CREATE TABLE IF NOT EXISTS ap_capacity_175932.invoices (
    document_id text PRIMARY KEY,
    receipt_id text NOT NULL REFERENCES ap_capacity_175932.receipts ON DELETE RESTRICT,
    quantity numeric(18,3) NOT NULL CHECK (quantity > 0),
    credited numeric(18,3) NOT NULL DEFAULT 0,
    CHECK (credited >= 0 AND credited <= quantity)
);
CREATE TABLE IF NOT EXISTS ap_capacity_175932.credits (
    document_id text PRIMARY KEY,
    invoice_id text NOT NULL REFERENCES ap_capacity_175932.invoices ON DELETE RESTRICT,
    quantity numeric(18,3) NOT NULL CHECK (quantity > 0)
);
CREATE TABLE IF NOT EXISTS ap_capacity_175932.events (
    event_id text PRIMARY KEY,
    payload jsonb NOT NULL,
    result jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS ap_capacity_175932.outbox (
    event_id text PRIMARY KEY REFERENCES ap_capacity_175932.events ON DELETE RESTRICT,
    body jsonb NOT NULL,
    sent_at timestamptz
);
CREATE INDEX IF NOT EXISTS capacity_pending_175932
    ON ap_capacity_175932.outbox (event_id) WHERE sent_at IS NULL;

CREATE OR REPLACE FUNCTION ap_capacity_175932.evaluate(p jsonb)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE
    eid text := p->>'event_id';
    rid text := p->>'receipt_id';
    kind text := p->>'kind';
    doc text := p->>'document_id';
    qty numeric;
    r ap_capacity_175932.receipts%ROWTYPE;
    inv ap_capacity_175932.invoices%ROWTYPE;
    prior ap_capacity_175932.events%ROWTYPE;
    reason text := 'INVALID_EVENT';
    accepted boolean := false;
    before_qty numeric;
    after_qty numeric;
    answer jsonb;
BEGIN
    -- An invalid identifier cannot be used as a durable idempotency key.
    IF jsonb_typeof(p) IS DISTINCT FROM 'object'
       OR jsonb_typeof(p->'event_id') IS DISTINCT FROM 'string'
       OR length(eid) NOT BETWEEN 1 AND 100 THEN
        RETURN jsonb_build_object('status','REJECTED','reason','INVALID_EVENT');
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended(eid, 175932));
    SELECT * INTO prior FROM ap_capacity_175932.events WHERE event_id = eid;
    IF FOUND THEN
        IF prior.payload = p THEN
            RETURN prior.result || jsonb_build_object('replay', true);
        END IF;
        RETURN jsonb_build_object('event_id',eid,'status','REJECTED',
                                 'reason','EVENT_KEY_CONFLICT','replay',false);
    END IF;

    IF jsonb_typeof(p->'receipt_id') = 'string' AND length(rid) BETWEEN 1 AND 100
       AND jsonb_typeof(p->'document_id') = 'string' AND length(doc) BETWEEN 1 AND 100
       AND kind IN ('INVOICE','CREDIT_QUANTITY')
       AND jsonb_typeof(p->'quantity') = 'string'
       AND (p->>'quantity') ~ '^[0-9]{1,15}(\.[0-9]{1,3})?$'
       AND NOT EXISTS (SELECT 1 FROM jsonb_object_keys(p) AS k(key)
                       WHERE key NOT IN ('event_id','receipt_id','kind','document_id','quantity','invoice_id'))
       AND ((kind = 'INVOICE' AND NOT p ? 'invoice_id')
            OR (kind = 'CREDIT_QUANTITY' AND jsonb_typeof(p->'invoice_id') = 'string'
                AND length(p->>'invoice_id') BETWEEN 1 AND 100)) THEN
        qty := (p->>'quantity')::numeric;
        IF qty > 0 THEN
            SELECT * INTO r FROM ap_capacity_175932.receipts
             WHERE receipt_id = rid FOR UPDATE;
            IF NOT FOUND THEN
                reason := 'RECEIPT_NOT_FOUND';
            ELSE
                before_qty := r.consumed;
                after_qty := r.consumed;
                IF NOT r.active THEN
                    reason := 'INACTIVE_RECEIPT';
                ELSIF kind = 'INVOICE' THEN
                    IF EXISTS (SELECT 1 FROM ap_capacity_175932.invoices WHERE document_id = doc) THEN
                        reason := 'DOCUMENT_EXISTS';
                    ELSIF qty > r.received - r.consumed THEN
                        reason := 'CAPACITY_EXCEEDED';
                    ELSE
                        INSERT INTO ap_capacity_175932.invoices(document_id, receipt_id, quantity)
                            VALUES (doc, rid, qty) ON CONFLICT DO NOTHING;
                        IF FOUND THEN
                            accepted := true;
                            after_qty := r.consumed + qty;
                            reason := 'CAPACITY_RESERVED';
                        ELSE
                            reason := 'DOCUMENT_EXISTS';
                        END IF;
                    END IF;
                ELSE
                    SELECT * INTO inv FROM ap_capacity_175932.invoices
                     WHERE document_id = p->>'invoice_id' AND receipt_id = rid FOR UPDATE;
                    IF NOT FOUND THEN
                        reason := 'INVOICE_NOT_FOUND';
                    ELSIF EXISTS (SELECT 1 FROM ap_capacity_175932.credits WHERE document_id = doc) THEN
                        reason := 'DOCUMENT_EXISTS';
                    ELSIF qty > inv.quantity - inv.credited THEN
                        reason := 'CREDIT_EXCEEDED';
                    ELSE
                        INSERT INTO ap_capacity_175932.credits(document_id, invoice_id, quantity)
                            VALUES (doc, inv.document_id, qty) ON CONFLICT DO NOTHING;
                        IF FOUND THEN
                            UPDATE ap_capacity_175932.invoices SET credited = credited + qty
                             WHERE document_id = inv.document_id;
                            accepted := true;
                            after_qty := r.consumed - qty;
                            reason := 'CAPACITY_RELEASED';
                        ELSE
                            reason := 'DOCUMENT_EXISTS';
                        END IF;
                    END IF;
                END IF;
                IF accepted THEN
                    UPDATE ap_capacity_175932.receipts SET consumed = after_qty WHERE receipt_id = rid;
                END IF;
            END IF;
        END IF;
    END IF;

    answer := jsonb_build_object(
        'event_id',eid,'agent','APReceiptCapacityAgent','activity','CHECK_ACCUMULATED_CAPACITY',
        'status',CASE WHEN accepted THEN 'ACCEPTED' ELSE 'REJECTED' END,
        'reason',reason,'replay',false,'receipt_id',rid,'document_id',doc,
        'kind',kind,'invoice_id',p->>'invoice_id','quantity',qty,
        'supplier_id',r.supplier_id,'item_id',r.item_id,'received',r.received,
        'consumed_before',before_qty,'consumed_after',after_qty,
        'available_after',r.received - after_qty,'reported_at',clock_timestamp());
    INSERT INTO ap_capacity_175932.events(event_id,payload,result) VALUES(eid,p,answer);
    INSERT INTO ap_capacity_175932.outbox(event_id,body) VALUES(eid,answer);
    RETURN answer;
END;
$$;

-- Control de reconciliación: debe devolver cero filas cuando el ledger coincide.
CREATE OR REPLACE VIEW ap_capacity_175932.balance_discrepancies AS
SELECT r.receipt_id, r.consumed,
       COALESCE(sum(i.quantity - i.credited),0) AS ledger_consumed
FROM ap_capacity_175932.receipts r
LEFT JOIN ap_capacity_175932.invoices i USING (receipt_id)
GROUP BY r.receipt_id, r.consumed
HAVING r.consumed <> COALESCE(sum(i.quantity - i.credited),0);
