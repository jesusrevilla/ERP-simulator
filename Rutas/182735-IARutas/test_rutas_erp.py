import unittest
from datetime import date

from rutas_erp import (
    Etapa,
    Inventario,
    Linea,
    ReglaDeRutaError,
    Ruta,
    auditar_costos,
    borrar_etapa,
    cambiar_almacen,
    crear_orden,
    emitir_para_produccion,
    finalizar_orden,
    insertar_etapa,
    liberar_orden,
    lineas_huerfanas,
    lineas_para_despacho,
    programar_fechas,
    validar_secuencia,
)

COSTOS = {
    "Motherboard_B650": 180,
    "CPU_Ryzen7": 320,
    "RAM_16GB_DDR5": 45,
    "SSD_1TB_NVMe": 80,
    "PowerSupply_750W": 90,
    "GraphicsCard_RTX": 450,
}
ETAPA_1 = ["Motherboard_B650", "CPU_Ryzen7", "RAM_16GB_DDR5", "SSD_1TB_NVMe"]


def ruta_gaming_pc():
    return Ruta("RUTA-GAMING-PC", [
        Etapa(1, "Etapa_1_Base", {m: 1 for m in ETAPA_1}, 90),
        Etapa(2, "Etapa_2_Energia", {"PowerSupply_750W": 1}, 60),
        Etapa(3, "Etapa_3_Graficos", {"GraphicsCard_RTX": 1}, 60),
    ])


def nueva_orden(fecha_fin=date(2026, 11, 20)):
    return crear_orden(ruta_gaming_pc(), "OP-001", "Gaming_PC", 2, "ALM-01",
                       date(2026, 11, 10), fecha_fin, COSTOS)


def inventario():
    existencias = {(m, "ALM-01"): 10 for m in COSTOS}
    existencias[("PowerSupply_750W", "ALM-02")] = 5
    return Inventario(existencias)


def despachar_etapa(orden, inv, secuencia):
    for linea in lineas_para_despacho(orden, secuencia):
        emitir_para_produccion(orden, inv, secuencia, linea.material, linea.planificada)


class TestSecuencia(unittest.TestCase):
    def test_correlativa_es_valida(self):
        validar_secuencia(ruta_gaming_pc().etapas)

    def test_con_huecos_se_rechaza(self):
        etapas = [Etapa(1, "A", {}, 10), Etapa(3, "B", {}, 10)]
        with self.assertRaises(ReglaDeRutaError):
            validar_secuencia(etapas)

    def test_no_entera_se_rechaza(self):
        for valor in (1.5, "2"):
            with self.assertRaises(ReglaDeRutaError):
                validar_secuencia([Etapa(1, "A", {}, 10), Etapa(valor, "B", {}, 10)])

    def test_orden_con_secuencia_invalida_no_se_crea(self):
        ruta = Ruta("R", [Etapa(1, "A", {"X": 1}, 10), Etapa(3, "B", {"X": 1}, 10)])
        with self.assertRaises(ReglaDeRutaError):
            crear_orden(ruta, "OP", "P", 1, "ALM-01", date(2026, 11, 10), date(2026, 11, 20), {"X": 1})


class TestMaestroRuta(unittest.TestCase):
    def test_guardado_del_maestro_de_etapas(self):
        ruta = Ruta("R")
        etapa = Etapa(1, "Etapa_1_Base", {"CPU_Ryzen7": 1}, 90)
        ruta.agregar_etapa(etapa)
        self.assertIs(ruta.buscar_etapa(1), etapa)
        with self.assertRaises(ReglaDeRutaError):
            ruta.agregar_etapa(Etapa(1, "Duplicada", {}, 10))

    def test_total_run_time_se_actualiza(self):
        ruta = ruta_gaming_pc()
        self.assertEqual(ruta.total_run_time, 210)
        ruta.buscar_etapa(1).run_time_min = 120
        self.assertEqual(ruta.total_run_time, 240)
        ruta.agregar_etapa(Etapa(4, "Etapa_4_Pruebas", {}, 30))
        self.assertEqual(ruta.total_run_time, 270)

    def test_reenumeracion_al_insertar_una_secuencia(self):
        ruta = ruta_gaming_pc()
        insertar_etapa(ruta, Etapa(2, "Etapa_Prueba", {}, 30))
        self.assertEqual([e.secuencia for e in ruta.etapas], [1, 2, 3, 4])
        self.assertEqual([e.codigo for e in ruta.etapas],
                         ["Etapa_1_Base", "Etapa_Prueba", "Etapa_2_Energia", "Etapa_3_Graficos"])
        validar_secuencia(ruta.etapas)

    def test_insertar_fuera_de_rango_se_rechaza(self):
        with self.assertRaises(ReglaDeRutaError):
            insertar_etapa(ruta_gaming_pc(), Etapa(9, "X", {}, 10))


class TestFechas(unittest.TestCase):
    def test_run_time_y_dias_de_espera(self):
        etapas = [Etapa(1, "A", {}, 600, dias_espera=2), Etapa(2, "B", {}, 60)]
        fechas = programar_fechas(date(2026, 11, 10), etapas)
        self.assertEqual(fechas[0], (date(2026, 11, 10), date(2026, 11, 11)))
        self.assertEqual(fechas[1], (date(2026, 11, 14), date(2026, 11, 14)))

    def test_fechas_dentro_del_horizonte(self):
        orden = nueva_orden()
        self.assertEqual(orden.etapas[-1].fecha_fin, date(2026, 11, 12))
        self.assertTrue(all(orden.fecha_inicio <= e.fecha_inicio and e.fecha_fin <= orden.fecha_fin
                            for e in orden.etapas))

    def test_fechas_fuera_del_horizonte_se_rechazan(self):
        with self.assertRaises(ReglaDeRutaError):
            nueva_orden(fecha_fin=date(2026, 11, 11))


