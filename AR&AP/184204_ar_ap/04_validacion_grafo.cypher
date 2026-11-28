MERGE (p:Proveedor {proveedor_id: 1})
  ON CREATE SET p.nombre = 'Proveedor Industrial S.A.';

MERGE (oc:OrdenCompra {oc_id: 5})
  ON CREATE SET oc.articulo = 'A200', oc.cantidad_ordenada = 20, oc.precio_unitario = 50.00, oc.estatus = 'A';

MERGE (rec:Recepcion {recepcion_id: 1})
  ON CREATE SET rec.articulo = 'A200', rec.cantidad_recibida = 10, rec.usuario = 'agente_recepcion';

MERGE (fac:FacturaProveedor {factura_id: 1})
  ON CREATE SET fac.articulo = 'A200', fac.cantidad_facturada = 10, fac.precio_unitario = 50.00, fac.monto_total = 500.00, fac.saldo = 0.00, fac.estatus = 'C';

MERGE (pag:Pago {pago_id: 1})
  ON CREATE SET pag.monto_aplicado = 500.00, pag.usuario = 'agente_ap';

MERGE (p)-[:EMITE_OC]->(oc)
MERGE (oc)-[:TIENE_RECEPCION]->(rec)
MERGE (rec)-[:RESPALDA_FACTURA]->(fac)
MERGE (oc)-[:FACTURADA_EN]->(fac)
MERGE (fac)-[:LIQUIDADA_CON]->(pag);

MATCH (p:Proveedor)-[:EMITE_OC]->(oc:OrdenCompra)-[:TIENE_RECEPCION]->(rec:Recepcion)-[:RESPALDA_FACTURA]->(fac:FacturaProveedor)
OPTIONAL MATCH (fac)-[:LIQUIDADA_CON]->(pag:Pago)
RETURN
  p.proveedor_id AS proveedor,
  oc.oc_id AS orden_compra,
  oc.cantidad_ordenada AS cant_ordenada,
  rec.recepcion_id AS recepcion,
  rec.cantidad_recibida AS cant_recibida,
  fac.factura_id AS factura,
  fac.cantidad_facturada AS cant_facturada,
  (fac.precio_unitario = oc.precio_unitario AND fac.cantidad_facturada <= rec.cantidad_recibida) AS match_3_vias_valido,
  fac.estatus AS estatus_factura,
  pag.pago_id AS pago_asociado;
