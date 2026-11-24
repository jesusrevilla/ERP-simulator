# Actividad del 10 de noviembre de 2026: eventos ISA-95 y tutorial Neo4j

**Alumno:** Cristian Ricardo Godinez Limones  
**Asignatura:** CNO VI Sistemas ERP — Grupo A26-T51A  
**Docente:** Jesús Alberto Revilla Silva  
**Caso de estudio:** TechAssembly S.A., ensamble de Gaming PC.

## 1. Catálogo de eventos

**Archivo:** \`Inventario/eventos_CristianGodinez_ISA95.json\`

Se definieron nueve eventos de ejemplo para intercambiar información del nivel 4 (ERP) al nivel 3 (MES/MOM), siguiendo una **alineación conceptual** con la jerarquía ISA-95. No es una certificación formal de cumplimiento. Los eventos son simulados; no representan operaciones ejecutadas en una fábrica real.

Cada evento registra identificador único, marca de tiempo ISO 8601 UTC, documento y correlación, rol, operación, regla aplicada, artículo, cantidad, variación del inventario y existencias antes/después.

### Secuencia del inventario

| Evento | Existencia anterior | Cambio | Existencia posterior |
|---|---:|---:|---:|
| Alta de producto | 0 | +10 | 10 |
| Compra en borrador | 10 | 0 | 10 |
| Recepción confirmada | 10 | +8 | 18 |
| Venta en borrador | 18 | 0 | 18 |
| Venta confirmada | 18 | -3 | 15 |
| Cancelación de venta | 15 | +3 | 18 |
| Venta rechazada por stock insuficiente | 18 | 0 | 18 |
| Ajuste autorizado | 18 | -13 | 5 |
| Alerta de stock mínimo | 5 | 0 | 5 |

Se aplican las reglas RN-04 (disponibilidad), RN-06 (compras), RN-07 (ventas), RN-08 (cancelación), RN-09 (ajustes) y RF-09 (alertas), documentadas en la primera aportación comercial.

## 2. Tutorial de Neo4j

**Archivo:** \`neo4j_tutorial_cristian/erp_graph.py\`

El tutorial utiliza la lista de materiales real de \`src/mrp.py\` del repositorio, junto con los niveles de stock de \`sql/seeds.sql\`, para representar en un grafo:

- \`CGProduct\`: producto final Gaming PC y artículo comercial del catálogo.
- \`CGMaterial\`: seis componentes de la BOM.
- \`CGEvent\`: nueve eventos simulados del catálogo.
- \`CG_REQUIRES\`: material y cantidad necesaria para un producto.
- \`CG_AFFECTS\`: relación entre un evento y el artículo.

Se usan \`MERGE\`, \`UNWIND\`, restricciones de unicidad y consultas \`MATCH\` con parámetros. Los nodos y relaciones tienen nombres propios (\`CG\`) para no interferir con las demostraciones de otros estudiantes. No se utiliza \`MATCH (n) DETACH DELETE n\` ni se requieren credenciales de terceros.

### Validación MRP

Para una orden de **30 Gaming PC**, la lista de materiales requiere 30 unidades de cada componente, excepto la RAM, que requiere 60. El inventario de referencia contiene 20 tarjetas gráficas y, por tanto, el faltante calculado es **10 Graphics Card RTX**. La consulta parametrizada de Neo4j verifica que el resultado sea igual al cálculo Python.

## 3. Ejecutar sin Neo4j

\`\`\`bash
python -m pytest tests/test_neo4j_eventos_cristian.py -q
python -m neo4j_tutorial_cristian.erp_graph --offline --quantity 30
\`\`\`

## 4. Ejecutar con Neo4j

Se requiere Python, el paquete \`neo4j\` y una base Neo4j 5.x accesible.

\`\`\`bash
python -m pip install -r requirements.txt
\`\`\`

Configurar **fuera del repositorio** las variables de entorno \`NEO4J_URI\`, \`NEO4J_USERNAME\`, \`NEO4J_PASSWORD\` y opcionalmente \`NEO4J_DATABASE\`; por ejemplo, un servicio local en \`bolt://localhost:7687\`. No registrar claves de acceso ni archivos \`.env\` con contraseñas.

\`\`\`bash
python -m neo4j_tutorial_cristian.erp_graph --quantity 30
\`\`\`

El script valida el JSON, verifica la conexión a Neo4j, carga los nodos de forma idempotente con \`MERGE\`, consulta los faltantes y compara los resultados con el cálculo de MRP en Python.

## 5. Pruebas y automatización

- \`tests/test_neo4j_eventos_cristian.py\`: consistencia del catálogo JSON, marcas de tiempo, control de inventario, prueba de faltantes, validación de cantidades y seguridad de consultas parametrizadas.
- \`.github/workflows/cristian_neo4j.yml\`: workflow independiente que inicia un contenedor Neo4j 5.26, ejecuta pruebas, espera el servicio, carga datos y comprueba resultados.

**La ejecución remota del workflow debe verificarse en la pestaña Actions; la existencia del workflow no es evidencia de una ejecución exitosa.**

## 6. Relación con las aportaciones previas

Este ejercicio complementa el módulo comercial \`src/erp_comercial_cristian.py\`: transforma sus reglas a un catálogo de mensajes y enseña cómo representar entidades en una base de grafos. No modifica los archivos de los otros estudiantes ni sustituye la implementación PostgreSQL/MRP existente.

**Propuestas de continuación:** almacenar los eventos reales de transacciones en una bandeja de salida (outbox), recibirlos en Neo4j y construir un enlace con el inventario de PostgreSQL.