class TestDespacho(unittest.TestCase):
    def setUp(self):
        self.orden = nueva_orden()
        liberar_orden(self.orden)
        self.inv = inventario()

    def test_orden_con_tres_etapas_liberada(self):
        self.assertEqual(len(self.orden.etapas), 3)
        self.assertEqual(self.orden.estatus, "LIBERADA")
        self.assertEqual(len(self.orden.lineas), 6)

    def test_filtro_de_la_etapa_1(self):
        materiales = {l.material for l in lineas_para_despacho(self.orden, 1)}
        self.assertEqual(materiales, set(ETAPA_1))

    def test_descuento_correcto_del_inventario(self):
        despachar_etapa(self.orden, self.inv, 1)
        for material in ETAPA_1:
            self.assertEqual(self.inv.cantidad(material, "ALM-01"), 8)
        self.assertEqual(self.inv.cantidad("PowerSupply_750W", "ALM-01"), 10)

    def test_orden_no_liberada_no_despacha(self):
        orden = nueva_orden()
        with self.assertRaises(ReglaDeRutaError):
            emitir_para_produccion(orden, self.inv, 1, "CPU_Ryzen7", 1)

    def test_bloqueo_hasta_completar_el_despacho_previo(self):
        with self.assertRaises(ReglaDeRutaError):
            emitir_para_produccion(self.orden, self.inv, 2, "PowerSupply_750W", 2)
        despachar_etapa(self.orden, self.inv, 1)
        emitir_para_produccion(self.orden, self.inv, 2, "PowerSupply_750W", 2)
        self.assertEqual(self.inv.cantidad("PowerSupply_750W", "ALM-01"), 8)

    def test_no_se_despacha_mas_de_lo_planificado(self):
        with self.assertRaises(ReglaDeRutaError):
            emitir_para_produccion(self.orden, self.inv, 1, "CPU_Ryzen7", 3)

    def test_existencia_insuficiente(self):
        inv = Inventario({(m, "ALM-01"): 1 for m in COSTOS})
        with self.assertRaises(ReglaDeRutaError):
            emitir_para_produccion(self.orden, inv, 1, "CPU_Ryzen7", 2)

    def test_cambio_de_almacen_despues_de_la_etapa_1(self):
        with self.assertRaises(ReglaDeRutaError):
            cambiar_almacen(self.orden, 2, "ALM-02")
        despachar_etapa(self.orden, self.inv, 1)
        cambiar_almacen(self.orden, 2, "ALM-02")
        emitir_para_produccion(self.orden, self.inv, 2, "PowerSupply_750W", 2)
        self.assertEqual(self.inv.cantidad("PowerSupply_750W", "ALM-02"), 3)
        self.assertEqual(self.inv.cantidad("PowerSupply_750W", "ALM-01"), 10)

    def test_la_etapa_1_no_cambia_de_almacen(self):
        with self.assertRaises(ReglaDeRutaError):
            cambiar_almacen(self.orden, 1, "ALM-02")

    def test_auditoria_de_costos_al_finalizar(self):
        for secuencia in (1, 2, 3):
            despachar_etapa(self.orden, self.inv, secuencia)
        resultado = finalizar_orden(self.orden)
        self.assertEqual(resultado, {"planificado": 2330, "real": 2330, "diferencia": 0})
        self.assertEqual(self.orden.estatus, "CERRADA")

    def test_no_se_finaliza_con_despachos_pendientes(self):
        despachar_etapa(self.orden, self.inv, 1)
        with self.assertRaises(ReglaDeRutaError):
            finalizar_orden(self.orden)
        self.assertEqual(auditar_costos(self.orden)["real"], 1250)


class TestIntegridad(unittest.TestCase):
    def test_lineas_huerfanas(self):
        orden = nueva_orden()
        self.assertEqual(lineas_huerfanas(orden), [])
        orden.lineas += [Linea(None, "CPU_Ryzen7", 1, 320), Linea(9, "CPU_Ryzen7", 1, 320)]
        self.assertEqual(len(lineas_huerfanas(orden)), 2)

    def test_no_se_borra_etapa_con_movimientos_en_orden_liberada(self):
        orden = nueva_orden()
        liberar_orden(orden)
        despachar_etapa(orden, inventario(), 1)
        with self.assertRaises(ReglaDeRutaError):
            borrar_etapa(orden, 1)
        self.assertEqual(len(orden.etapas), 3)

    def test_se_borra_etapa_sin_movimientos(self):
        orden = nueva_orden()
        liberar_orden(orden)
        borrar_etapa(orden, 3)
        self.assertEqual([e.secuencia for e in orden.etapas], [1, 2])
        self.assertEqual(lineas_huerfanas(orden), [])
        self.assertEqual(len(orden.lineas), 5)

    def test_borrar_etapa_inexistente(self):
        with self.assertRaises(ReglaDeRutaError):
            borrar_etapa(nueva_orden(), 7)

    def test_la_orden_conserva_su_ruta_original(self):
        ruta = ruta_gaming_pc()
        orden = crear_orden(ruta, "OP-002", "Gaming_PC", 1, "ALM-01",
                            date(2026, 11, 10), date(2026, 11, 20), COSTOS)
        ruta.buscar_etapa(1).run_time_min = 999
        ruta.agregar_etapa(Etapa(4, "Etapa_4_Pruebas", {}, 30))
        self.assertEqual(orden.ruta.total_run_time, 210)
        self.assertEqual(len(orden.ruta.etapas), 3)


if __name__ == "__main__":
    unittest.main()
