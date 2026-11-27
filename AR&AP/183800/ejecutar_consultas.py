#!/usr/bin/env python3
"""
ejecutar_consultas.py                                       Matrícula 183800

Ejecuta cada consulta de consultas_arap.cypher en Neo4j y muestra el resultado
como tabla. Sirve para sacar las capturas de evidencia y para validar en el CI
que todas las consultas corren sin errores.

Uso
  python ejecutar_consultas.py                 # todas
  python ejecutar_consultas.py --solo Q3 Q5    # solo algunas

Termina con código 1 si alguna consulta falla.
Usa las mismas variables NEO4J_* que sync_postgres_neo4j.py.
"""
import argparse
import re
import sys
from pathlib import Path

import sync_postgres_neo4j as sync

RUTA_CONSULTAS = Path(__file__).resolve().parent / "consultas_arap.cypher"
CLAVES_VISIBLES = ("folio", "codigo", "eventId", "nombre", "id", "rfc")
ANCHO_MAXIMO = 60


def leer_consultas(ruta: Path = RUTA_CONSULTAS) -> list[tuple[str, str, str]]:
    """Devuelve [(Q1, titulo, cypher), ...] a partir de los bloques '// Qn. título'."""
    partes = re.split(r"^// (Q\d+)\. ", ruta.read_text(encoding="utf-8"), flags=re.MULTILINE)
    consultas = []
    for numero, cuerpo in zip(partes[1::2], partes[2::2]):
        lineas = cuerpo.splitlines()
        cypher = "\n".join(l for l in lineas[1:] if not l.strip().startswith("//")).strip()
        consultas.append((numero, lineas[0].strip(), cypher.rstrip(";").strip()))
    return consultas


def _etiqueta_corta(nodo) -> str:
    props = getattr(nodo, "properties", None) or dict(nodo)
    clave = next((props[k] for k in CLAVES_VISIBLES if k in props), "")
    return f"({':'.join(sorted(nodo.labels))} {clave})".replace("  ", " ")


def formatear(valor) -> str:
    if hasattr(valor, "labels"):  # nodo
        return _etiqueta_corta(valor)
    if hasattr(valor, "nodes"):   # camino
        nodos = valor.nodes() if callable(valor.nodes) else valor.nodes
        return " -> ".join(_etiqueta_corta(n) for n in nodos)
    if isinstance(valor, (list, tuple)):
        return "[" + ", ".join(formatear(v) for v in valor) + "]"
    if isinstance(valor, float):
        return f"{valor:.2f}".rstrip("0").rstrip(".")
    return str(valor)


def _cortar(texto: str) -> str:
    return texto if len(texto) <= ANCHO_MAXIMO else texto[:ANCHO_MAXIMO - 3] + "..."


def imprimir_tabla(columnas: list[str], filas: list[list[str]]) -> None:
    if not filas:
        print("   (sin filas)")
        return
    anchos = [max(len(c), *(len(f[i]) for f in filas)) for i, c in enumerate(columnas)]
    linea = lambda celdas: "   " + " | ".join(c.ljust(a) for c, a in zip(celdas, anchos))
    print(linea(columnas))
    print("   " + "-+-".join("-" * a for a in anchos))
    for f in filas:
        print(linea(f))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ejecuta el catálogo de consultas Cypher")
    ap.add_argument("--solo", nargs="*", help="números a ejecutar, por ejemplo Q3 Q5")
    args = ap.parse_args(argv)
    elegidas = {q.upper() for q in args.solo} if args.solo else None

    driver = sync.conectar_neo4j()
    driver.verify_connectivity()
    fallos = 0
    with driver.session() as sesion:
        for numero, titulo, cypher in leer_consultas():
            if elegidas and numero not in elegidas:
                continue
            print(f"\n{numero}. {titulo}")
            try:
                registros = [dict(r) for r in sesion.run(cypher)]
            except Exception as e:  # una consulta con error no detiene a las demás
                fallos += 1
                print(f"   ERROR: {str(e).splitlines()[0]}")
                continue
            columnas = list(registros[0].keys()) if registros else []
            imprimir_tabla(columnas, [[_cortar(formatear(r[c])) for c in columnas] for r in registros])
            print(f"   ({len(registros)} filas)")
    driver.close()
    print(f"\nConsultas con error: {fallos}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
