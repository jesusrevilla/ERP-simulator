import os
import time
from datetime import datetime, timezone
import psycopg2
from pymongo import MongoClient
from neo4j import GraphDatabase


def wait_for_services():
    """Espera a que PostgreSQL, MongoDB y Neo4j estén disponibles."""
    pg_params = dict(
        host=os.getenv("PG_HOST", "localhost"),
        port=int(os.getenv("PG_PORT", "5432")),
        dbname=os.getenv("PG_DB", "erp_leadtime"),
        user=os.getenv("PG_USER", "postgres"),
        password=os.getenv("PG_PASSWORD", "postgres"),
    )
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_pass = os.getenv("NEO4J_PASSWORD", "password123")

    for attempt in range(1, 21):
        try:
            conn = psycopg2.connect(**pg_params)
            conn.close()
            MongoClient(mongo_uri, serverSelectionTimeoutMS=2000).admin.command("ping")
            driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_pass))
            driver.verify_connectivity()
            driver.close()
            print(f"[OK] Todos los servicios listos en el intento {attempt}.")
            return pg_params, mongo_uri, (neo4j_uri, neo4j_user, neo4j_pass)
        except Exception as exc:
            print(f"[ESPERA {attempt}/20] Servicios iniciando... ({exc})")
            time.sleep(3)
    raise RuntimeError("No se pudo conectar a las bases de datos a tiempo.")


def setup_and_query_postgres(pg_params):
    """Crea tablas de historial de entregas en PostgreSQL y calcula desviaciones de Lead Time."""
    conn = psycopg2.connect(**pg_params)
    cur = conn.cursor()

    cur.execute("""
        DROP TABLE IF EXISTS historial_entregas_lt;
        CREATE TABLE historial_entregas_lt (
            id SERIAL PRIMARY KEY,
            proveedor VARCHAR(50),
            componente VARCHAR(50),
            lead_time_prometido INT,
            lead_time_real INT
        );
    """)

    datos = [
        ("Prov_Chips_A", "GPU_RTX", 5, 11),
        ("Prov_Chips_A", "GPU_RTX", 5, 10),
        ("Prov_Chips_B", "GPU_RTX", 6, 6),
        ("Prov_Placa_X", "Motherboard", 4, 5),
        ("Prov_Fuente_Z", "PSU_850W", 3, 7),
    ]
    cur.executemany(
        "INSERT INTO historial_entregas_lt (proveedor, componente, lead_time_prometido, lead_time_real) VALUES (%s, %s, %s, %s);",
        datos,
    )
    conn.commit()

    cur.execute("""
        SELECT
            proveedor,
            componente,
            ROUND(AVG(lead_time_prometido), 2) AS lt_prometido,
            ROUND(AVG(lead_time_real), 2) AS lt_real,
            ROUND(AVG(lead_time_real - lead_time_prometido), 2) AS desviacion_dias
        FROM historial_entregas_lt
        GROUP BY proveedor, componente
        ORDER BY desviacion_dias DESC;
    """)
    resultados = cur.fetchall()
    cur.close()
    conn.close()
    return resultados


def setup_and_query_neo4j(neo4j_cfg):
    """Carga el grafo de BOM/Proveedores en Neo4j y calcula la ruta crítica de Lead Time."""
    uri, user, password = neo4j_cfg
    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
        session.run("""
            CREATE (pc:Producto {nombre: 'PC_Gaming_Pro', lead_time_ensamble: 2})
            CREATE (gpu:Componente {nombre: 'GPU_RTX'})
            CREATE (mb:Componente {nombre: 'Motherboard'})
            CREATE (psu:Componente {nombre: 'PSU_850W'})
            CREATE (pa:Proveedor {nombre: 'Prov_Chips_A', confiabilidad: 0.65})
            CREATE (pb:Proveedor {nombre: 'Prov_Chips_B', confiabilidad: 0.96})
            CREATE (px:Proveedor {nombre: 'Prov_Placa_X', confiabilidad: 0.90})
            CREATE (pz:Proveedor {nombre: 'Prov_Fuente_Z', confiabilidad: 0.72})

            CREATE (pc)-[:REQUIERE]->(gpu)
            CREATE (pc)-[:REQUIERE]->(mb)
            CREATE (pc)-[:REQUIERE]->(psu)

            CREATE (pa)-[:SUMINISTRA {lead_time_dias: 10, es_principal: true}]->(gpu)
            CREATE (pb)-[:SUMINISTRA {lead_time_dias: 6, es_principal: false}]->(gpu)
            CREATE (px)-[:SUMINISTRA {lead_time_dias: 5, es_principal: true}]->(mb)
            CREATE (pz)-[:SUMINISTRA {lead_time_dias: 7, es_principal: true}]->(psu)
        """)

        # Consulta Cypher 1: Ruta crítica actual (proveedores principales)
        ruta_critica = session.run("""
            MATCH (p:Producto)-[:REQUIERE]->(c:Componente)<-[r:SUMINISTRA {es_principal: true}]-(prov:Proveedor)
            RETURN p.nombre AS producto,
                   c.nombre AS componente,
                   prov.nombre AS proveedor,
                   r.lead_time_dias AS lt_proveedor,
                   (r.lead_time_dias + p.lead_time_ensamble) AS lt_total_acumulado
            ORDER BY lt_total_acumulado DESC
            LIMIT 1
        """).single()

        # Consulta Cypher 2: Buscar proveedor alterno con menor Lead Time para el componente crítico
        alterno = session.run("""
            MATCH (c:Componente {nombre: $comp})<-[r:SUMINISTRA {es_principal: false}]-(alt:Proveedor)
            RETURN alt.nombre AS proveedor_alterno, r.lead_time_dias AS lt_alterno, alt.confiabilidad AS confiabilidad
            ORDER BY r.lead_time_dias ASC
            LIMIT 1
        """, comp=ruta_critica["componente"]).single()

    driver.close()
    return dict(ruta_critica), (dict(alterno) if alterno else None)


