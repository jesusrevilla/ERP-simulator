# Implementación y validación - fases 3 y 4

**Validada en GitHub Actions:** 15 pruebas correctas y 31 eventos reconciliados
en PostgreSQL, Neo4j y MongoDB. Consultar ../04_pruebas_evidencias/.

## Requisitos y ejecución futura

Python 3.12, PostgreSQL, Neo4j 5 y MongoDB accesibles por red.
Desde esta carpeta, preparar un entorno virtual e instalar requirements.txt.
Configurar las variables de .env.example en la terminal; el programa no carga
ese archivo automáticamente. No publicar credenciales ni una DSN con contraseña.
Usar una base de demostración y un usuario con acceso solo al esquema de práctica.
La función usa SECURITY INVOKER; no otorga permisos ni eleva privilegios.

Órdenes previstas para la fase autorizada de ejecución:

```sh
python agent.py init
python agent.py add-receipt --receipt REC-001 --supplier PROV-001 --item CPU --quantity 10
python agent.py evaluate examples/01_factura.json
python agent.py evaluate examples/02_exceso_acumulado.json
python agent.py evaluate examples/03_credito_cantidad.json
python agent.py evaluate examples/04_factura_tras_credito.json
python agent.py status
python agent.py export
```

## Escenario ejecutado

Recibido 10; primera factura de 6 reserva 6. Otra de 6 debe bloquearse porque
solo quedan 4. Crédito de cantidad de 2 a la primera factura libera 2;
ahora una nueva solicitud de 6 puede aceptarse y deja consumido 10.
La factura bloqueada se reenvía con event_id nuevo; reutilizar EV-002 conservaría
la decisión inicial. La idempotencia se identifica por event_id; el documento
aceptado se identifica por document_id. Son conceptos diferentes.

## Archivos

- sql/schema.sql: esquema, ledger, decisiones, outbox y función evaluate.
- agent.py: interfaz de línea de comandos y proyección de reportes.
- graph.cypher: grafo explicativo por evento, idempotente con MERGE.
- consultas.cypher y consultas_mongo.js: inspección de las proyecciones.
- sql/consultas_validacion.sql: reconciliación y revisión del outbox.
- examples/: entradas sintéticas; no son capturas ni resultados.

## Operación y pendientes

Una respuesta REJECTED es una decisión de negocio, no necesariamente un fallo
técnico. Las excepciones técnicas del comando deben detener la operación y se
propagan; no se presenta una aprobación si PostgreSQL falla.

El exportador puede entregar primero a Neo4j y después fallar en MongoDB. En ese
caso PostgreSQL conserva el pendiente y la siguiente ejecución repite ambas
escrituras de manera idempotente. No hay garantía de sincronización instantánea.
El grafo conserva cantidades como texto para no perder precisión decimal.

No ejecutar borrados generales, MATCH (n) DETACH DELETE n ni DROP SCHEMA como
parte del uso normal. La preparación de fixtures aislados, pruebas de fallos y
concurrencia se ejecutó en una base temporal. Los permisos productivos siguen pendientes.
El workflow .github/workflows/agent-capacity-175932.yml ejecuta verify_project.py
y publica los resultados como artefacto. No usa secretos de bases productivas.
