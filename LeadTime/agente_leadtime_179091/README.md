# Agente de Análisis de Riesgo y Cuellos de Botella de Lead Time (179091)

## Descripción
Este agente inteligente evalúa el riesgo de incumplimiento en los tiempos de entrega (*Lead Time*) dentro del simulador ERP integrando tres motores de bases de datos:
1. **PostgreSQL:** Almacena el historial de entregas y calcula la desviación promedio (`lead_time_real - lead_time_prometido`).
2. **Neo4j (Cypher):** Modela el grafo de dependencias `Producto -> Componente <- Proveedor` para detectar la ruta crítica y buscar proveedores alternos.
3. **MongoDB:** Registra las alertas clasificadas por severidad (`BAJO`, `MEDIO`, `CRITICO`) y las recomendaciones de mitigación.

## Reglas del Sistema Experto
- **Desviación >= 4 días:** Severidad `CRITICO` → Escalar incidencia y sugerir proveedor alterno de Neo4j.
- **Desviación >= 2 días:** Severidad `MEDIO` → Aumentar stock de seguridad.
- **Desviación < 2 días:** Severidad `BAJO` → Mantener plan actual.

## Ejecución Automatizada
El agente se ejecuta automáticamente mediante el workflow `.github/workflows/agente_leadtime_179091.yml` en GitHub Actions, el cual levanta los contenedores de PostgreSQL, MongoDB y Neo4j y valida el flujo completo.
