Tutorial de Neo4j

Tutorial: Neo4j Tutorial: Using And Querying Graph Databases in Python (DataCamp)

Neo4j se ejecutó con Docker en un Codespace de CS50, en lugar de AuraDB, y se consultó con Python usando el driver oficial neo4j.

Archivos
tutorial_neo4j.py: conexión, tamaño del grafo, consultas Cypher, consulta con parámetros, escritura con CREATE y transacción con sesión.
1. Iniciar Neo4j
bash
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/<contraseña> neo4j
2. Entorno de Python
bash
mkdir neo4j_tutorial && cd neo4j_tutorial
pip install neo4j python-dotenv tqdm pandas
3. Credenciales

Archivo .env (no se sube al repositorio):

NEO4J_USERNAME="neo4j"
NEO4J_PASSWORD="<contraseña>"
NEO4J_URI="bolt://localhost:7687"
4. Carga de los datos de fútbol
bash
wget https://raw.githubusercontent.com/BexTuychiev/medium_stories/refs/heads/master/2024/9_september/3_neo4j_python/ingest_football_data.py
python ingest_football_data.py
5. Consultas del tutorial
bash
python tutorial_neo4j.py

El script realiza:

Conexión con verify_connectivity().
Conteo de nodos y relaciones del grafo.
Equipo con más victorias en la FIFA World Cup.
Consulta con parámetros ($tournament, $limit) para la UEFA Euro.
Escritura con CREATE: nuevo entrenador (Coach) y relación COACHES.
Verificación del entrenador creado.
Transacción con sesión (execute_read): goleadores de la FIFA World Cup.
6. Limpieza
bash
docker rm -f neo4j
