# Evidencias · 184814

Salida real de la ejecución del workflow **184814 - Programación y Costeo de Órdenes por Ruta** en GitHub Actions:
[ejecución 46041419731](https://github.com/dimae251318-tech/feature-184814/actions/runs/46041419731) (27/11/2026, PostgreSQL 16 y Neo4j 5.26, resultado ✅ *success*).

| Archivo | Paso del workflow | Qué demuestra |
|---|---|---|
| `02_programacion_inicial.txt` | Esquema y datos semilla | Las 3 órdenes se programan: fecha de fin y costo planificado de cada una |
| `03_consultas_agente.txt` | Consultas SQL del agente | Q1 a Q7: simulación de 30 PC, atrasos, centros saturados, desviación, costos por etapa, bitácora y siguiente día laborable |
| `04_grafo_neo4j.txt` | Grafo en Neo4j | 3 órdenes, 9 etapas, 3 centros y 21 días cargados; resultados de las 4 consultas Cypher |
| `05_pruebas.txt` | Pruebas con pytest | **22 de 22 pruebas aprobadas** (17 de PostgreSQL y 5 de Neo4j) |

## Resultados principales

- **OP-2026-001** (30 Gaming PC desde el 1 de diciembre): termina el **21/12/2026** y cuesta **$717,135**. Su compromiso era el 18/12, así que lleva **3 días de atraso**.
- **OP-2026-002** se cruza con la OP-2026-001: el centro **CT-ENS queda al 200 %** del 3 al 7 de diciembre, y Neo4j detecta el mismo conflicto.
- **OP-2026-003** salta la Navidad: su etapa 2 trabaja el 24 y luego el 28 de diciembre.
- La etapa 1 de la OP-2026-001 se despachó con el CPU a $5,350 en vez de $5,200: **desviación de $4,500 (1.30 %)**.
- Si la etapa 1 de la OP-2026-001 se retrasa, el grafo marca como afectadas sus etapas 2 y 3, y como órdenes en riesgo la OP-2026-002 y la OP-2026-003, porque comparten centros.

Para volver a generar estas evidencias, ejecuta el workflow desde la pestaña **Actions** (*Run workflow*). Los mismos archivos se descargan en el artefacto `evidencias-184814`.
