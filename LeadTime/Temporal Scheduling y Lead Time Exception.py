from datetime import datetime, timedelta
from typing import Dict, List, Optional


class MRPLeadTimeSchedulingAgent:
    """
    Agente de Planificación Temporal y Gestión de Excepciones de Lead Time (CPM + CSP).
    Cumple con RF-01 a RF-07 y RN-01 a RN-09 (173030_ERP_Lead_Time.pdf).
    """

    def __init__(self, inventario_actual: Dict[str, int], tiempo_interno_horas: float = 7.5):
        """
        :param inventario_actual: {codigo_material: stock_disponible}
        :param tiempo_interno_horas: Duración estándar de ensamble, pruebas y empaque (ej. 7.5h)
        """
        self.inventario = inventario_actual
        self.tiempo_interno_horas = tiempo_interno_horas
        self.ordenes_compra: Dict[str, dict] = {}
        self.ordenes_produccion: Dict[str, dict] = {}

    @staticmethod
    def _horas_entre(inicio: str, fin: str) -> float:
        t0 = datetime.fromisoformat(inicio)
        t1 = datetime.fromisoformat(fin)
        if t1 < t0:
            raise ValueError(f"Error RN-03 / PU-03: Fecha final ({fin}) anterior a fecha inicial ({inicio}).")
        return round((t1 - t0).total_seconds() / 3600.0, 3)

    def registrar_orden_compra(
        self,
        oc_id: str,
        codigo_material: str,
        cantidad: int,
        fecha_emision: str,
        lead_time_estimado_horas: float
    ) -> dict:
        """Crea una orden de compra de material faltante (RF-02, RF-03, RN-01)."""
        if oc_id in self.ordenes_compra:
            raise ValueError(f"Error RN-01 / PU-06: La orden '{oc_id}' ya existe.")

        t_inicio = datetime.fromisoformat(fecha_emision)
        t_estimada = t_inicio + timedelta(hours=lead_time_estimado_horas)

        orden = {
            "oc_id": oc_id,
            "codigo_material": codigo_material,
            "cantidad": cantidad,
            "fecha_emision": fecha_emision,
            "fecha_estimada_disponibilidad": t_estimada.isoformat(),
            "lead_time_estimado_horas": lead_time_estimado_horas,
            "fecha_recepcion_almacen": None,
            "fecha_liberacion_calidad": None,
            "fecha_real_disponibilidad": None,
            "estado": "EN_TRANSITO",
            "lead_time_real_horas": None,
            "desviacion_horas": None
        }
        self.ordenes_compra[oc_id] = orden
        return orden

    def procesar_recepcion_y_calidad(
        self,
        oc_id: str,
        fecha_recepcion: str,
        fecha_aprobacion_calidad: Optional[str] = None,
        fecha_disponible_inventario: Optional[str] = None
    ) -> dict:
        """
        Aplica RN-02 y RN-04 (PU-05): La recepción física no implica disponibilidad
        hasta que calidad apruebe y libere el material.
        """
        orden = self.ordenes_compra[oc_id]
        self._horas_entre(orden["fecha_emision"], fecha_recepcion)
        orden["fecha_recepcion_almacen"] = fecha_recepcion

        if not fecha_aprobacion_calidad or not fecha_disponible_inventario:
            orden["estado"] = "EN_REVISION"  # PU-05: No marcar disponible ni calcular LT definitivo
            return orden

        self._horas_entre(fecha_recepcion, fecha_aprobacion_calidad)
        self._horas_entre(fecha_aprobacion_calidad, fecha_disponible_inventario)

        lt_real = self._horas_entre(orden["fecha_emision"], fecha_disponible_inventario)
        desviacion = round(lt_real - orden["lead_time_estimado_horas"], 3)

        orden.update({
            "fecha_liberacion_calidad": fecha_aprobacion_calidad,
            "fecha_real_disponibilidad": fecha_disponible_inventario,
            "estado": "DISPONIBLE",
            "lead_time_real_horas": lt_real,
            "desviacion_horas": desviacion
        })
        # Actualiza inventario disponible para producción
        mat = orden["codigo_material"]
        self.inventario[mat] = self.inventario.get(mat, 0) + orden["cantidad"]
        return orden

    def auditar_ordenes_abiertas_csp(self, timestamp_actual: str) -> List[dict]:
        """
        Evaluación CSP de restricciones temporales (RN-05, RN-06, PU-04, PF-03).
        Identifica órdenes abiertas vencidas sin asignar lead time real definitivo.
        """
        t_now = datetime.fromisoformat(timestamp_actual)
        alertas = []

        for oc in self.ordenes_compra.values():
            if oc["estado"] not in {"DISPONIBLE", "CANCELADA"}:
                t_est = datetime.fromisoformat(oc["fecha_estimada_disponibilidad"])
                transcurrido = self._horas_entre(oc["fecha_emision"], timestamp_actual)
                if t_now > t_est:
                    oc["estado"] = "RETRASADO"
                    alertas.append({
                        "oc_id": oc["oc_id"],
                        "material": oc["codigo_material"],
                        "estado": "RETRASADO",
                        "tiempo_transcurrido_horas": transcurrido,
                        "retraso_actual_horas": round((t_now - t_est).total_seconds() / 3600.0, 3)
                    })
        return alertas

    def planificar_orden_produccion_cpm(
        self,
        op_id: str,
        requerimientos_mrp: Dict[str, int],
        fecha_creacion_pedido: str,
        fecha_entrega_comprometida: Optional[str] = None
    ) -> dict:
        """
        Algoritmo CPM + Backward/Forward Scheduling (RN-08, PF-06).
        Calcula la ruta crítica de abastecimiento y determina cuándo puede iniciar producción.
        """
        faltantes = {}
        ruta_critica_inicio_prod = datetime.fromisoformat(fecha_creacion_pedido)
        material_cuello_botella = None

        # 1. Verificar disponibilidad y calcular fecha más temprana de inicio (Early Start)
        for mat, req in requerimientos_mrp.items():
            stock = self.inventario.get(mat, 0)
            if stock < req:
                deficit = req - stock
                faltantes[mat] = deficit

                # Buscar OC abierta o programada para cubrir el faltante
                ocs_mat = [o for o in self.ordenes_compra.values()
                           if o["codigo_material"] == mat and o["estado"] != "CANCELADA"]
                if not ocs_mat:
                    return {
                        "op_id": op_id,
                        "estado": "BLOQUEADA_POR_FALTANTES",
                        "mensaje": f"Restricción RN-08: Faltan {deficit} de '{mat}' y no existe OC activa.",
                        "faltantes": faltantes
                    }

                # Tomar la fecha estimada o real de liberación de la OC
                oc = ocs_mat[0]
                fecha_disp_str = oc["fecha_real_disponibilidad"] or oc["fecha_estimada_disponibilidad"]
                fecha_disp = datetime.fromisoformat(fecha_disp_str)

                if fecha_disp > ruta_critica_inicio_prod:
                    ruta_critica_inicio_prod = fecha_disp
                    material_cuello_botella = mat

        # 2. Calcular fin de producción interna y Lead Time Total de la Orden
        fin_produccion_estimado = ruta_critica_inicio_prod + timedelta(hours=self.tiempo_interno_horas)
        lt_total_orden_horas = self._horas_entre(fecha_creacion_pedido, fin_produccion_estimado.isoformat())

        # 3. Evaluación Backward Scheduling si hay fecha compromiso del cliente
        holgura_horas = None
        if fecha_entrega_comprometida:
            t_comp = datetime.fromisoformat(fecha_entrega_comprometida)
            holgura_horas = round((t_comp - fin_produccion_estimado).total_seconds() / 3600.0, 3)

        resultado = {
            "op_id": op_id,
            "estado": "LISTA_PARA_PRODUCCION" if not faltantes else "EN_ESPERA_DE_MATERIAL_CRITICO",
            "faltantes_detectados": faltantes,
            "material_cuello_botella": material_cuello_botella,
            "inicio_mas_temprano_ensamble": ruta_critica_inicio_prod.isoformat(),
            "fin_estimado_producto_terminado": fin_produccion_estimado.isoformat(),
            "lead_time_interno_horas": self.tiempo_interno_horas,
            "lead_time_total_orden_horas": lt_total_orden_horas,
            "holgura_vs_compromiso_horas": holgura_horas
        }
        self.ordenes_produccion[op_id] = resultado
        return resultado


