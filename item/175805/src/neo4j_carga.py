"""Genera (y opcionalmente carga) el grafo del Item Master en Neo4j.

Uso (desde la carpeta item/175805):
    python src/neo4j_carga.py                # solo genera cypher/01_carga_grafo.cypher
    python src/neo4j_carga.py --cargar       # además ejecuta las sentencias en Neo4j

Variables de entorno para --cargar (el paquete 'neo4j' se instala con pip install neo4j):
    NEO4J_URI       (por defecto bolt://localhost:7687)
    NEO4J_USER      (por defecto neo4j)
    NEO4J_PASSWORD  (obligatoria)

Neo4j no admite mapas anidados como propiedad, por eso atributosTecnicos se guarda
aplanado: marca, modelo, capacidad y tipo.
"""
from __future__ import annotations

import argparse
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
RUTA_DATOS = os.path.join(BASE, "..", "datos", "items.json")
RUTA_CYPHER = os.path.join(BASE, "..", "cypher", "01_carga_grafo.cypher")

PROPIEDADES = (
    "Description", "ItemType", "UnitOfMeasure", "ListPrice", "StandardCost", "SafetyStock",
    "Category", "SubstituteGroup", "EsCritico", "StockDisponible", "DemandaAnual",
)


def literal(valor) -> str:
    """Convierte un valor de Python en un literal de Cypher."""
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, (int, float)):
        return str(valor)
    return json.dumps(str(valor), ensure_ascii=False)


def generar_sentencias(datos: dict) -> list:
    sentencias = ["CREATE CONSTRAINT item_code_unico IF NOT EXISTS FOR (i:Item) REQUIRE i.ItemCode IS UNIQUE"]
    for item in datos["items"]:
        props = {p: item[p] for p in PROPIEDADES}
        props.update(item.get("atributosTecnicos") or {})
        asignaciones = ", ".join(f"i.{k} = {literal(v)}" for k, v in props.items())
        sentencias.append(f"MERGE (i:Item {{ItemCode: {literal(item['ItemCode'])}}}) SET {asignaciones}")
    for componente, placa in datos["compatibilidad"]:
        sentencias.append(
            f"MATCH (a:Item {{ItemCode: {literal(componente)}}}), (b:Item {{ItemCode: {literal(placa)}}}) "
            f"MERGE (a)-[:COMPATIBLE_WITH]->(b)"
        )
    return sentencias


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera/carga el grafo en Neo4j")
    parser.add_argument("--cargar", action="store_true", help="Ejecutar las sentencias en Neo4j")
    args = parser.parse_args()

    with open(RUTA_DATOS, encoding="utf-8") as archivo:
        datos = json.load(archivo)
    sentencias = generar_sentencias(datos)

    os.makedirs(os.path.dirname(RUTA_CYPHER), exist_ok=True)
    with open(RUTA_CYPHER, "w", encoding="utf-8") as salida:
        salida.write("// Generado por src/neo4j_carga.py a partir de datos/items.json\n")
        salida.write(";\n".join(sentencias) + ";\n")
    print(f"{len(sentencias)} sentencias escritas en {os.path.normpath(RUTA_CYPHER)}")

    if args.cargar:
        from neo4j import GraphDatabase  # import tardío: solo se necesita para cargar

        uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        usuario = os.environ.get("NEO4J_USER", "neo4j")
        password = os.environ["NEO4J_PASSWORD"]
        with GraphDatabase.driver(uri, auth=(usuario, password)) as driver:
            with driver.session() as sesion:
                for sentencia in sentencias:
                    sesion.run(sentencia)
        print(f"Grafo cargado en {uri}")


if __name__ == "__main__":
    main()
