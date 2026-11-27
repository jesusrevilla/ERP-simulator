// =====================================================================
// consultas_arap.cypher                                     Matrícula 183800
// Catálogo de consultas analíticas del Knowledge Graph A/R-A/P + ISA-95
//
// Cómo ejecutarlas: copiar una consulta en Neo4j Browser (http://localhost:7474)
// o con  cypher-shell -f consultas_arap.cypher . Cada consulta termina en ;
// Datos de ejemplo: seed_arap_183800.sql + sync_postgres_neo4j.py
// Sintaxis para Neo4j 5.x.
//
// Cada consulta indica qué agente del ERP la usa y qué decisión soporta.
// =====================================================================


// ---------------------------------------------------------------------
// Q1. Ciclo completo de una orden de compra (grafo)
//     OC -> recepción -> factura -> pago, con los eventos ISA-95 de cada paso.
//     Cambiar 'OC-4001' por otro folio de orden de compra.
// Agente:   Orquestador de Operaciones y Cadena de Suministro
// Decisión: ver el recorrido completo de una compra y los eventos que lo respaldan
// ---------------------------------------------------------------------
MATCH cadena = (p:Proveedor)-[:RECIBE_OC]->(oc:OrdenCompra {folio: 'OC-4001'})
               -[:SURTIDA_EN]->(r:Recepcion)-[:CONCILIADA_EN]->(f:FacturaProveedor)
               <-[:LIQUIDA]-(pg:Pago)
OPTIONAL MATCH (e:EventoISA95)-[:REGISTRADO_EN]->(d:Documento)
WHERE d IN nodes(cadena)
RETURN cadena, collect(e) AS eventos;


// ---------------------------------------------------------------------
// Q2. Línea de tiempo de la misma compra (tabla)
// Agente:   Orquestador de Operaciones y Cadena de Suministro
// Decisión: detectar en qué paso se detuvo un documento y reactivarlo
// ---------------------------------------------------------------------
MATCH (oc:OrdenCompra {folio: 'OC-4001'})-[:SURTIDA_EN]->(r:Recepcion)
      -[:CONCILIADA_EN]->(f:FacturaProveedor)<-[:LIQUIDA]-(pg:Pago)
UNWIND [oc, r, f, pg] AS d
MATCH (e:EventoISA95)-[:REGISTRADO_EN]->(d)
RETURN d.folio AS documento, e.tipo AS evento, e.timestamp AS momento, e.nivel AS nivel_isa95
ORDER BY momento;


// ---------------------------------------------------------------------
// Q3. Demora de cobro por cliente (A/R)
//     Días entre la fecha de la factura y su último cobro (facturas ya saldadas).
// Agente:   Riesgo Crediticio y Cobranza
// Decisión: clasificar clientes por su rapidez de pago y ajustar el crédito
// ---------------------------------------------------------------------
MATCH (c:Cliente)-[:TIENE_FACTURA]->(f:FacturaCliente)<-[:PAGA]-(cb:Cobro)
WHERE f.saldo = 0
WITH c, f, max(date(cb.fecha)) AS ultimo_cobro
RETURN c.codigo AS cliente,
       c.razon_social AS razon_social,
       count(f) AS facturas_liquidadas,
       round(avg(duration.inDays(date(f.fecha), ultimo_cobro).days), 1) AS dias_promedio_cobro
ORDER BY dias_promedio_cobro DESC;


// ---------------------------------------------------------------------
// Q4. Demora de pago por proveedor (A/P)
//     Días entre la fecha de la factura del proveedor y su último pago.
// Agente:   Orquestador de Operaciones / Compras y Tesorería
// Decisión: preferir proveedores que cumplen más rápido y planear la tesorería
// ---------------------------------------------------------------------
MATCH (p:Proveedor)-[:TIENE_FACTURA]->(f:FacturaProveedor)<-[:LIQUIDA]-(pg:Pago)
WHERE f.saldo = 0
WITH p, f, max(date(pg.fecha)) AS ultimo_pago
RETURN p.codigo AS proveedor,
       p.razon_social AS razon_social,
       count(f) AS facturas_liquidadas,
       round(avg(duration.inDays(date(f.fecha), ultimo_pago).days), 1) AS dias_promedio_pago
ORDER BY dias_promedio_pago DESC;


// ---------------------------------------------------------------------
// Q5. Clientes con varias facturas vencidas y abiertas (cadena de deuda)
//     Compara la deuda vencida contra el límite de crédito.
// Agente:   Riesgo Crediticio y Cobranza
// Decisión: frenar nuevos pedidos o priorizar la cobranza
// ---------------------------------------------------------------------
MATCH (c:Cliente)-[:TIENE_FACTURA]->(f:FacturaCliente)
WHERE f.saldo > 0 AND date(f.fecha_vencimiento) < date()
WITH c, count(f) AS facturas_vencidas, sum(f.saldo) AS deuda_vencida, collect(f.folio) AS folios
WHERE facturas_vencidas >= 2
RETURN c.codigo AS cliente,
       c.razon_social AS razon_social,
       facturas_vencidas,
       deuda_vencida,
       c.limite_credito AS limite_credito,
       round(100.0 * deuda_vencida / c.limite_credito, 1) AS pct_del_limite,
       folios
ORDER BY deuda_vencida DESC;


