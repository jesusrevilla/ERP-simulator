"""Integración PostgreSQL -> Neo4j y Consultas Analíticas para Agentes ERP.

Conecta las tablas normalizadas de PostgreSQL (compras, recibos, inventario, entregas)
con el Knowledge Graph de Neo4j y expone consultas parametrizadas utilizadas por los
agentes inteligentes del módulo (trazabilidad, pedidos/picking y despacho).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List


SQL_INVENTARIOS_CRITICOS = """
SELECT p.codigo_sku,
       p.nombre AS producto,
       a.codigo AS almacen,
       i.stock_actual,
       i.stock_reservado,
       (i.stock_actual - i.stock_reservado) AS stock_disponible,
       p.stock_minimo
FROM inventario_stock i
JOIN productos p ON p.id = i.producto_id
JOIN almacenes a ON a.id = i.almacen_id
WHERE p.activo = TRUE
  AND (i.stock_actual - i.stock_reservado) <= p.stock_minimo
ORDER BY (p.stock_minimo - (i.stock_actual - i.stock_reservado)) DESC
"""

SQL_CUMPLIMIENTO_PROVEEDORES = """
SELECT pr.codigo_proveedor,
       pr.nombre,
       pr.estatus,
       COALESCE(SUM(ocd.cantidad_solicitada), 0) AS solicitado,
       COALESCE(SUM(ocd.cantidad_recibida), 0) AS recibido
FROM proveedores pr
LEFT JOIN ordenes_compra oc ON oc.proveedor_id = pr.id
LEFT JOIN ordenes_compra_detalle ocd ON ocd.orden_compra_id = oc.id
GROUP BY pr.codigo_proveedor, pr.nombre, pr.estatus
"""

SQL_EXTRACT_MOVIMIENTOS = """
SELECT m.codigo_movimiento,
       p.codigo_sku,
       p.nombre AS producto,
       a.codigo AS codigo_almacen,
       m.tipo_movimiento,
       m.documento_tipo,
       m.cantidad,
       m.signo,
       m.stock_anterior,
       m.stock_posterior,
       m.fecha_movimiento
FROM movimientos_inventario m
JOIN productos p ON p.id = m.producto_id
JOIN almacenes a ON a.id = m.almacen_id
ORDER BY m.id ASC
"""

CYPHER_SYNC_MOVIMIENTO = """
UNWIND $rows AS row
MERGE (a:Almacen {codigo_almacen: row.codigo_almacen})
MERGE (pr:Producto {codigo_sku: row.codigo_sku})
SET pr.nombre = row.producto
MERGE (m:MovimientoInventario {codigo_movimiento: row.codigo_movimiento})
SET m.tipo_movimiento = row.tipo_movimiento,
    m.documento_tipo = row.documento_tipo,
    m.cantidad = toFloat(row.cantidad),
    m.signo = toInteger(row.signo),
    m.stock_anterior = toFloat(row.stock_anterior),
    m.stock_posterior = toFloat(row.stock_posterior),
    m.fecha_movimiento = row.fecha_movimiento
MERGE (m)-[:AFECTA_PRODUCTO]->(pr)
MERGE (m)-[:EN_ALMACEN]->(a)
RETURN count(m) AS movimientos_sincronizados
"""

CYPHER_TRAZABILIDAD_PRODUCTO = """
MATCH (pr:Producto {codigo_sku: $codigo_sku})
OPTIONAL MATCH (oc:OrdenCompra)-[sol:SOLICITA]->(pr)
OPTIONAL MATCH (oc)-[:EMITIDA_A]->(prov:Proveedor)
OPTIONAL MATCH (r:ReciboMercancia)-[rec:RECIBE]->(pr)
OPTIONAL MATCH (e:EntregaMercancia)-[ent:ENTREGA]->(pr)
RETURN pr.codigo_sku AS sku,
       collect(DISTINCT prov.codigo_proveedor) AS proveedores,
       collect(DISTINCT oc.codigo_oc) AS ordenes_compra,
       collect(DISTINCT r.codigo_recibo) AS recibos,
       collect(DISTINCT e.codigo_entrega) AS entregas
"""

CYPHER_PROVEEDORES_CONFIABLES = """
MATCH (oc:OrdenCompra)-[:EMITIDA_A]->(p:Proveedor)
MATCH (oc)-[sol:SOLICITA]->(:Producto)
WITH p,
     sum(sol.cantidad_solicitada) AS total_solicitado,
     sum(coalesce(sol.cantidad_recibida, 0.0)) AS total_recibido
