import os
from neo4j import GraphDatabase

# 1. CONFIGURACIÓN DE CREDENCIALES (Neo4j AuraDB)
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://TU_INSTANCIA.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "TU_PASSWORD_AQUI")
DATABASE_NAME = "neo4j"


# 2. OPERACIONES CRUD SOBRE EL GRAFO (Usando driver.execute_query)
def reset_database(driver) -> None:
    """Elimina todos los nodos y relaciones existentes antes de iniciar."""
    driver.execute_query(
        "MATCH (n) DETACH DELETE n",
        database_=DATABASE_NAME,
    )
    print("[Paso 1] Base de datos reiniciada correctamente.")


def build_initial_graph(driver) -> None:
    """Crea los nodos (Estudiante, Proyecto, Tecnologia) y sus relaciones."""
    cypher_create = """
    // Nodos de Estudiantes
    CREATE (e1:Estudiante {nombre: "Ana Sofía", matricula: "A012345", semestre: 6})
    CREATE (e2:Estudiante {nombre: "Carlos Méndez", matricula: "A012346", semestre: 6})
    CREATE (e3:Estudiante {nombre: "Lucía Torres", matricula: "A012347", semestre: 7})

    // Nodos de Proyectos
    CREATE (p1:Proyecto {titulo: "Sistema de Recomendación", estado: "En desarrollo", anio: 2026})
    CREATE (p2:Proyecto {titulo: "Monitor de Red IoT", estado: "En desarrollo", anio: 2026})

    // Nodos de Tecnologías
    CREATE (t1:Tecnologia {nombre: "Python", tipo: "Lenguaje"})
    CREATE (t2:Tecnologia {nombre: "Neo4j", tipo: "Base de Datos de Grafos"})
    CREATE (t3:Tecnologia {nombre: "FastAPI", tipo: "Framework Web"})

    // Relaciones entre Estudiantes y Proyectos
    CREATE (e1)-[:DESARROLLA {rol: "Líder Técnico"}]->(p1)
    CREATE (e2)-[:DESARROLLA {rol: "Backend Developer"}]->(p1)
    CREATE (e3)-[:DESARROLLA {rol: "Arquitecta de Datos"}]->(p2)
    CREATE (e1)-[:COLABORA_CON {desde: 2025}]->(e2)

    // Relaciones entre Proyectos y Tecnologías
    CREATE (p1)-[:USA]->(t1)
    CREATE (p1)-[:USA]->(t2)
    CREATE (p2)-[:USA]->(t1)
    CREATE (p2)-[:USA]->(t3)

    // Nodo temporal para demostrar eliminación controlada
    CREATE (tmp:NotaTemporal {descripcion: "Registro de prueba"})
    CREATE (e1)-[:TIENE_NOTA]->(tmp)
    """
    result = driver.execute_query(cypher_create, database_=DATABASE_NAME)
    counters = result.summary.counters
    print(
        f"[Paso 2] Grafo creado -> {counters.nodes_created} nodos y "
        f"{counters.relationships_created} relaciones insertadas."
    )


def fetch_projects_by_year(driver, year: int) -> None:
    """Consulta proyectos filtrando por año y agrupa sus tecnologías."""
    cypher_match = """
    MATCH (e:Estudiante)-[r:DESARROLLA]->(p:Proyecto)-[:USA]->(t:Tecnologia)
    WHERE p.anio = $year
    RETURN e.nombre AS estudiante,
           r.rol AS rol,
           p.titulo AS proyecto,
           collect(t.nombre) AS tecnologias
    ORDER BY proyecto ASC
    """
    records, _, _ = driver.execute_query(
        cypher_match,
        year=year,
        database_=DATABASE_NAME,
    )

    print(f"\n[Paso 3] Proyectos activos en {year}:")
    for row in records:
        stack = ", ".join(row["tecnologias"])
        print(
            f"  * {row['estudiante']} ({row['rol']}) -> "
            f"{row['proyecto']} | Stack: [{stack}]"
        )


def update_project_status(driver, project_title: str, status: str, score: int) -> None:
    """Modifica el estado y asigna calificación a un proyecto mediante SET."""
    cypher_set = """
    MATCH (p:Proyecto {titulo: $title})
    SET p.estado = $status,
        p.calificacion = $score
    RETURN p.titulo AS titulo, p.estado AS estado, p.calificacion AS calificacion
    """
    records, _, _ = driver.execute_query(
        cypher_set,
        title=project_title,
        status=status,
        score=score,
        database_=DATABASE_NAME,
    )

    print("\n[Paso 4] Proyecto actualizado con SET:")
    for row in records:
        print(
            f"  * '{row['titulo']}' -> Estado: {row['estado']} | "
            f"Calificación: {row['calificacion']}"
        )


def remove_temp_records(driver) -> None:
    """Elimina los nodos marcados como NotaTemporal junto con sus relaciones."""
    cypher_delete = """
    MATCH (n:NotaTemporal)
    DETACH DELETE n
    """
    result = driver.execute_query(cypher_delete, database_=DATABASE_NAME)
    counters = result.summary.counters
    print(
        f"\n[Paso 5] Nodo temporal eliminado -> {counters.nodes_deleted} nodo(s) y "
        f"{counters.relationships_deleted} relación(es) borradas."
    )


def main() -> None:
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        driver.verify_connectivity()
        print("=== Conexión establecida con Neo4j AuraDB (Versión 1) ===\n")

        reset_database(driver)
        build_initial_graph(driver)
        fetch_projects_by_year(driver, year=2026)
        update_project_status(
            driver,
            project_title="Sistema de Recomendación",
            status="Completado",
            score=98,
        )
        remove_temp_records(driver)

        print(
            "\nEjecución finalizada. Para ver el grafo en Neo4j Workspace ejecuta:\n"
            "  MATCH (n)-[r]->(m) RETURN n, r, m;"
        )


if __name__ == "__main__":
    main()