# Modelo de datos · Programación y Costeo de Órdenes por Ruta (184814)

Diagramas del componente del Issue #300. GitHub dibuja los bloques Mermaid directamente.

## 1. Modelo entidad-relación (PostgreSQL)

Las tablas marcadas con **NUEVA** son de este componente. Las demás ya existen en `Rutas/Scheme.sql` y solo se leen o actualizan a través de las funciones; su estructura no cambia.

```mermaid
erDiagram
    hoja_ruta ||--|{ hoja_ruta_operacion : "tiene"
    hoja_ruta_operacion ||--o{ hoja_ruta_operacion_material : "consume"
    hoja_ruta_operacion ||--o{ hoja_ruta_operacion_recurso : "usa"
    hoja_ruta_operacion }o--|| centro_trabajo : "se realiza en"
    hoja_ruta ||--o{ orden_produccion : "define la ruta de"
    orden_produccion ||--|{ orden_produccion_etapa : "tiene"
    orden_produccion_etapa }o--|| centro_trabajo : "se realiza en"
    orden_produccion_etapa ||--o{ orden_produccion_linea : "planifica"
    orden_produccion_etapa ||--o{ orden_etapa_carga_dia : "ocupa (NUEVA)"
    orden_produccion ||--o| orden_fecha_compromiso : "promete (NUEVA)"
    orden_produccion ||--o{ orden_programacion_log : "audita (NUEVA)"
    orden_produccion_linea ||--o{ despacho_produccion : "se despacha en"

    calendario_laboral {
        date fecha PK "NUEVA"
        boolean laborable
        varchar motivo "obligatorio si no es laborable"
    }
    orden_fecha_compromiso {
        int orden_produccion_id PK "NUEVA, FK"
        date fecha_compromiso
        timestamp registrado_en
    }
    orden_etapa_carga_dia {
        int orden_produccion_etapa_id PK "NUEVA, FK"
        date fecha PK
        numeric horas "mayor a 0"
    }
    orden_programacion_log {
        int orden_programacion_log_id PK "NUEVA"
        int orden_produccion_id FK
        varchar tipo "PROGRAMACION, COSTEO, RETRASO"
        date fecha_fin_anterior
        date fecha_fin_nueva
        numeric costo_anterior
        numeric costo_nuevo
        varchar motivo
        int ejecutado_por FK
        timestamp ejecutado_en
    }
    orden_produccion {
        int orden_produccion_id PK
        varchar folio
        numeric cantidad
        varchar estatus
        date fecha_inicio
        date fecha_fin "la calcula fn_programar_orden"
        numeric costo_planificado "lo calcula fn_calcular_costo_planificado"
        numeric costo_real
    }
    orden_produccion_etapa {
        int orden_produccion_etapa_id PK
        int secuencia
        numeric tiempo_preparacion_min
        numeric tiempo_ejecucion_min
        int dias_espera
        date fecha_inicio "calculada"
        date fecha_fin "calculada"
        varchar estatus
    }
    centro_trabajo {
        int centro_trabajo_id PK
        varchar codigo
        numeric capacidad_horas_dia
        numeric costo_hora
    }
```

## 2. Funciones, vistas y triggers nuevos

| Objeto | Tipo | Qué hace |
|---|---|---|
| `fn_es_laborable(fecha)` | Función | Consulta `calendario_laboral`; si la fecha no está, lunes a viernes son laborables. |
| `fn_siguiente_laborable(fecha)` | Función | Primer día laborable igual o posterior a la fecha. |
| `fn_generar_etapas_orden(orden)` | Función | Copia las operaciones, materiales y recursos de la hoja de ruta a la orden. |
| `fn_programar_orden(orden, motivo, usuario)` | Función | Calcula las fechas de cada etapa, la carga por día y el costo, y registra la bitácora. |
| `fn_calcular_costo_planificado(orden, ...)` | Función | Material + recurso + centro de trabajo; actualiza `costo_planificado`. |
| `fn_registrar_retraso(etapa, días, motivo, usuario)` | Función | Recorre el fin de una etapa y reprograma las siguientes. |
| `fn_reenumerar_secuencia(hoja, desde)` | Función | Abre un hueco en la secuencia de una hoja en borrador o en revisión. |
| `tr_bitacora_inmutable` | Trigger | Impide modificar o borrar la bitácora. |
| `vw_programa_ordenes` | Vista | Etapas con fechas, días laborables y holgura contra el compromiso. |
| `vw_carga_centro_dia` | Vista | Horas por centro y día contra su capacidad. |
| `vw_desviacion_costos` | Vista | Costo estándar contra real de lo despachado, por orden y por etapa. |
| `ix_carga_dia_fecha`, `ix_programacion_log_orden`, `ix_op_etapa_centro_fechas` | Índices | Aceleran las vistas de carga y la bitácora. |

## 3. Cálculo de fechas

```mermaid
flowchart TD
    A([fn_programar_orden]) --> B{¿La orden tiene etapas?}
    B -->|No| C[fn_generar_etapas_orden: copia la hoja de ruta]
    B -->|Sí| D
    C --> D[cursor = fecha de inicio de la orden]
    D --> E{¿Etapa PENDIENTE?}
    E -->|No| F[Conserva sus fechas; cursor = su fin + 1]
    E -->|Sí| G["inicio = siguiente laborable(cursor + días de espera)"]
    G --> H["horas = (preparación + ejecución × cantidad) / 60"]
    H --> I[Reparte las horas en días laborables hasta la capacidad del centro]
    I --> J[fin = último día con horas; cursor = fin + 1]
    F --> K{¿Hay más etapas?}
    J --> K
    K -->|Sí| E
    K -->|No| L[Actualiza fecha fin de la orden, etapas y carga por día]
    L --> M[fn_calcular_costo_planificado]
    M --> N[Registra en orden_programacion_log]
```

## 4. Modelo del grafo (Neo4j)

El grafo está a nivel de **orden programada**. El de rutas maestras con estaciones y rutas alternativas pertenece al Issue #249.

```mermaid
flowchart LR
    O((Orden<br/>folio, cantidad,<br/>fecha_fin, fecha_compromiso,<br/>costo_planificado))
    E1((EtapaOrden<br/>secuencia 1))
    E2((EtapaOrden<br/>secuencia 2))
    E3((EtapaOrden<br/>secuencia 3))
    C((CentroTrabajo<br/>codigo, capacidad))
    D((Dia<br/>fecha))

    O -- TIENE_ETAPA --> E1
    O -- TIENE_ETAPA --> E2
    O -- TIENE_ETAPA --> E3
    E1 -- "SIGUIENTE {dias_espera}" --> E2
    E2 -- "SIGUIENTE {dias_espera}" --> E3
    E1 -- EN_CENTRO --> C
    E1 -- "PROGRAMADA_EL {horas}" --> D
```

Todos los nodos llevan `fuente = 'rutas_184814'`, para no mezclarse con los grafos de otros compañeros si comparten la misma base de Neo4j.
