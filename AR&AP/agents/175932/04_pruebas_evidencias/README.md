# Evidencias reales - APReceiptCapacityAgent

Ejecución: https://github.com/armekmc54-ops/ERP-simulator/actions/runs/45907283467
Artefacto original: https://github.com/armekmc54-ops/ERP-simulator/actions/runs/45907283467/artifacts/15158820397
Commit ejecutado: cddb6f810fb9aa345aee967274d7b64583e5f6b3

Se ejecutaron 15 pruebas: 3 unitarias y 12 de integración. Todas pasaron.
Se reconciliaron 31 eventos en PostgreSQL, Neo4j y MongoDB por identificador,
estado y motivo. El outbox terminó sin pendientes y la vista de discrepancias
no devolvió filas. Los datos son sintéticos.

results.json conserva las versiones, estados, decisiones y nodos/relaciones
exportados de Neo4j. execution.log conserva la sección de pruebas del log del
job sin el prefijo horario de Actions. No se modificaron los resultados.

Las imágenes del PDF se renderizan desde esos datos y se identifican como
diagramas o visualizaciones de resultados; no simulan capturas de GitHub.

Issue: https://github.com/jesusrevilla/ERP-simulator/issues/301
Pull Request: https://github.com/jesusrevilla/ERP-simulator/pull/302
Estado al preparar el reporte: abierto, no fusionado; requiere revisión del mantenedor.

La comprobación del agente también pasó en el commit documental a1f1c1774d5b6762ccc798cf6358ac02ab629302,
run https://github.com/armekmc54-ops/ERP-simulator/actions/runs/45908204282.
Los controles heredados del ERP pueden fallar de manera independiente. En el
PR se observó el fallo de Neo4j Tutorial Pipeline CI por URI vacía y variable
driver sin inicializar (run 45908209213 del repositorio original).
