"""SKU Sentinel & Data Steward - demostración de las tres fases.

Uso (desde la carpeta item/175805):
    python src/main.py
    python src/main.py --datos datos/items.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fase1_deduplicacion import evaluar_alta  # noqa: E402
from fase2_validacion import validar_integridad  # noqa: E402
from fase3_sustitutos import (  # noqa: E402
    bfs_sustituto,
    construir_grafo,
    greedy_sustituto,
    segmentacion_abc,
)

RUTA_DATOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "datos", "items.json")


def titulo(texto: str) -> None:
    print("\n" + "=" * 78)
    print(texto)
    print("=" * 78)


def procesar_alta(nuevo: dict, catalogo: list) -> str:
    """Fase 1 y luego Fase 2. Devuelve la decisión final."""
    print(f"\n> Alta solicitada: {nuevo['ItemCode']} - {nuevo['Description']}")
    fase1 = evaluar_alta(nuevo, catalogo)
    print(f"  Fase 1 (deduplicación): {fase1.decision}")
    for motivo in fase1.motivos:
        print(f"    - {motivo}")
    for aviso in fase1.advertencias:
        print(f"    * Aviso: {aviso}")
    if fase1.decision == "BLOQUEADO":
        print(f"  DECISIÓN FINAL: BLOQUEADO. Usar el SKU existente {fase1.sku_existente}")
        return "BLOQUEADO"

    errores = validar_integridad(nuevo)
    if errores:
        print(f"  Fase 2 (integridad): RECHAZADO ({len(errores)} violación(es))")
        for e in errores:
            print(f"    - {e}")
        print("  DECISIÓN FINAL: RECHAZADO")
        return "RECHAZADO"
    print("  Fase 2 (integridad): CORRECTO")
    print("  DECISIÓN FINAL: APROBADO")
    return "APROBADO"


def main() -> None:
    parser = argparse.ArgumentParser(description="SKU Sentinel & Data Steward")
    parser.add_argument("--datos", default=RUTA_DATOS, help="Ruta del archivo items.json")
    args = parser.parse_args()

    with open(args.datos, encoding="utf-8") as archivo:
        datos = json.load(archivo)
    catalogo = datos["items"]
    por_codigo = {i["ItemCode"]: i for i in catalogo}

    titulo("FASE 1 y 2 - Altas de prueba (deduplicación + validación de integridad)")
    for alta in datos["altas_prueba"]:
        procesar_alta(alta, catalogo)

    titulo("FASE 2 - Auditoría del catálogo vigente")
    con_errores = {i["ItemCode"]: validar_integridad(i) for i in catalogo}
    con_errores = {k: v for k, v in con_errores.items() if v}
    if con_errores:
        for codigo, errores in con_errores.items():
            print(f"{codigo}: {errores}")
    else:
        print(f"Los {len(catalogo)} artículos del catálogo cumplen las reglas de integridad.")

    titulo("FASE 3 - Sustitutos para artículos críticos sin existencias")
    grafo = construir_grafo(catalogo, datos["compatibilidad"])
    agotados = [i for i in catalogo if i["EsCritico"] and i["StockDisponible"] <= 0]
    for item in agotados:
        print(f"\n> {item['ItemCode']} ({item['Description']}) sin existencias")
        for buscar in (bfs_sustituto, greedy_sustituto):
            r = buscar(grafo, por_codigo, item["ItemCode"])
            if r:
                sust = por_codigo[r.codigo]
                print(
                    f"  {r.algoritmo:<6} -> {r.codigo} ({sust['Description']}), "
                    f"existencias {sust['StockDisponible']}, {r.saltos} saltos, "
                    f"{r.nodos_explorados} nodos explorados"
                )
            else:
                print(f"  {buscar.__name__}: sin sustituto compatible con existencias -> escalar incidencia")

    titulo("FASE 3 - Segmentación ABC (DemandaAnual x StandardCost)")
    clases = segmentacion_abc(catalogo)
    for clase in ("A", "B", "C"):
        codigos = [c for c, k in clases.items() if k == clase]
        print(f"Clase {clase} ({len(codigos)}): {', '.join(codigos)}")


if __name__ == "__main__":
    main()
