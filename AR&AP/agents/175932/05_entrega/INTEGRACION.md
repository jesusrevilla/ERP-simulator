# Entrega final

- Alumno: José Armando Palomo Cerda.
- Matrícula: 175932.
- Tema: A/R y A/P; capacidad acumulada de cuentas por pagar.
- Rama: feature/175932 en armekmc54-ops/ERP-simulator.
- Issue: https://github.com/jesusrevilla/ERP-simulator/issues/301
- PR: https://github.com/jesusrevilla/ERP-simulator/pull/302
- Pruebas: https://github.com/armekmc54-ops/ERP-simulator/actions/runs/45907283467

El plan se preparó localmente antes del código final. El Issue se publicó por
interfaz web después de los primeros commits porque el conector devolvió 403;
se conserva esta cronología real, sin simular avances de fechas anteriores.

El PR propone integrar el agente y sus evidencias al repositorio original.
La publicación del PR no equivale a aprobación ni merge. No se ejecuta una
fusión automática ni se afirma que los documentos productivos del ERP estén
ya conectados al adaptador de demostración.

Los cinco controles del PR pasaron sobre el commit
037a4a2057409d5ad81f97c6165432299ba9290c:

- MongoDB 184027: https://github.com/jesusrevilla/ERP-simulator/actions/runs/45909807417
- MongoDB 184149: https://github.com/jesusrevilla/ERP-simulator/actions/runs/45909807337
- MRP: https://github.com/jesusrevilla/ERP-simulator/actions/runs/45909807249
- Tutorial Neo4j: https://github.com/jesusrevilla/ERP-simulator/actions/runs/45909807353
- Agente: https://github.com/jesusrevilla/ERP-simulator/actions/runs/45909807328

Se corrigieron Python incompatible en MongoDB, imports y catálogo del tutorial
BOM movido, y conexión del tutorial Neo4j mediante un servicio temporal.
MRP reportó 45 pruebas correctas y 1 omitida por su condición previa; no se
añadieron exclusiones. El agente conserva sus 15 pruebas correctas.
La aprobación y el merge siguen pendientes del mantenedor.

## Explicación breve para clase

El agente vigila cuántas piezas de una recepción ya están facturadas. Si recibo
10 y acepto una factura de 6, solo quedan 4 por facturar: por eso otra de 6 se
bloquea. Un crédito de cantidad de 2 libera capacidad y permite aceptar después
una nueva solicitud de 6. PostgreSQL decide con bloqueo de fila para proteger
operaciones simultáneas, Neo4j muestra las relaciones entre decisiones y
documentos y MongoDB guarda la bitácora. El outbox permite recuperar reportes
cuando falla una base secundaria sin duplicar el efecto de la factura.