# ==========================================
# EJEMPLO DE EJECUCIÓN (Caso TechAssembly 30 Gaming PC)
# ==========================================
if __name__ == "__main__":
    stock_inicial = {
        "CPU001": 50, "MB001": 45, "RAM001": 200,
        "SSD001": 75, "PSU001": 40, "GPU001": 20  # Faltan 10 para 30 PCs
    }
    agente_lt = MRPLeadTimeSchedulingAgent(stock_inicial, tiempo_interno_horas=7.5)

    # 1. Emitir OC por las 10 GPU faltantes (09:00 del 10-Nov, estimado 48h)
    agente_lt.registrar_orden_compra(
        oc_id="OC-GPU-101",
        codigo_material="GPU001",
        cantidad=10,
        fecha_emision="2026-11-10T09:00:00",
        lead_time_estimado_horas=48.0
    )

    # 2. Planificar orden de 30 Gaming PC creada a las 08:00 del 10-Nov
    requerimientos_30_pc = {"CPU001": 30, "MB001": 30, "RAM001": 60, "SSD001": 30, "PSU001": 30, "GPU001": 30}
    print("--- PLANIFICACIÓN INICIAL (CON FALTANTE) ---")
    print(agente_lt.planificar_orden_produccion_cpm("OP-30-PC", requerimientos_30_pc, "2026-11-10T08:00:00"))

    # 3. Recepción y aprobación de calidad el 12-Nov a las 10:30 (Lead Time real = 49.5h -> +1.5h desviación)
    print("\n--- RECEPCIÓN Y LIBERACIÓN DE CALIDAD ---")
    print(agente_lt.procesar_recepcion_y_calidad(
        oc_id="OC-GPU-101",
        fecha_recepcion="2026-11-12T09:00:00",
        fecha_aprobacion_calidad="2026-11-12T10:00:00",
        fecha_disponible_inventario="2026-11-12T10:30:00"
    ))