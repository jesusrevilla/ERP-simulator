"""
Agente Inteligente de Compensación Transaccional y Detección de Deadlocks (Saga-ERP)
Matrícula: 182217 | Módulo: Integridad_de_las_transacciones
"""

import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()


class AgenteCompensacionERP:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.driver.verify_connectivity()

    def cerrar(self):
        self.driver.close()

    def limpiar_escenario_erp(self):
        """Elimina únicamente los nodos del escenario ERP (no toca otros grafos)."""
        query = """
        MATCH (n)
        WHERE n:OrdenVenta OR n:Transaccion OR n:MovimientoInventario
           OR n:CuentaPorCobrar OR n:PolizaContable OR n:Compensacion OR n:AlertaIntegridad
        DETACH DELETE n
        """
        with self.driver.session() as session:
            session.run(query)

    def cargar_escenarios_prueba(self):
        """Carga 4 escenarios ERP en el Knowledge Graph de Neo4j."""
        query = """
        // Escenario 1: Transacción íntegra (sana)
        CREATE (o1:OrdenVenta {id: 'OV-101', cliente: 'Aceros Potosí', total: 1500.0})
        CREATE (t1:Transaccion {id: 'TX-1001', estado: 'COMPLETADA', modulo: 'VENTAS'})
        CREATE (i1:MovimientoInventario {id: 'INV-101', producto: 'Valvula-Industrial', cantidad: -10, estado: 'APLICADO'})
        CREATE (c1:CuentaPorCobrar {id: 'CXC-101', monto: 1500.0, estado: 'ACTIVA'})
        CREATE (p1:PolizaContable {id: 'POL-101', tipo: 'NORMAL', cargos: 1500.0, abonos: 1500.0, estado: 'CUADRADA'})
        CREATE (o1)-[:GENERA]->(t1)
        CREATE (t1)-[:AFECTA_INVENTARIO]->(i1)
        CREATE (t1)-[:GENERA_CXC]->(c1)
        CREATE (t1)-[:REGISTRA_POLIZA]->(p1)

        // Escenario 2: Transacción fallida a mitad del flujo (requiere compensación Saga)
        CREATE (o2:OrdenVenta {id: 'OV-102', cliente: 'Manufacturas SLP', total: 4200.0})
        CREATE (t2:Transaccion {id: 'TX-1002', estado: 'FALLIDA', modulo: 'VENTAS', error: 'Timeout en pasarela bancaria'})
        CREATE (i2:MovimientoInventario {id: 'INV-102', producto: 'Sensor-Presion', cantidad: -5, estado: 'APLICADO'})
        CREATE (c2:CuentaPorCobrar {id: 'CXC-102', monto: 4200.0, estado: 'ACTIVA'})
        CREATE (p2:PolizaContable {id: 'POL-102', tipo: 'NORMAL', cargos: 4200.0, abonos: 4200.0, estado: 'PENDIENTE'})
        CREATE (o2)-[:GENERA]->(t2)
        CREATE (t2)-[:AFECTA_INVENTARIO]->(i2)
        CREATE (t2)-[:GENERA_CXC]->(c2)
        CREATE (t2)-[:REGISTRA_POLIZA]->(p2)

        // Escenario 3: Descuadre contable (incumple partida doble: cargos != abonos)
        CREATE (o3:OrdenVenta {id: 'OV-103', cliente: 'Logística Bajío', total: 2500.0})
        CREATE (t3:Transaccion {id: 'TX-1003', estado: 'COMPLETADA', modulo: 'CONTABILIDAD'})
        CREATE (p3:PolizaContable {id: 'POL-103', tipo: 'NORMAL', cargos: 2500.0, abonos: 2000.0, estado: 'PENDIENTE'})
        CREATE (o3)-[:GENERA]->(t3)
        CREATE (t3)-[:REGISTRA_POLIZA]->(p3)

        // Escenario 4: Ciclo de bloqueo mutuo (Deadlock concurrente)
        CREATE (t4:Transaccion {id: 'TX-1004', estado: 'EN_PROCESO', modulo: 'INVENTARIO'})
        CREATE (t5:Transaccion {id: 'TX-1005', estado: 'EN_PROCESO', modulo: 'INVENTARIO'})
        CREATE (t4)-[:BLOQUEA {recurso: 'STOCK-SKU-99'}]->(t5)
        CREATE (t5)-[:BLOQUEA {recurso: 'CUENTA-CLI-42'}]->(t4)
        """
        with self.driver.session() as session:
            session.run(query)

    # --- REGLA 1: DETECCIÓN Y RESOLUCIÓN DE DEADLOCKS ---
    def detectar_y_resolver_deadlocks(self):
        print("\n[REGLA 1] Buscando ciclos de bloqueo (Deadlocks)...")
        query_detectar = """
        MATCH p = (t:Transaccion)-[:BLOQUEA*2..5]->(t)
        RETURN [n IN nodes(p) | n.id] AS ciclo
        """
        query_resolver = """
        MATCH (v:Transaccion {id: $victima})-[r:BLOQUEA]->(obj:Transaccion)
        DELETE r
        SET v.estado = 'ABORTADA_DEADLOCK'
        MERGE (a:AlertaIntegridad {id: $alerta_id})
        SET a.tipo = 'DEADLOCK_CONCURRENTE',
            a.severidad = 'CRITICA',
            a.detalle = $detalle,
            a.fecha = datetime()
        MERGE (v)-[:GENERA_ALERTA]->(a)
        RETURN v.id AS victima, obj.id AS liberada, a.id AS alerta
        """
        vistos = set()
        resueltos = []

        with self.driver.session() as session:
            for record in session.run(query_detectar):
                ciclo = record["ciclo"]
                nodos_unicos = frozenset(ciclo)
                if nodos_unicos in vistos:
                    continue
                vistos.add(nodos_unicos)

                # Política del sistema experto: abortar la transacción con ID más reciente
                victima = max(nodos_unicos)
                alerta_id = f"ALERT-DL-{victima}"
                detalle = f"Ciclo detectado {' -> '.join(ciclo)}. Se aborta {victima} para liberar recursos."

                res = session.run(
                    query_resolver,
                    victima=victima,
                    alerta_id=alerta_id,
                    detalle=detalle,
                ).single()
                if res:
                    resueltos.append(res.data())
                    print(f"  -> DEADLOCK DETECTADO: {' -> '.join(ciclo)}")
                    print(f"     DECISIÓN: Abortada {res['victima']} | Liberada {res['liberada']} | Alerta {res['alerta']}")

        if not resueltos:
            print("  -> Sin deadlocks activos.")
        return resueltos

    # --- REGLA 2: AUDITORÍA DE PARTIDA DOBLE ---
    def auditar_partida_doble(self):
        print("\n[REGLA 2] Auditando principio de Partida Doble (Cargos == Abonos)...")
        query_auditar = """
        MATCH (t:Transaccion)-[:REGISTRA_POLIZA]->(p:PolizaContable)
        WHERE abs(p.cargos - p.abonos) > 0.01
        RETURN t.id AS tx_id, p.id AS poliza_id, p.cargos AS cargos, p.abonos AS abonos
        """
        query_alertar = """
        MATCH (t:Transaccion {id: $tx_id})-[:REGISTRA_POLIZA]->(p:PolizaContable {id: $poliza_id})
        SET t.estado = 'BLOQUEADA_AUDITORIA',
            p.estado = 'DESCUADRADA'
        MERGE (a:AlertaIntegridad {id: $alerta_id})
        SET a.tipo = 'DESCUADRE_PARTIDA_DOBLE',
            a.severidad = 'ALTA',
            a.detalle = $detalle,
            a.fecha = datetime()
        MERGE (t)-[:GENERA_ALERTA]->(a)
        RETURN t.id AS tx_id, a.id AS alerta
        """
        inconsistencias = []

        with self.driver.session() as session:
            for record in session.run(query_auditar):
                diff = round(record["cargos"] - record["abonos"], 2)
                alerta_id = f"ALERT-PD-{record['tx_id']}"
                detalle = (
                    f"Póliza {record['poliza_id']} descuadrada: "
                    f"Cargos={record['cargos']} vs Abonos={record['abonos']} (Dif={diff})"
                )
                res = session.run(
                    query_alertar,
                    tx_id=record["tx_id"],
                    poliza_id=record["poliza_id"],
                    alerta_id=alerta_id,
                    detalle=detalle,
                ).single()
                inconsistencias.append(res.data())
                print(f"  -> DESCUADRE EN {record['tx_id']} ({record['poliza_id']}): Diferencia de ${diff}")
                print(f"     DECISIÓN: Transacción bloqueada y escalada a Finanzas | Alerta {res['alerta']}")

        if not inconsistencias:
            print("  -> Todas las pólizas cumplen la partida doble.")
        return inconsistencias

    # --- REGLA 3: PLANEACIÓN Y COMPENSACIÓN (PATRÓN SAGA) ---
    def ejecutar_compensacion_saga(self):
        print("\n[REGLA 3] Evaluando transacciones fallidas para planeación Saga...")
        query_fallidas = """
        MATCH (t:Transaccion {estado: 'FALLIDA'})
        OPTIONAL MATCH (t)-[:AFECTA_INVENTARIO]->(inv:MovimientoInventario)
        OPTIONAL MATCH (t)-[:GENERA_CXC]->(cxc:CuentaPorCobrar)
        OPTIONAL MATCH (t)-[:REGISTRA_POLIZA]->(pol:PolizaContable)
        RETURN t.id AS tx_id, inv.id AS inv_id, inv.producto AS producto,
               inv.cantidad AS cantidad, cxc.id AS cxc_id, cxc.monto AS monto, pol.id AS pol_id
        """
        query_compensar = """
        MATCH (t:Transaccion {id: $tx_id})
        SET t.estado = 'COMPENSADA_SAGA'
        CREATE (comp:Compensacion {
            id: $comp_id,
            patron: 'SAGA',
            plan_ejecutado: $plan,
            fecha: datetime()
        })
        CREATE (comp)-[:COMPENSA]->(t)
        WITH t, comp
        OPTIONAL MATCH (t)-[:AFECTA_INVENTARIO]->(inv:MovimientoInventario)
        SET inv.estado = 'REINTEGRADO'
        WITH t, comp
        OPTIONAL MATCH (t)-[:GENERA_CXC]->(cxc:CuentaPorCobrar)
        SET cxc.estado = 'CANCELADA'
        WITH t, comp
        CREATE (cp:PolizaContable {
            id: $contra_poliza_id,
            tipo: 'CONTRA_POLIZA',
            cargos: $monto,
            abonos: $monto,
            estado: 'CUADRADA'
        })
        CREATE (comp)-[:EMITE_CONTRA_POLIZA]->(cp)
        RETURN t.id AS tx_id, comp.id AS comp_id, cp.id AS contra_poliza
        """
        compensadas = []

        with self.driver.session() as session:
            for rec in session.run(query_fallidas):
                plan = [
                    f"1. Reintegrar {abs(rec['cantidad'] or 0)} unidades de {rec['producto']} ({rec['inv_id']})",
                    f"2. Cancelar Cuenta por Cobrar {rec['cxc_id']} por ${rec['monto']}",
                    f"3. Emitir contra-póliza cuadrada de reversión para {rec['pol_id']}",
                ]
                res = session.run(
                    query_compensar,
                    tx_id=rec["tx_id"],
                    comp_id=f"SAGA-{rec['tx_id']}",
                    plan=" | ".join(plan),
                    contra_poliza_id=f"CPOL-{rec['tx_id']}",
                    monto=rec["monto"] or 0.0,
                ).single()
                compensadas.append(res.data())
                print(f"  -> FALLA EN {rec['tx_id']} — Plan Saga ejecutado:")
                for paso in plan:
                    print(f"     {paso}")
                print(f"     DECISIÓN: Compensación {res['comp_id']} y contra-póliza {res['contra_poliza']} registradas.")

        if not compensadas:
            print("  -> Sin transacciones fallidas pendientes.")
        return compensadas

    # --- REGLA 4: APROBACIÓN DE TRANSACCIONES ÍNTEGRAS ---
    def aprobar_transacciones_integras(self):
        print("\n[REGLA 4] Validando transacciones íntegras para aprobación final...")
        query = """
        MATCH (t:Transaccion {estado: 'COMPLETADA'})-[:REGISTRA_POLIZA]->(p:PolizaContable)
        WHERE abs(p.cargos - p.abonos) <= 0.01
          AND NOT (t)-[:BLOQUEA]->()
          AND NOT (t)-[:GENERA_ALERTA]->()
        SET t.estado = 'APROBADA_INTEGRA'
        RETURN t.id AS tx_id, p.id AS poliza_id, p.cargos AS monto
        """
        aprobadas = []
        with self.driver.session() as session:
            for rec in session.run(query):
                aprobadas.append(rec.data())
                print(f"  -> {rec['tx_id']} APROBADA (Póliza {rec['poliza_id']} cuadrada por ${rec['monto']}).")
        return aprobadas

    def ejecutar_ciclo_completo(self):
        print("=" * 65)
        print("  AGENTE SAGA-ERP (182217) - INTEGRIDAD DE LAS TRANSACCIONES")
        print("=" * 65)
        self.limpiar_escenario_erp()
        self.cargar_escenarios_prueba()
        print("Escenarios ERP cargados correctamente en Neo4j AuraDB.")

        self.detectar_y_resolver_deadlocks()
        self.auditar_partida_doble()
        self.ejecutar_compensacion_saga()
        self.aprobar_transacciones_integras()
        print("\nCiclo de inferencia y compensación finalizado con éxito.")


def main():
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    if not all([uri, user, password]):
        raise ValueError("Faltan variables en el archivo .env (NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD).")

    agente = AgenteCompensacionERP(uri, user, password)
    try:
        agente.ejecutar_ciclo_completo()
    finally:
        agente.cerrar()


if __name__ == "__main__":
    main()