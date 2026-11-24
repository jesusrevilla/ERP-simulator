"""Pruebas del agente SKU Sentinel & Data Steward (matrícula 175805).

Se ejecutan sin base de datos:  pytest item/175805/pruebas
"""
import copy
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "src"))

from fase1_deduplicacion import (  # noqa: E402
    clasificar_categoria,
    clave_estructural,
    evaluar_alta,
    similitud_descripcion,
)
from fase2_validacion import ac3, validar_atributos_csp, validar_integridad  # noqa: E402
from fase3_sustitutos import (  # noqa: E402
    bfs_sustituto,
    construir_grafo,
    greedy_sustituto,
    segmentacion_abc,
)

with open(os.path.join(RAIZ, "datos", "items.json"), encoding="utf-8") as f:
    DATOS = json.load(f)

CATALOGO = DATOS["items"]
POR_CODIGO = {i["ItemCode"]: i for i in CATALOGO}
GRAFO = construir_grafo(CATALOGO, DATOS["compatibilidad"])
ALTAS = {a["ItemCode"]: a for a in DATOS["altas_prueba"]}


# ---------------- Fase 1 ----------------
def test_duplicado_estructural_se_bloquea_y_sugiere_sku_existente():
    r = evaluar_alta(ALTAS["RAM-KINGSTON-FURY-16G"], CATALOGO)
    assert r.decision == "BLOQUEADO"
    assert r.sku_existente == "RAM-KF-16-D5"


def test_clave_estructural_ignora_mayusculas_y_espacios():
    a = ALTAS["RAM-KINGSTON-FURY-16G"]
    assert clave_estructural(a) == clave_estructural(POR_CODIGO["RAM-KF-16-D5"])


def test_itemcode_repetido_se_bloquea():
    r = evaluar_alta(copy.deepcopy(POR_CODIGO["CPU-R7-7700X"]), CATALOGO)
    assert r.decision == "BLOQUEADO"
    assert r.sku_existente == "CPU-R7-7700X"


def test_articulo_nuevo_distinto_se_aprueba_en_fase1():
    assert evaluar_alta(ALTAS["RAM-KF-64-D5"], CATALOGO).decision == "APROBADO"


def test_similitud_del_ejemplo_del_documento():
    s = similitud_descripcion("Memoria Kingston Fury 16 GB DDR5", "RAM DDR5 16GB Kingston Fury")
    assert s == 1.0


def test_clasificacion_por_descripcion():
    assert clasificar_categoria("SSD Samsung 990 NVMe 2 TB") == "SSD"
    assert clasificar_categoria("Memoria Corsair 32 GB DDR5") == "RAM"
    assert clasificar_categoria("Tarjeta madre MSI B650") == "Motherboard"
    assert clasificar_categoria("Tarjeta de video MSI RTX 4070") == "GPU"
    assert clasificar_categoria("Silla de oficina") is None


# ---------------- Fase 2 ----------------
def test_catalogo_vigente_cumple_las_reglas():
    for item in CATALOGO:
        assert validar_integridad(item) == [], item["ItemCode"]


def test_precio_menor_al_costo_unidad_invalida_y_safety_stock_cero():
    errores = validar_integridad(ALTAS["SSD-KNV2-4TB"])
    texto = " | ".join(errores)
    assert "ListPrice" in texto
    assert "UnitOfMeasure" in texto
    assert "SafetyStock" in texto


def test_csp_detecta_combinacion_invalida():
    errores = validar_integridad(ALTAS["RAM-KV-64-D4"])
    assert any("AC-3" in e for e in errores)


def test_csp_acepta_combinacion_valida():
    assert validar_integridad(ALTAS["RAM-KF-64-D5"]) == []


def test_ac3_infiere_dominio_cuando_falta_capacidad():
    item = copy.deepcopy(POR_CODIGO["RAM-KV-16-D4"])
    item["atributosTecnicos"]["capacidad"] = None
    errores, dominios = validar_atributos_csp(item)
    assert errores == []
    assert "64GB" not in dominios["capacidad"]      # DDR4 con 64GB no es posible
    assert dominios["capacidad"] == {"8GB", "16GB", "32GB"}


def test_consistencia_de_nodo_valor_fuera_de_dominio():
    item = copy.deepcopy(POR_CODIGO["RAM-KV-16-D4"])
    item["atributosTecnicos"]["tipo"] = "DDR3"
    errores, _ = validar_atributos_csp(item)
    assert errores and "fuera del dominio" in errores[0]


def test_ac3_devuelve_false_si_un_dominio_queda_vacio():
    dominios = {"x": {1}, "y": {1}}
    arcos = {("x", "y"): lambda a, b: a != b, ("y", "x"): lambda a, b: a != b}
    assert ac3(dominios, arcos) is False


# ---------------- Fase 3 ----------------
def test_bfs_encuentra_sustituto_nvme_compatible():
    r = bfs_sustituto(GRAFO, POR_CODIGO, "SSD-SAM980-1TB")
    assert r is not None
    assert r.codigo == "SSD-WD770-1TB"
    assert r.saltos == 2


def test_greedy_coincide_con_bfs_en_este_grafo():
    r = greedy_sustituto(GRAFO, POR_CODIGO, "SSD-SAM980-1TB")
    assert r is not None and r.codigo == "SSD-WD770-1TB"


def test_sustituto_de_ram_ddr5_no_es_ddr4():
    for buscar in (bfs_sustituto, greedy_sustituto):
        r = buscar(GRAFO, POR_CODIGO, "RAM-KF-16-D5")
        assert r is not None
        assert r.codigo == "RAM-CV-16-D5"
        assert POR_CODIGO[r.codigo]["atributosTecnicos"]["tipo"] == "DDR5"


def test_sin_sustituto_devuelve_none():
    catalogo = copy.deepcopy(CATALOGO)
    for i in catalogo:
        if i["Category"] == "SSD" and i["ItemCode"] != "SSD-SAM980-1TB":
            i["StockDisponible"] = 0
    por_codigo = {i["ItemCode"]: i for i in catalogo}
    grafo = construir_grafo(catalogo, DATOS["compatibilidad"])
    assert bfs_sustituto(grafo, por_codigo, "SSD-SAM980-1TB") is None
    assert greedy_sustituto(grafo, por_codigo, "SSD-SAM980-1TB") is None


def test_abc_clasifica_todo_y_el_mayor_valor_es_a():
    clases = segmentacion_abc(CATALOGO)
    assert set(clases) == set(POR_CODIGO)
    assert set(clases.values()) <= {"A", "B", "C"}
    assert clases["CPU-R7-7700X"] == "A"            # mayor valor de consumo anual
    assert clases["MB-B550-GIGA"] == "C"
