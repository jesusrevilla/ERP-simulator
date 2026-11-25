"""
Pruebas automatizadas para el Agente Saga-ERP (Matrícula: 182217)
Valida los 4 escenarios definidos en el Plan de Trabajo (Issue #210).
"""

import os
from dotenv import load_dotenv
from agente_compensacion_182217 import AgenteCompensacionERP

load_dotenv()


def ejecutar_pruebas():
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    agente = AgenteCompensacionERP(uri, user, password)
    try:
        agente.limpiar_escenario_erp()
        agente.cargar_escenarios_prueba()

        # Prueba 1: Detección y resolución de Deadlock
        deadlocks = agente.detectar_y_resolver_deadlocks()
        assert len(deadlocks) == 1, "Se esperaba detectar exactamente 1 deadlock."
        assert deadlocks[0]["victima"] == "TX-1005", "La víctima del deadlock debe ser TX-1005."
        assert deadlocks[0]["liberada"] == "TX-1004", "La transacción liberada debe ser TX-1004."
        print("[PASS] Prueba 1: Deadlock detectado y resuelto correctamente.")

        # Prueba 2: Auditoría de Partida Doble
        descuadres = agente.auditar_partida_doble()
        assert len(descuadres) == 1, "Se esperaba detectar 1 póliza descuadrada."
        assert descuadres[0]["tx_id"] == "TX-1003", "La transacción descuadrada debe ser TX-1003."
        print("[PASS] Prueba 2: Descuadre de partida doble detectado y bloqueado.")

        # Prueba 3: Planeación y Compensación Saga
        compensadas = agente.ejecutar_compensacion_saga()
        assert len(compensadas) == 1, "Se esperaba compensar 1 transacción fallida."
        assert compensadas[0]["comp_id"] == "SAGA-TX-1002", "ID de compensación incorrecto."
        assert compensadas[0]["contra_poliza"] == "CPOL-TX-1002", "ID de contra-póliza incorrecto."
        print("[PASS] Prueba 3: Compensación Saga y contra-póliza ejecutadas.")

        # Prueba 4: Aprobación de transacción íntegra
        aprobadas = agente.aprobar_transacciones_integras()
        assert len(aprobadas) == 1, "Se esperaba aprobar exactamente 1 transacción sana."
        assert aprobadas[0]["tx_id"] == "TX-1001", "La transacción aprobada debe ser TX-1001."
        print("[PASS] Prueba 4: Transacción íntegra aprobada correctamente.")

        print("\n>>> TODAS LAS PRUEBAS (4/4) PASARON CON ÉXITO <<<")
    finally:
        agente.cerrar()


if __name__ == "__main__":
    ejecutar_pruebas()