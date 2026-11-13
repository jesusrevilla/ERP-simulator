# Neo4j con Python: análisis de fútbol


## Modelo de datos

Los archivos CSV de partidos, goleadores y tandas de penales se transforman en nodos como `Team`, `Match`, `Player`, `Tournament`, `City` y `Country`. Las relaciones permiten identificar equipos participantes, resultados, goles, torneos y sedes.

## Archivos

- **`conexion.py`**: establece y verifica la conexión con Neo4j AuraDB.
- **`ingest_football_data.py`**: importa los CSV, crea índices y construye nodos y relaciones.
- **`consultas.py`**: ejecuta consultas Cypher para analizar victorias y goleadores, y registra la relación entre un entrenador y su equipo.
- **`requirements.txt`**: incluye las dependencias `neo4j`, `python-dotenv`, `pandas` y `tqdm`.

## Consultas implementadas

- Equipo con más victorias en la Copa Mundial.
- Tres equipos con más victorias en la Eurocopa.
- Cinco máximos goleadores de la Copa Mundial.
- Asociación de un entrenador con un equipo mediante `MERGE`.

La conexión utiliza las variables de entorno `NEO4J_URI`, `NEO4J_USERNAME` y `NEO4J_PASSWORD`; las credenciales privadas no forman parte del código.
