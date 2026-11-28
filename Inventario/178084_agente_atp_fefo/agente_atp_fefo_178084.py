"""
Agente Inteligente de Control de Disponibilidad (ATP) y Priorización FEFO
Matrícula: 178084 | Issue #306 (Inteligencia Artificial - Inventario)

Integración:
- PostgreSQL: lectura de vista vw_inventario_atp_178084 y lotes_inspeccion_178084
- Neo4j (Knowledge Graph): ranking de confiabilidad de proveedores por SKU (tasa de aprobación / RTV)
- MongoDB: registro trazable de alertas y decisiones en 'decisiones_agente_178084'
"""

from datetime import date, datetime, timezone
import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from neo4j import GraphDatabase
from pymongo import MongoClient

PROYECTO_TAG = "178084"


class InventoryFEFOAgent:
    """Sistema experto + planeación operativa sobre PostgreSQL, Neo4j y MongoDB."""

    def __init__(self, dias_alerta_fefo: int = 30, tasa_minima_proveedor: float = 80.0):
        self.dias_alerta_fefo = dias_alerta_fefo
        self.tasa_minima_proveedor = tasa_minima_proveedor

    @staticmethod
    def _get_postgres_conn():
        return psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            dbname=os.getenv("POSTGRES_DB", "erpdb"),
            user=os.getenv("POSTGRES_USER", "erp"),
            password=os.getenv("POSTGRES_PASSWORD", "erp"),
        )

    @staticmethod
    def _get_neo4j_driver():
        host = os.getenv("NEO4J_HOST", "localhost")
        port = os.getenv("NEO4J_PORT", "7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        return GraphDatabase.driver(f"bolt://{host}:{port}", auth=(user, password))

    @staticmethod
    def _get_mongo_client():
        host = os.getenv("MONGO_HOST", "localhost")
        port = int(os.getenv("MONGO_PORT", "27017"))
        client = MongoClient(f"mongodb://{host}:{port}/", serverSelectionTimeoutMS=5000)
        db = client[os.getenv("MONGO_DB", "erpdb")]
        return client, db

    # ------------------------------------------------------------------
    # 1. PERCEPCIÓN (LECTURA DE POSTGRESQL Y NEO4J)
    # ------------------------------------------------------------------
    def percibir_inventario_y_lotes(self):
        """Obtiene disponibilidad ATP y lotes activos desde PostgreSQL."""
        conn = self._get_postgres_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM vw_inventario_atp_178084 ORDER BY articulo_id")
                articulos = [dict(r) for r in cur.fetchall()]

                cur.execute(
                    """
                    SELECT
                        l.lote_id,
                        l.numero_lote,
                        l.articulo_id,
                        a.sku,
                        l.cantidad_recibida,
                        l.cantidad_aprobada,
                        l.fecha_caducidad,
                        l.estatus_lote
                    FROM lotes_inspeccion_178084 l
                    JOIN articulos_178084 a ON a.articulo_id = l.articulo_id
                    WHERE l.estatus_lote IN ('DISPONIBLE', 'CUARENTENA')
                    ORDER BY l.articulo_id, l.fecha_caducidad ASC
                    """
                )
                lotes = [dict(r) for r in cur.fetchall()]
            return articulos, lotes
        finally:
            conn.close()

    def consultar_proveedores_confiables_neo4j(self, sku: str):
        """Consulta el Knowledge Graph en Neo4j para rankear proveedores de un SKU."""
        query = """
        MATCH (p:Proveedor {proyecto: $tag})-[:SUMINISTRO]->(:Recepcion)-[:CONTIENE]->(l:Lote)-[:ES_ARTICULO]->(a:Articulo {sku: $sku})
        OPTIONAL MATCH (l)-[:DEVUELTO_EN]->(rtv:DevolucionRTV)
        WITH
            p,
            sum(l.cantidad_aprobada) AS aprobadas,
            sum(l.cantidad_rechazada) AS rechazadas,
            count(DISTINCT rtv) AS total_rtv
        WITH
            p, aprobadas, rechazadas, total_rtv,
            (aprobadas + rechazadas) AS evaluadas
        RETURN
            p.codigo AS codigo,
            p.nombre AS proveedor,
            aprobadas,
            rechazadas,
            total_rtv,
            CASE
                WHEN evaluadas = 0 THEN 100.0
                ELSE round((toFloat(aprobadas) / evaluadas) * 10000) / 100.0
            END AS tasa_aprobacion_pct
        ORDER BY tasa_aprobacion_pct DESC, total_rtv ASC, aprobadas DESC
        """
        driver = self._get_neo4j_driver()
        try:
            with driver.session() as session:
                result = session.run(query, tag=PROYECTO_TAG, sku=sku)
                return [dict(r) for r in result]
        finally:
            driver.close()

    # ------------------------------------------------------------------
    # 2. MOTOR DE REGLAS Y PLANEACIÓN (ATP + FEFO + PROVEEDOR)
    # ------------------------------------------------------------------
    def evaluar_atp(self, articulo: dict, proveedores_grafo: list):
        """Aplica reglas de Sistema Experto sobre el cálculo ATP y stock en cuarentena."""
        atp = articulo["atp"]
        stock_minimo = articulo["stock_minimo"]
        cuarentena = articulo["stock_cuarentena"]

        recomendacion_proveedor = None
        proveedores_riesgosos = [
            p for p in proveedores_grafo if p["tasa_aprobacion_pct"] < self.tasa_minima_proveedor
        ]
        if proveedores_grafo:
            recomendacion_proveedor = proveedores_grafo[0]

        if atp < 0:
            cantidad_sugerida = stock_minimo - atp
            return {
                "severidad": "CRITICO",
                "estado_atp": "QUIEBRE_BACKORDER",
                "atp": atp,
                "stock_cuarentena": cuarentena,
                "cantidad_reabastecer": cantidad_sugerida,
                "accion": (
                    f"Emitir orden de compra urgente por {cantidad_sugerida} unidades "
                    f"para cubrir backorder ({atp}) y recuperar stock mínimo ({stock_minimo})."
                ),
                "proveedor_recomendado": recomendacion_proveedor,
                "proveedores_con_advertencia": proveedores_riesgosos,
            }

        if atp < stock_minimo:
            deficit = stock_minimo - atp
            if (atp + cuarentena) >= stock_minimo:
                return {
                    "severidad": "ADVERTENCIA",
                    "estado_atp": "BAJO_MINIMO_CON_CUARENTENA",
                    "atp": atp,
                    "stock_cuarentena": cuarentena,
                    "cantidad_reabastecer": 0,
                    "accion": (
                        f"Escalar a Calidad: hay {cuarentena} unidades en CUARENTENA "
                        f"que cubren el déficit de {deficit} unidades sin comprar de inmediato."
                    ),
                    "proveedor_recomendado": recomendacion_proveedor,
                    "proveedores_con_advertencia": proveedores_riesgosos,
                }
            return {
                "severidad": "ADVERTENCIA",
                "estado_atp": "BAJO_MINIMO",
                "atp": atp,
                "stock_cuarentena": cuarentena,
                "cantidad_reabastecer": deficit,
                "accion": f"Programar reabastecimiento por {deficit} unidades.",
                "proveedor_recomendado": recomendacion_proveedor,
                "proveedores_con_advertencia": proveedores_riesgosos,
            }

        return {
            "severidad": "INFO",
            "estado_atp": "SALUDABLE",
            "atp": atp,
            "stock_cuarentena": cuarentena,
            "cantidad_reabastecer": 0,
            "accion": "Sin requerimiento de compra; disponibilidad ATP dentro de rango.",
            "proveedor_recomendado": None,
            "proveedores_con_advertencia": [],
        }

    def evaluar_fefo(self, lotes_articulo: list, fecha_referencia: date | None = None):
        """Ordena lotes disponibles bajo criterio FEFO y detecta vencidos o próximos a vencer."""
        hoy = fecha_referencia or date.today()
        orden_despacho_fefo = []
        alertas_caducidad = []

        lotes_disponibles = [l for l in lotes_articulo if l["estatus_lote"] == "DISPONIBLE"]
        lotes_disponibles.sort(key=lambda x: x["fecha_caducidad"])

        prioridad = 1
        for lote in lotes_disponibles:
            dias_restantes = (lote["fecha_caducidad"] - hoy).days

            if dias_restantes < 0:
                alertas_caducidad.append(
                    {
                        "severidad": "CRITICO",
                        "numero_lote": lote["numero_lote"],
                        "dias_restantes": dias_restantes,
                        "accion": "BLOQUEAR_LOTE_VENCIDO",
                        "detalle": (
                            f"Lote vencido hace {abs(dias_restantes)} días; "
                            "prohibir despacho y gestionar baja/devolución."
                        ),
                    }
                )
            elif dias_restantes <= self.dias_alerta_fefo:
                orden_despacho_fefo.append(
                    {
                        "prioridad_fefo": prioridad,
                        "numero_lote": lote["numero_lote"],
                        "fecha_caducidad": lote["fecha_caducidad"].isoformat(),
                        "dias_restantes": dias_restantes,
                        "estado": "PROXIMO_A_VENCER",
                    }
                )
                alertas_caducidad.append(
                    {
                        "severidad": "ADVERTENCIA",
                        "numero_lote": lote["numero_lote"],
                        "dias_restantes": dias_restantes,
                        "accion": "PRIORIZAR_DESPACHO_FEFO",
                        "detalle": (
                            f"Lote caduca en {dias_restantes} días "
                            f"(<= {self.dias_alerta_fefo}); asignar como prioridad #{prioridad}."
                        ),
                    }
                )
                prioridad += 1
            else:
                orden_despacho_fefo.append(
                    {
                        "prioridad_fefo": prioridad,
                        "numero_lote": lote["numero_lote"],
                        "fecha_caducidad": lote["fecha_caducidad"].isoformat(),
                        "dias_restantes": dias_restantes,
                        "estado": "VIGENTE",
                    }
                )
                prioridad += 1

        return orden_despacho_fefo, alertas_caducidad

    # ------------------------------------------------------------------
    # 3. EJECUCIÓN COMPLETA Y PERSISTENCIA EN MONGODB
    # ------------------------------------------------------------------
    def registrar_reporte_mongodb(self, reporte: dict):
        """Persiste el resultado completo del agente en MongoDB."""
        client, db = self._get_mongo_client()
        try:
            col = db["decisiones_agente_178084"]
            doc = dict(reporte)
            res = col.insert_one(doc)
            return str(res.inserted_id)
        finally:
            client.close()

    def ejecutar(self, guardar_en_mongo: bool = True):
        """Ejecuta el ciclo completo Percepción -> Razonamiento -> Acción -> Bitácora."""
        articulos, lotes = self.percibir_inventario_y_lotes()
        lotes_por_sku = {}
        for lote in lotes:
            lotes_por_sku.setdefault(lote["sku"], []).append(lote)

        evaluaciones = []
        resumen_alertas = {"CRITICO": 0, "ADVERTENCIA": 0, "INFO": 0}

        for art in articulos:
            sku = art["sku"]
            proveedores = self.consultar_proveedores_confiables_neo4j(sku)
            decision_atp = self.evaluar_atp(art, proveedores)
            plan_fefo, alertas_fefo = self.evaluar_fefo(lotes_por_sku.get(sku, []))

            resumen_alertas[decision_atp["severidad"]] += 1
            for alerta in alertas_fefo:
                resumen_alertas[alerta["severidad"]] += 1

            evaluaciones.append(
                {
                    "sku": sku,
                    "articulo": art["nombre"],
                    "metricas_stock": {
                        "disponible": art["stock_disponible"],
                        "cuarentena": art["stock_cuarentena"],
                        "comprometido": art["stock_comprometido"],
                        "atp": art["atp"],
                        "minimo": art["stock_minimo"],
                    },
                    "decision_atp": decision_atp,
                    "plan_despacho_fefo": plan_fefo,
                    "alertas_fefo": alertas_fefo,
                }
            )

        reporte = {
            "agente": "InventoryFEFOAgent",
            "proyecto": PROYECTO_TAG,
            "fecha_ejecucion": datetime.now(timezone.utc).isoformat(),
            "parametros": {
                "dias_alerta_fefo": self.dias_alerta_fefo,
                "tasa_minima_proveedor": self.tasa_minima_proveedor,
            },
            "resumen_alertas": resumen_alertas,
            "evaluaciones": evaluaciones,
        }

        if guardar_en_mongo:
            reporte["mongo_document_id"] = self.registrar_reporte_mongodb(reporte)

        return reporte


if __name__ == "__main__":
    agente = InventoryFEFOAgent(dias_alerta_fefo=30, tasa_minima_proveedor=80.0)
    resultado = agente.ejecutar(guardar_en_mongo=True)
    print("=== [178084] Reporte de Decisiones: InventoryFEFOAgent ===")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))