// ---------------------------------------------------------------------
// Q6. Artículos con un solo proveedor (concentración de riesgo)
// Agente:   Compras y Tesorería
// Decisión: buscar proveedores alternos para los artículos sin respaldo
// ---------------------------------------------------------------------
MATCH (p:Proveedor)-[:RECIBE_OC]->(:OrdenCompra)-[:INCLUYE]->(a:Articulo)
WITH a, collect(DISTINCT p) AS proveedores
WHERE size(proveedores) = 1
RETURN a.nombre AS articulo,
       proveedores[0].codigo AS proveedor_unico,
       proveedores[0].razon_social AS razon_social
ORDER BY articulo;


// ---------------------------------------------------------------------
// Q7. Facturas de proveedor vencidas y sin pagar por completo
// Agente:   Compras y Tesorería
// Decisión: priorizar los pagos y evitar recargos o pérdida de crédito
// ---------------------------------------------------------------------
MATCH (p:Proveedor)-[:TIENE_FACTURA]->(f:FacturaProveedor)
WHERE f.saldo > 0 AND date(f.fecha_vencimiento) < date()
RETURN p.razon_social AS proveedor,
       f.folio AS factura,
       f.saldo AS saldo_pendiente,
       duration.inDays(date(f.fecha_vencimiento), date()).days AS dias_vencida
ORDER BY dias_vencida DESC;


// ---------------------------------------------------------------------
// Q8. Mercancía recibida que todavía no se factura (compras estancadas)
// Agente:   Orquestador de Operaciones y Cadena de Suministro
// Decisión: reclamar o capturar la factura faltante del proveedor
// ---------------------------------------------------------------------
MATCH (p:Proveedor)-[:RECIBE_OC]->(oc:OrdenCompra)-[:SURTIDA_EN]->(r:Recepcion)
WHERE NOT (r)-[:CONCILIADA_EN]->(:FacturaProveedor)
RETURN p.razon_social AS proveedor,
       oc.folio AS orden_compra,
       r.folio AS recepcion,
       r.fecha AS recibida_el
ORDER BY recibida_el;


// ---------------------------------------------------------------------
// Q9. Documentos sin ningún evento ISA-95 (control de calidad)
// Agente:   Auditor Contable
// Decisión: marcar documentos sin trazabilidad operativa para revisión
// ---------------------------------------------------------------------
MATCH (d:Documento)
WHERE NOT (d)<-[:REGISTRADO_EN]-(:EventoISA95)
RETURN [x IN labels(d) WHERE x <> 'Documento'][0] AS tipo,
       d.folio AS folio,
       d.proceso AS proceso
ORDER BY tipo, folio;


// ---------------------------------------------------------------------
// Q10. Eventos huérfanos de A/R y A/P (su folio no existe en PostgreSQL)
//      Los eventos de MRP (producción) se excluyen: sus órdenes de
//      producción no pertenecen a las tablas A/R-A/P.
// Agente:   Auditor Contable
// Decisión: señalar eventos sin documento y corregir la fuente
// ---------------------------------------------------------------------
MATCH (e:EventoISA95)
WHERE e.huerfano = true AND e.proceso IN ['AR', 'AP']
RETURN e.fuente AS fuente, e.eventId AS evento, e.tipo AS tipo, e.folio AS folio_sin_documento
ORDER BY fuente, e.timestamp;


// ---------------------------------------------------------------------
// Q11. Eventos por nivel de la jerarquía ISA-95 (0 a 4)
// Agente:   Orquestador de Operaciones y Cadena de Suministro
// Decisión: saber desde qué niveles (ERP, MES, PLC, sensores) llega la información
// ---------------------------------------------------------------------
MATCH (n:NivelISA95)
OPTIONAL MATCH (e:EventoISA95)-[:DE_NIVEL]->(n)
RETURN n.nivel AS nivel, n.nombre AS descripcion, count(e) AS eventos
ORDER BY nivel DESC;


// ---------------------------------------------------------------------
// Q12. Tiempo entre eventos consecutivos de una fuente (cuellos de botella)
//      Cambiar '181585' por otra fuente (181779, 182028).
// Agente:   Orquestador de Operaciones y Cadena de Suministro
// Decisión: encontrar los pasos del proceso que más tardan
// ---------------------------------------------------------------------
MATCH (a:EventoISA95 {fuente: '181585'})-[:SIGUIENTE]->(b:EventoISA95)
RETURN a.proceso AS proceso,
       a.tipo AS desde,
       b.tipo AS hasta,
       duration.inSeconds(datetime(a.timestamp), datetime(b.timestamp)).seconds AS segundos
ORDER BY a.timestamp;


// ---------------------------------------------------------------------
// Q13. Recorridos posibles del proceso de compras (eventos_ap.json)
//      Incluye las decisiones de las compuertas (3-way match, saldo = 0).
// Agente:   Orquestador de Operaciones y Cadena de Suministro
// Decisión: validar que el proceso tenga salida exitosa y salida por rechazo
// ---------------------------------------------------------------------
MATCH ruta = (:PasoProceso {id: 'P0'})-[:SIGUIENTE*..12]->(:PasoProceso {tipo: 'fin'})
RETURN [n IN nodes(ruta) | n.nombre] AS pasos,
       [r IN relationships(ruta) WHERE r.condicion IS NOT NULL | r.condicion] AS decisiones;
