from neo4j import GraphDatabase

# 1. Configuración de la conexión a Neo4j (AuraDB o instancia local)
URI = "neo4j+s://df9fda9e.databases.neo4j.io"
USER = "df9fda9e"
PASSWORD = "mXG14iVx4hLHiRrMhxiJpilGkEd5Ee-5sNcM4HGl0Ns"


class Neo4jTutorialApp:
    def __init__(self, uri, user, password):
        # Crear la instancia del driver de Neo4j
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        # Cerrar el driver al terminar
        self.driver.close()

    def verificar_conexion(self):
        # Verificar que la conexión sea exitosa
        self.driver.verify_connectivity()
        print("¡Conexión establecida correctamente con Neo4j!\n")

    def crear_datos_ejemplo(self, nombre_persona: str, titulo_pelicula: str):
        """Crea nodos de tipo Person y Movie, y una relación ACTED_IN entre ellos."""
        with self.driver.session() as session:
            session.execute_write(self._tx_crear_relacion, nombre_persona, titulo_pelicula)
        print(f"[Creación] Relación creada: {nombre_persona} -> ACTED_IN -> {titulo_pelicula}")

    @staticmethod
    def _tx_crear_relacion(tx, nombre_persona, titulo_pelicula):
        query = """
        MERGE (p:Person {name: $nombre_persona})
        MERGE (m:Movie {title: $titulo_pelicula})
        MERGE (p)-[:ACTED_IN]->(m)
        """
        tx.run(query, nombre_persona=nombre_persona, titulo_pelicula=titulo_pelicula)

    def consultar_peliculas_por_actor(self, nombre_persona: str):
        """Consulta las películas asociadas a una persona específica."""
        with self.driver.session() as session:
            resultados = session.execute_read(self._tx_consultar_actor, nombre_persona)
        
        print(f"\n[Consulta] Películas en las que participó {nombre_persona}:")
        for registro in resultados:
            print(f"  * {registro['pelicula']}")

    @staticmethod
    def _tx_consultar_actor(tx, nombre_persona):
        query = """
        MATCH (p:Person {name: $nombre_persona})-[:ACTED_IN]->(m:Movie)
        RETURN m.title AS pelicula
        """
        result = tx.run(query, nombre_persona=nombre_persona)
        return [record.data() for record in result]


# Ejecución principal del script
if __name__ == "__main__":
    # Inicializar la aplicación con las credenciales
    app = Neo4jTutorialApp(URI, USER, PASSWORD)

    try:
        app.verificar_conexion()

        # 1. Insertar algunos datos de prueba estilo DataCamp
        app.crear_datos_ejemplo("Keanu Reeves", "The Matrix")
        app.crear_datos_ejemplo("Keanu Reeves", "John Wick")
        app.crear_datos_ejemplo("Carrie-Anne Moss", "The Matrix")

        # 2. Consultar la información estructurada en el grafo
        app.consultar_peliculas_por_actor("Keanu Reeves")

    except Exception as e:
        print(f"Ocurrió un error durante la ejecución: {e}")
    finally:
        app.close()
        print("\nDriver cerrado correctamente.")
