# Agente IA de Implosión (Where-Used) y Análisis de Impacto por Desabasto BOM

Alumno: Aaron Emanuel Gonzalez Diaz, matrícula 182447. Rama: `feature/182447`.

## Problema
Cuando falta un componente de la BOM o sube su precio, no es evidente qué subensambles y productos terminados se afectan, porque la BOM se consulta normalmente de padre a hijo.

## Qué hace el agente
1. **Implosión Where-Used:** DFS inverso multinivel desde un SKU de componente, con control de ciclos y opción de incluir o excluir líneas inactivas.
2. **Consumo acumulado:** multiplica las cantidades a lo largo de cada ruta de ensamble.
3. **Impacto por desabasto:** calcula el déficit (demanda − stock) y separa productos terminados (PT) de subensambles (SE).
4. **Plan de mitigación:** nivel de riesgo (BAJO, MEDIO, CRITICO) y acciones. Usa OpenAI si `LLM_PROVIDER=openai` y hay `OPENAI_API_KEY`; si no, usa un motor experto local.
5. **Neo4j (opcional):** si se pasa un driver, ejecuta las consultas de `consultas.cypher` y registra un nodo `AlertaDesabasto`.

## Archivos
- `agente_where_used_llm.py`: agente y planificador.
- `test_agente_where_used.py`: pruebas unitarias y funcionales (con un driver falso de Neo4j).
- `consultas.cypher`: consultas Cypher del agente.
- `evidencias/`: salida de las pruebas y ejemplo de ejecución.

## Cómo ejecutar
```bash
cd BOM/agente_where_used_impacto
python test_agente_where_used.py
```
No requiere dependencias externas ni conexión a Neo4j.

## Resultado de las pruebas
2 pruebas, ambas aprobadas (ver `evidencias/salida_pruebas.txt`):
- Implosión multinivel con líneas activas e inactivas.
- Análisis de impacto: déficit de 10 unidades, PT afectados `PC001` y `WS001`, subensamble `SUB-GPU`, riesgo CRITICO y registro de la alerta en Neo4j.

## Ejemplo
Para `GPU001` con stock 20 y demanda 30, el agente reporta déficit de 10, consumo de 2 unidades por `WS001` y 1 por `PC001` (vía `SUB-GPU`), y recomienda compra urgente, sustituto homologado vía ECO y reprogramar el subensamble (ver `evidencias/salida_ejemplo.json`).
