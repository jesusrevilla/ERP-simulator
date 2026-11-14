# Tutorial de Neo4j con Python: partidos de fútbol

**Actividad:** practicar bases de datos de grafos con Neo4j AuraDB, consultas Cypher e integración con Python.

Este ejercicio sigue el tutorial proporcionado en clase: *Neo4j Tutorial: Using And Querying Graph Databases in Python*. Se conserva la idea original de importar resultados de fútbol y consultar nodos `Team`, `Match`, `Tournament` y `Player`.

## 1. Preparación

1. Crea una instancia gratuita de **Neo4j AuraDB** en <https://console.neo4j.io/> y guarda **Connection URI**, usuario y contraseña.
2. Instala Python 3 y abre la carpeta de este tutorial en VS Code (**File > Open Folder**).
3. Abre una terminal (**Terminal > New Terminal**).
4. Instala las dependencias:

   ```bash
   python -m pip install -r requirements.txt
   ```

   Según el sistema, `python` puede llamarse `py` (Windows) o `python3` (macOS/Linux).
5. Haz una copia del archivo `.env.example`, ponle de nombre `.env` y sustituye los valores de ejemplo por tus datos reales:

   ```dotenv
   NEO4J_URI=neo4j+s://TU_INSTANCIA.databases.neo4j.io
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=TU_PASSWORD
   ```

   **No publiques `.env` en GitHub.** El archivo `.gitignore` lo excluye del control de versiones. El nombre correcto de la variable de URL es `NEO4J_URI` (no `NEO4J_CONNECTION_URI`).

## 2. Comprobar la conexión

Desde la terminal, dentro de esta carpeta:

```bash
python conexion.py
```

Si funciona, debe aparecer `Conexión correcta con Neo4j AuraDB`.

## 3. Importar los datos de fútbol (tutorial original)

Descarga el archivo `ingest_football_data.py` desde el repositorio del autor y guárdalo en esta misma carpeta:

<https://github.com/BexTuychiev/medium_stories/blob/master/2024/9_september/3_neo4j_python/ingest_football_data.py>

En GitHub, abre ese enlace, haz clic en **Raw** y usa **Guardar como...** para guardarlo con el nombre `ingest_football_data.py`.

Ejecuta:

```bash
python ingest_football_data.py
```

Ese script carga datos CSV de partidos, goleadores y penales desde archivos remotos, crea índices y relaciones mediante Cypher y puede tardar algunos minutos. Necesita Internet. No vuelvas a ejecutarlo sin necesidad: parte de las relaciones de goles usa `CREATE` y podría duplicarlas.

El script del autor se distribuye en su enlace original y no forma parte de estos archivos propios.

## 4. Ejecutar consultas Cypher desde Python

Una vez importados los datos, escribe:

```bash
python consultas.py
```

El archivo `consultas.py` demuestra:

- `MATCH`, `RETURN`, `COUNT`, `ORDER BY` y `LIMIT`.
- Consultas parametrizadas para torneos (ejemplo: FIFA World Cup).
- Búsqueda de goleadores con una sesión de lectura.
- `MERGE` para registrar un entrenador y su relación con un equipo sin duplicar nodos del mismo nombre.

Para visualizar el grafo desde AuraDB, entra a tu instancia, abre **Query** y prueba:

```cypher
MATCH (t:Team)-[:WON]->(m:Match)-[:PART_OF]->(:Tournament {name: 'FIFA World Cup'})
RETURN t, m
LIMIT 20;
```

Puedes cambiar a vista de grafo para observar los nodos y sus relaciones.

## 5. Evidencias sugeridas para la entrega

Capturas recomendadas (si el profesor las solicita):

1. Consola indicando que la conexión a AuraDB fue correcta.
2. Proceso de importación de los CSV finalizado.
3. Resultado de una consulta Cypher en AuraDB.
4. Ejecución de `consultas.py` desde VS Code.
5. Pull request abierto hacia `jesusrevilla/ERP-simulator`, rama `development`.

**Seguridad:** oculta credenciales, identificadores de conexión sensibles y contraseñas en tus capturas. Nunca subas `.env`.

## 6. Pull request

Para subir archivos con el botón **Add file > Upload files** de la web de GitHub, **no arrastres la carpeta de trabajo si dentro creaste un `.env` real**: esa carga manual puede incluirlo aunque exista `.gitignore`. Vuelve a extraer el ZIP original en otra carpeta limpia (sin `.env`) y sube únicamente esos archivos de ejemplo. Después abre un pull request con estos valores:

- **Base repository:** `jesusrevilla/ERP-simulator`
- **Base branch:** `development`
- **Head repository:** tu fork
- **Compare branch:** tu rama de actividad (por ejemplo `feature/179798`)

Describe qué ejecutaste realmente. No afirmes haber completado la importación o las pruebas si todavía no las has realizado.

## Fuentes

- Tutorial de Neo4j compartido en la actividad.
- Script de importación del autor: <https://github.com/BexTuychiev/medium_stories/blob/master/2024/9_september/3_neo4j_python/ingest_football_data.py>
- Documentación oficial: <https://neo4j.com/docs/aura/>