RETURN p.codigo_proveedor AS codigo_proveedor,
       p.nombre AS nombre,
       p.estatus AS estatus,
       total_solicitado,
       total_recibido,
       CASE
           WHEN total_solicitado = 0 THEN 0.0
           ELSE round((total_recibido / total_solicitado) * 10000) / 100
       END AS porcentaje_cumplimiento
ORDER BY porcentaje_cumplimiento DESC
"""


class IntegracionPGNeo4j:
    """Puente de datos entre PostgreSQL y Neo4j para los agentes inteligentes del ERP."""

    def __init__(self, pg_conn: Any, neo4j_driver: Any, database: str = "neo4j") -> None:
        self.pg_conn = pg_conn
        self.neo4j_driver = neo4j_driver
        self.database = database

    @classmethod
    def from_env(cls) -> "IntegracionPGNeo4j":
        import psycopg2
        from neo4j import GraphDatabase

        pg_conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            database=os.getenv("POSTGRES_DB", "erpdb"),
            user=os.getenv("POSTGRES_USER", "erp"),
            password=os.getenv("POSTGRES_PASSWORD", "erp"),
        )
        uri = os.getenv("NEO4J_URI") or (
            f"bolt://{os.getenv('NEO4J_HOST', 'localhost')}:{os.getenv('NEO4J_PORT', '7687')}"
        )
        driver = GraphDatabase.driver(
            uri,
            auth=(
                os.getenv("NEO4J_USER", os.getenv("NEO4J_USERNAME", "neo4j")),
                os.getenv("NEO4J_PASSWORD", "password"),
            ),
        )
        driver.verify_connectivity()
        return cls(pg_conn, driver, database=os.getenv("NEO4J_DATABASE", "neo4j"))

    def obtener_inventarios_criticos(self) -> List[Dict[str, Any]]:
        """Consulta SQL utilizada por el agente de compras para disparar reabastecimiento."""
        cur = self.pg_conn.cursor()
        try:
            cur.execute(SQL_INVENTARIOS_CRITICOS)
            rows = cur.fetchall()
            return [
                {
                    "codigo_sku": r[0],
                    "producto": r[1],
                    "almacen": r[2],
                    "stock_actual": float(r[3]),
                    "stock_reservado": float(r[4]),
                    "stock_disponible": float(r[5]),
                    "stock_minimo": float(r[6]),
                }
                for r in rows
            ]
        finally:
            cur.close()

    def sincronizar_movimientos_a_neo4j(self) -> int:
        """Extrae el kardex de PostgreSQL y lo sincroniza al grafo Neo4j."""
        cur = self.pg_conn.cursor()
        try:
            cur.execute(SQL_EXTRACT_MOVIMIENTOS)
            rows = [
                {
                    "codigo_movimiento": r[0],
                    "codigo_sku": r[1],
                    "producto": r[2],
                    "codigo_almacen": r[3],
                    "tipo_movimiento": r[4],
                    "documento_tipo": r[5],
                    "cantidad": float(r[6]),
                    "signo": int(r[7]),
                    "stock_anterior": float(r[8]),
                    "stock_posterior": float(r[9]),
                    "fecha_movimiento": r[10].isoformat() if hasattr(r[10], "isoformat") else str(r[10]),
                }
                for r in cur.fetchall()
            ]
        finally:
            cur.close()

        if not rows:
            return 0

        records, _, _ = self.neo4j_driver.execute_query(
            CYPHER_SYNC_MOVIMIENTO,
            database_=self.database,
            rows=rows,
        )
        return records[0].data()["movimientos_sincronizados"] if records else 0

    def consultar_trazabilidad_grafo(self, codigo_sku: str) -> Dict[str, Any]:
        """Consulta Cypher para agentes de trazabilidad y auditoría end-to-end."""
        records, _, _ = self.neo4j_driver.execute_query(
            CYPHER_TRAZABILIDAD_PRODUCTO,
            database_=self.database,
            codigo_sku=codigo_sku.strip().upper(),
        )
        return records[0].data() if records else {
            "sku": codigo_sku.strip().upper(),
            "proveedores": [],
            "ordenes_compra": [],
            "recibos": [],
            "entregas": [],
        }

    def consultar_proveedores_confiables(self) -> List[Dict[str, Any]]:
        """Ranking de cumplimiento de proveedores en el Knowledge Graph."""
        records, _, _ = self.neo4j_driver.execute_query(
            CYPHER_PROVEEDORES_CONFIABLES,
            database_=self.database,
        )
        return [r.data() for r in records]