def evaluate_and_log_mongodb(mongo_uri, pg_stats, ruta_critica, alterno):
    """Aplica reglas de sistema experto y guarda las alertas y decisiones en MongoDB."""
    client = MongoClient(mongo_uri)
    db = client["erp_leadtime_db"]
    col = db["alertas_leadtime"]
    col.delete_many({})

    alertas = []
    for prov, comp, lt_prom, lt_real, desv in pg_stats:
        desv_f = float(desv)
        if desv_f >= 4.0:
            severidad = "CRITICO"
            accion = "ESCALAR_Y_CAMBIAR_PROVEEDOR"
        elif desv_f >= 2.0:
            severidad = "MEDIO"
            accion = "AUMENTAR_STOCK_SEGURIDAD"
        else:
            severidad = "BAJO"
            accion = "MANTENER_PLAN"

        doc = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "matricula_agente": "179091",
            "proveedor": prov,
            "componente": comp,
            "lead_time_prometido": float(lt_prom),
            "lead_time_real": float(lt_real),
            "desviacion_dias": desv_f,
            "severidad": severidad,
            "accion_recomendada": accion,
        }
        if comp == ruta_critica["componente"] and severidad == "CRITICO" and alterno:
            doc["proveedor_alterno_sugerido"] = alterno["proveedor_alterno"]
            doc["ahorro_estimado_dias"] = ruta_critica["lt_proveedor"] - alterno["lt_alterno"]

        alertas.append(doc)

    col.insert_many(alertas)
    criticas = list(col.find({"severidad": "CRITICO"}, {"_id": 0}))
    client.close()
    return alertas, criticas


def main():
    print("=== INICIANDO AGENTE DE RIESGO DE LEAD TIME (179091) ===")
    pg_params, mongo_uri, neo4j_cfg = wait_for_services()

    print("\n--- 1. Análisis Histórico en PostgreSQL ---")
    pg_stats = setup_and_query_postgres(pg_params)
    for row in pg_stats:
        print(f"Proveedor: {row[0]} | Comp: {row[1]} | Prometido: {row[2]}d | Real: {row[3]}d | Desviación: +{row[4]}d")

    print("\n--- 2. Ruta Crítica en Neo4j (Knowledge Graph) ---")
    ruta_critica, alterno = setup_and_query_neo4j(neo4j_cfg)
    print(f"Cuello de botella: {ruta_critica['componente']} ({ruta_critica['proveedor']}) -> LT Total: {ruta_critica['lt_total_acumulado']} días")
    if alterno:
        print(f"Proveedor alterno detectado: {alterno['proveedor_alterno']} (LT: {alterno['lt_alterno']} días, Confiabilidad: {alterno['confiabilidad']})")

    print("\n--- 3. Decisiones y Registro de Alertas en MongoDB ---")
    _, criticas = evaluate_and_log_mongodb(mongo_uri, pg_stats, ruta_critica, alterno)
    for alerta in criticas:
        print(f"[ALERTA {alerta['severidad']}] {alerta['componente']} ({alerta['proveedor']}): {alerta['accion_recomendada']}")
        if "proveedor_alterno_sugerido" in alerta:
            print(f"   -> Recomendación: Cambiar a {alerta['proveedor_alterno_sugerido']} (ahorro de {alerta['ahorro_estimado_dias']} días).")

    print("\n=== EJECUCIÓN FINALIZADA CON ÉXITO ===")


if __name__ == "__main__":
    main()
