// =====================================================================
// schema_neo4j_arap.cypher                                  Matrícula 183800
// Constraints e índices del Knowledge Graph A/R-A/P + eventos ISA-95
//
// - Es idempotente: todo usa IF NOT EXISTS, se puede ejecutar varias veces.
// - Lo ejecuta automáticamente sync_postgres_neo4j.py, o a mano con:
//       cypher-shell -u neo4j -p <password> -f schema_neo4j_arap.cypher
// - Sintaxis para Neo4j 5.x (el CI del repo usa neo4j:5.26-community).
// =====================================================================

// ---------- Nodos maestros ----------
CREATE CONSTRAINT cliente_rfc IF NOT EXISTS
  FOR (n:Cliente) REQUIRE n.rfc IS UNIQUE;

CREATE CONSTRAINT proveedor_rfc IF NOT EXISTS
  FOR (n:Proveedor) REQUIRE n.rfc IS UNIQUE;

CREATE CONSTRAINT articulo_nombre IF NOT EXISTS
  FOR (n:Articulo) REQUIRE n.nombre IS UNIQUE;

CREATE CONSTRAINT cuenta_contable_codigo IF NOT EXISTS
  FOR (n:CuentaContable) REQUIRE n.codigo IS UNIQUE;

// ---------- Nodos documentales: folio único por tipo ----------
CREATE CONSTRAINT pedido_venta_folio IF NOT EXISTS
  FOR (n:PedidoVenta) REQUIRE n.folio IS UNIQUE;

CREATE CONSTRAINT factura_cliente_folio IF NOT EXISTS
  FOR (n:FacturaCliente) REQUIRE n.folio IS UNIQUE;

CREATE CONSTRAINT cobro_folio IF NOT EXISTS
  FOR (n:Cobro) REQUIRE n.folio IS UNIQUE;

CREATE CONSTRAINT orden_compra_folio IF NOT EXISTS
  FOR (n:OrdenCompra) REQUIRE n.folio IS UNIQUE;

CREATE CONSTRAINT recepcion_folio IF NOT EXISTS
  FOR (n:Recepcion) REQUIRE n.folio IS UNIQUE;

CREATE CONSTRAINT factura_proveedor_folio IF NOT EXISTS
  FOR (n:FacturaProveedor) REQUIRE n.folio IS UNIQUE;

CREATE CONSTRAINT pago_folio IF NOT EXISTS
  FOR (n:Pago) REQUIRE n.folio IS UNIQUE;

// ---------- ISA-95 y proceso ----------
CREATE CONSTRAINT evento_id IF NOT EXISTS
  FOR (n:EventoISA95) REQUIRE n.eventId IS UNIQUE;

CREATE CONSTRAINT nivel_isa95 IF NOT EXISTS
  FOR (n:NivelISA95) REQUIRE n.nivel IS UNIQUE;

CREATE CONSTRAINT area_trabajo_clave IF NOT EXISTS
  FOR (n:AreaTrabajo) REQUIRE n.clave IS UNIQUE;

CREATE CONSTRAINT paso_proceso_id IF NOT EXISTS
  FOR (n:PasoProceso) REQUIRE n.id IS UNIQUE;

// ---------- Índices de apoyo para las consultas ----------
// Todos los documentos llevan además la etiqueta :Documento, así los
// eventos buscan por folio sin importar el tipo de documento.
CREATE INDEX documento_folio IF NOT EXISTS
  FOR (n:Documento) ON (n.folio);

CREATE INDEX evento_folio IF NOT EXISTS
  FOR (n:EventoISA95) ON (n.folio);

CREATE INDEX evento_timestamp IF NOT EXISTS
  FOR (n:EventoISA95) ON (n.timestamp);

CREATE INDEX evento_huerfano IF NOT EXISTS
  FOR (n:EventoISA95) ON (n.huerfano);
