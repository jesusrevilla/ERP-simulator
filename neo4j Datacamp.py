import os
from typing import Any
from neo4j import GraphDatabase

# CONFIGURACIÓN DE CONEXIÓN
DB_CONFIG = {
    "uri": os.getenv("NEO4J_URI", "neo4j+s://TU_INSTANCIA.databases.neo4j.io"),
    "user": os.getenv("NEO4J_USER", "neo4j"),
    "password": os.getenv("NEO4J_PASSWORD", "TU_PASSWORD_AQUI"),
    "database": "neo4j",
}


class Neo4jGraphService:
    """Encapsula la conexión y las transacciones CRUD contra Neo4j."""

    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database

    def verify(self) -> None:
        self.driver.verify_connectivity()

    def close(self) -> None:
        self.driver.close()

    def limpiar_todo(self) -> None:
        with self.driver.session(database=self.database) as session:
            session.execute_write(self._tx_borrar_todo)
        print("[1/5] Grafo anterior eliminado correctamente.")

    def poblar_datos_iniciales(self) -> dict[str, int]:
        estudiantes = [
            {"nombre": "Ana Sofía", "matricula": "A012345", "semestre": 6},
            {"nombre": "Carlos Méndez", "matricula": "A012346", "semestre": 6},
            {"nombre": "Lucía Torres", "matricula": "A012347", "semestre": 7},
        ]
        proyectos = [
            {"titulo": "Sistema de Recomendación", "estado": "En desarrollo", "anio": 2026},
            {"titulo": "Monitor de Red IoT", "estado": "En desarrollo", "anio": 2026},
        ]
        tecnologias = [
            {"nombre": "Python", "tipo": "Lenguaje"},
            {"nombre": "Neo4j", "tipo": "Base de Datos de Grafos"},
            {"nombre": "FastAPI", "tipo": "Framework Web"},
        ]

        with self.driver.session(database=self.database) as session:
            stats = session.execute_write(
                self._tx_crear_estructura,
                estudiantes,
                proyectos,
                tecnologias,
            )
        print(
            f"[2/5] Estructura creada -> Nodos: {stats['nodos']}, "
            f"Relaciones: {stats['relaciones']}"
        )
        return stats

    def obtener_proyectos_por_anio(self, anio: int) -> list[dict[str, Any]]:
        with self.driver.session(database=self.database) as session:
            resultados = session.execute_read(self._tx_consultar_proyectos, anio)

        print(f"\n[3/5] Resultados de consulta (Año {anio}):")
        for item in resultados:
            tecnologias_str = ", ".join(item["tecnologias"])
            print(
                f"  -> {item['estudiante']} [{item['rol']}] desarrolla "
                f"'{item['proyecto']}' con: {tecnologias_str}"
            )
        return resultados

    def actualizar_proyecto(self, titulo: str, nuevo_estado: str, calificacion: int) -> None:
        with self.driver.session(database=self.database) as session:
            actualizado = session.execute_write(
                self._tx_actualizar_proyecto,
                titulo,
                nuevo_estado,
                calificacion,
            )

        print("\n[4/5] Actualización de nodo completada:")
        if actualizado:
            print(
                f"  -> '{actualizado['titulo']}' | Estado: {actualizado['estado']} | "
                f"Calificación: {actualizado['calificacion']}"
            )

    def depurar_nodos_temporales(self) -> None:
        with self.driver.session(database=self.database) as session:
            borrados = session.execute_write(self._tx_eliminar_temporales)
        print(
            f"\n[5/5] Depuración completada -> Nodos borrados: {borrados['nodos']}, "
            f"Relaciones borradas: {borrados['relaciones']}"
        )

    @staticmethod
    def _tx_borrar_todo(tx) -> None:
        tx.run("MATCH (n) DETACH DELETE n")

    @staticmethod
    def _tx_crear_estructura(tx, estudiantes, proyectos, tecnologias) -> dict[str, int]:
        query = """
        UNWIND $estudiantes AS est
        CREATE (:Estudiante {
            nombre: est.nombre,
            matricula: est.matricula,
            semestre: est.semestre
        })
        WITH count(*) AS dummy

        UNWIND $proyectos AS proy
        CREATE (:Proyecto {
            titulo: proy.titulo,
            estado: proy.estado,
            anio: proy.anio
        })
        WITH count(*) AS dummy2

        UNWIND $tecnologias AS tec
        CREATE (:Tecnologia {
            nombre: tec.nombre,
            tipo: tec.tipo
        })
        WITH count(*) AS dummy3

        MATCH (e1:Estudiante {nombre: "Ana Sofía"}),
              (e2:Estudiante {nombre: "Carlos Méndez"}),
              (e3:Estudiante {nombre: "Lucía Torres"}),
              (p1:Proyecto {titulo: "Sistema de Recomendación"}),
              (p2:Proyecto {titulo: "Monitor de Red IoT"}),
              (t1:Tecnologia {nombre: "Python"}),
              (t2:Tecnologia {nombre: "Neo4j"}),
              (t3:Tecnologia {nombre: "FastAPI"})

        CREATE (e1)-[:DESARROLLA {rol: "Líder Técnico"}]->(p1)
        CREATE (e2)-[:DESARROLLA {rol: "Backend Developer"}]->(p1)
        CREATE (e3)-[:DESARROLLA {rol: "Arquitecta de Datos"}]->(p2)
        CREATE (e1)-[:COLABORA_CON {desde: 2025}]->(e2)

        CREATE (p1)-[:USA]->(t1)
        CREATE (p1)-[:USA]->(t2)
        CREATE (p2)-[:USA]->(t1)
        CREATE (p2)-[:USA]->(t3)

        CREATE (tmp:NotaTemporal {descripcion: "Registro de prueba"})
        CREATE (e1)-[:TIENE_NOTA]->(tmp)
        """
        summary = tx.run(
            query,
            estudiantes=estudiantes,
            proyectos=proyectos,
            tecnologias=tecnologias,
        ).consume()
        return {
            "nodos": summary.counters.nodes_created,
            "relaciones": summary.counters.relationships_created,
        }

    @staticmethod
    def _tx_consultar_proyectos(tx, anio: int) -> list[dict[str, Any]]:
        query = """
        MATCH (e:Estudiante)-[r:DESARROLLA]->(p:Proyecto)-[:USA]->(t:Tecnologia)
        WHERE p.anio = $anio
        RETURN e.nombre AS estudiante,
               r.rol AS rol,
               p.titulo AS proyecto,
               collect(t.nombre) AS tecnologias
        ORDER BY proyecto ASC
        """
        result = tx.run(query, anio=anio)
        return [record.data() for record in result]

    @staticmethod
    def _tx_actualizar_proyecto(
        tx, titulo: str, nuevo_estado: str, calificacion: int
    ) -> dict[str, Any] | None:
        query = """
        MATCH (p:Proyecto {titulo: $titulo})
        SET p.estado = $nuevo_estado,
            p.calificacion = $calificacion
        RETURN p.titulo AS titulo, p.estado AS estado, p.calificacion AS calificacion
        """
        record = tx.run(
            query,
            titulo=titulo,
            nuevo_estado=nuevo_estado,
            calificacion=calificacion,
        ).single()
        return record.data() if record else None

    @staticmethod
    def _tx_eliminar_temporales(tx) -> dict[str, int]:
        summary = tx.run("MATCH (n:NotaTemporal) DETACH DELETE n").consume()
        return {
            "nodos": summary.counters.nodes_deleted,
            "relaciones": summary.counters.relationships_deleted,
        }


if __name__ == "__main__":
    servicio = Neo4jGraphService(
        uri=DB_CONFIG["uri"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
    )

    try:
        servicio.verify()
        print("=== Conectado a Neo4j AuraDB (Versión 2 - POO) ===\n")

        servicio.limpiar_todo()
        servicio.poblar_datos_iniciales()
        servicio.obtener_proyectos_por_anio(2026)
        servicio.actualizar_proyecto("Sistema de Recomendación", "Completado", 98)
        servicio.depurar_nodos_temporales()

        print(
            "\nProceso terminado. Visualiza el grafo en Neo4j Workspace con:\n"
            "  MATCH (n)-[r]->(m) RETURN n, r, m;"
        )
    finally:
        servicio.close()
        print("Sesión y driver cerrados correctamente.")