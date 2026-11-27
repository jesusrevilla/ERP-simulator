# Análisis de la base de datos de Rutas frente a `Rutas.md`

Fuentes: `Rutas/Scheme.sql` (18 tablas y 8 triggers), `Rutas/Rutas.md` y `Rutas/descripcion_agente_178920.md`.

## 1. Cobertura de los nodos de `Rutas.md`

| Nodo | Objeto en la base de datos | Estado |
|---|---|---|
| B1 Etapas secuenciales | `hoja_ruta_operacion.secuencia`, `etapa_ruta` | Cubierto |
| B2 Materiales y capacidades por etapa | `hoja_ruta_operacion_material`, `hoja_ruta_operacion_recurso` | Cubierto |
| B3 Run Time | `tiempo_preparacion_min`, `tiempo_ejecucion_min` | Cubierto: se guardan los tiempos, pero las fechas de la orden se capturan, no se calculan |
| B4 Días de espera | `dias_espera` | Cubierto |
| C1 Secuencia entera y correlativa | `INTEGER`, `CHECK (secuencia >= 1)`, `UNIQUE (hoja_ruta_id, secuencia)` | Parcial: no impide huecos (etapas 1 y 3) |
| C2 Fechas dentro del horizonte | `tr_validar_horizonte_etapa` | Cubierto |
| C3 y C4 Despacho previo completo | `tr_registrar_despacho` | Cubierto |
| D1 Guardado del maestro de etapas | `etapa_ruta` | Cubierto |
| D2 Total Run Time | `tr_actualizar_tiempo_total` | Cubierto: suma preparación y ejecución |
| D3 Reenumeración al insertar | `UNIQUE ... DEFERRABLE` | Parcial: permite reenumerar dentro de una transacción, pero no hay rutina que lo haga |
| E1 Orden con 3 etapas | `orden_produccion`, `orden_produccion_etapa`, `orden_produccion_linea` | Cubierto |
| E1a Filtro de la Etapa 1 | `orden_produccion_linea.orden_produccion_etapa_id` e índice | Cubierto |
| E1b Descuento de inventario | `tr_registrar_despacho` actualiza `existencia` | Cubierto |
| E1c Auditoría de costos | `costo_real` se acumula; `costo_planificado` queda en 0 | Parcial |
| E2 Cambio de almacén tras la Etapa 1 | `orden_produccion_etapa.almacen_id` | Parcial: existe la columna, pero ninguna regla |
| F1 Líneas huérfanas | `orden_produccion_etapa_id NOT NULL` y llave foránea | Cubierto |
| F2 Borrado de etapa con movimientos | `tr_bloquear_borrado_etapa` | Cubierto |
| F3 La orden conserva su ruta | `tr_conservar_ruta_original` | Cubierto |

## 2. Hallazgos

1. **C1:** nada valida que la secuencia sea correlativa; insertar las etapas 1 y 3 es válido.
2. **Sobredespacho:** `fn_registrar_despacho` no compara el despacho con la cantidad planificada ni verifica que la línea pertenezca a la etapa indicada.
3. **E1c:** `costo_planificado` no se calcula en ningún trigger.
4. **E2:** el cambio de almacén no tiene regla.
5. **Nombres de estado:** `descripcion_agente_178920.md` usa `EN REVISION` y el esquema usa `EN_REVISION`.
6. **Total Run Time:** la base de datos suma preparación y ejecución; `182735-IARutas/rutas_erp.py` usa solo el tiempo de ejecución.
7. **Datos semilla:** solo hay roles; faltan materiales, almacenes, centros de trabajo y hojas de ruta para probar el agente.

## 3. Estado del agente (`descripcion_agente_178920.md`)

| Componente | Archivo | Estado |
|---|---|---|
| Conector PostgreSQL | `Scheme.sql` | Esquema listo; falta el código de conexión |
| Validador de reglas | `182735-IARutas/rutas_erp.py` | Implementado y probado (27 pruebas) |
| Gestor de estados y roles | `Scheme.sql` (segregación RN-12 y trigger RN-11) | Reglas en la base de datos; falta el código del agente |
| Traductor ISA-95 | JSON de ejemplo de 172122 y 178218 | Solo ejemplos; falta el serializador |
| Núcleo LLM | — | Solo descrito |
