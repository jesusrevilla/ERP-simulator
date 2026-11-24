# Evidencia de ejecución — 175932

Tutorial ejecutado en Neo4j Community 5.26.33 con Python 3.12.16.

- [Ejecución exitosa de GitHub Actions](https://github.com/armekmc54-ops/ERP-simulator/actions/runs/43326039416).
- [Artefacto original](https://github.com/armekmc54-ops/ERP-simulator/actions/runs/43326039416/artifacts/13992666693).
- `results.json`: resultados reales, versiones, commit y validaciones.
- `execution.log`: sección de ejecución del tutorial extraída del log del job; se retiró el prefijo horario de Actions de cada línea. El registro completo permanece en el enlace del run.

Los conteos por etiqueta y relación se capturaron después de la ingesta y antes de crear los entrenadores. El top de goleadores se contrastó de forma independiente con los CSV fijados. Se verificó la creación de un nodo y una relación para Scaloni y que ejecutar MERGE dos veces crea 1 y 0 nodos, respectivamente.

La primera ejecución detectó una expectativa desactualizada del ranking del artículo de 2024. Se corrigió la validación para comparar el grafo con sus datos de entrada; esta evidencia corresponde a la ejecución posterior, que pasó todas las comprobaciones.
