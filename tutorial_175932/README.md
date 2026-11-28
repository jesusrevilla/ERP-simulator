# Tutorial de Neo4j — 175932

Práctica del [tutorial de DataCamp](https://www.datacamp.com/tutorial/neo4j-tutorial).
Se utiliza Neo4j Community en un servicio temporal de GitHub Actions en lugar de
AuraDB. El driver de Python, las consultas Cypher y el modelo de fútbol son los
del ejercicio; no se requieren credenciales de una cuenta en la nube.

## Contenido

- Conexión con `GraphDatabase` y `verify_connectivity`.
- Carga por lotes de partidos, goles y penaltis, con índices y relaciones.
- Equipo con más victorias en mundiales mediante `execute_query`.
- Top 3 de la Eurocopa con parámetros.
- Creación de Lionel Scaloni y su relación `COACHES` con Argentina.
- Comparación de `CREATE` y `MERGE`, comprobando que repetir `MERGE` no duplica.
- Top 5 de goleadores del Mundial mediante `session.execute_read`.
- Conteos, versiones y resultados exportados a JSON solo después de verificar las consultas.

La ingesta se reutiliza de `neo4j_tutorial/ingest_football_data.py` del repositorio
(commit `de5e3f8f065fd896ac3a6d526b2914e6edc049c7`). Los CSV proceden de
[international_results](https://github.com/martj42/international_results), fijados
al commit `b0948cb558c927c357db4067eac5b37b96d0e4bb` para reproducir los resultados.
Los números pueden diferir de los publicados en 2024 porque el dataset incluye
partidos posteriores. No se usan resultados copiados del artículo como evidencia.

## Ejecución

El workflow **Tutorial Neo4j 175932** ejecuta la práctica en una base vacía y
publica el artefacto `neo4j-tutorial-175932-evidence` con `results.json` y
`execution.log`. La contraseña del servicio temporal es de demostración; no es
una credencial de AuraDB ni se usa fuera del job.

Para ejecutar localmente, usar Python 3.12 y una base Neo4j 5.26 vacía dedicada:

```sh
python -m venv tutorial_175932/.venv
# Activar el entorno según el sistema operativo.
pip install -r tutorial_175932/requirements.txt
# Copiar .env.example como .env dentro de tutorial_175932 y completar las credenciales.
python tutorial_175932/run_tutorial.py
```

El script rechaza bases con nodos para no mezclar los datos de la práctica con
los del ERP. Al terminar cierra el driver. Los archivos `.env` quedan excluidos
de Git. La evidencia registra el commit ejecutado y la URL del run cuando se
ejecuta en Actions.
