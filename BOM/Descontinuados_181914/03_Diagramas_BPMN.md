# 3. Diagramas BPMN

Igual que en `BOM/ERP/BOM requeriments.md`, se usa Mermaid para aproximar la notación BPMN 2.0:

| Elemento BPMN | Representación |
|---|---|
| Evento de inicio | Círculo verde |
| Evento de fin | Círculo rojo de borde grueso |
| Evento intermedio de mensaje o temporizador | Círculo doble |
| Tarea | Rectángulo redondeado |
| Compuerta exclusiva | Rombo |
| Carril (*lane*) | Subgráfico con el nombre del actor |
| Flujo de mensaje entre participantes | Flecha punteada |
| Problema identificado (anotación) | Nota gris punteada |

---

## 3.1 Proceso actual (AS-IS)

Sin gestión del ciclo de vida, la descontinuación se descubre **después** de que el MRP emitió la compra, y la identificación de BOM y sustitutos es manual.

```mermaid
flowchart TB
  subgraph ASIS["Proceso AS-IS: componente descontinuado detectado al comprar"]
    direction TB
    subgraph CLI["Carril: Ventas / Cliente"]
      I((Inicio))
      PED("Registrar pedido<br/>de cliente")
    end
    subgraph MRPL["Carril: ERP – MRP"]
      CALC("Calcular necesidades<br/>con la BOM vigente")
      REC("Generar recomendación<br/>de compra de faltantes")
      RECALC("Ejecutar MRP<br/>nuevamente")
    end
    subgraph COMP["Carril: Comprador"]
      CONS("Consultar disponibilidad<br/>con el proveedor")
      DISP{"¿Componente<br/>disponible?"}
      OC("Emitir orden<br/>de compra")
    end
    subgraph PROV["Carril: Proveedor"]
      RESP(("Responder:<br/>componente<br/>descontinuado"))
    end
    subgraph BOML["Carril: Responsable de BOM"]
      BUSCAR("Identificar manualmente<br/>las BOM afectadas")
      INVEST("Investigar posibles<br/>sustitutos")
      COMPAT{"¿Sustituto<br/>compatible?"}
      ACT("Editar la BOM<br/>vigente")
    end
    subgraph TECL["Carril: Responsable técnico"]
      AUT("Autorizar<br/>el cambio")
    end
    subgraph PRODL["Carril: Producción"]
      FAB("Continuar aprovisionamiento<br/>y fabricación")
      F((Fin))
    end
  end

  I --> PED --> CALC --> REC --> CONS --> DISP
  DISP -->|Sí| OC --> FAB --> F
  DISP -->|No| RESP --> BUSCAR --> INVEST --> COMPAT
  COMPAT -->|No| INVEST
  COMPAT -->|Sí| AUT --> ACT --> RECALC --> REC

  N1["P2: el MRP recomienda comprar<br/>un componente descontinuado"]
  N2["P1/P3: detección tardía,<br/>la orden ya está comprometida"]
  N3["P4: sin where-used multinivel,<br/>se omiten BOM indirectas"]
  N4["P5: sin especificaciones<br/>estructuradas ni criterios"]
  N5["P6: se edita la BOM aprobada,<br/>sin historial ni snapshot"]
  N1 -.- REC
  N2 -.- RESP
  N3 -.- BUSCAR
  N4 -.- COMPAT
  N5 -.- ACT

  classDef inicio fill:#dcfce7,stroke:#15803d,stroke-width:2px;
  classDef fin fill:#fee2e2,stroke:#b91c1c,stroke-width:4px;
  classDef decision fill:#fef3c7,stroke:#a16207;
  classDef mensaje fill:#e0f2fe,stroke:#0369a1,stroke-width:3px;
  classDef problema fill:#f1f5f9,stroke:#b91c1c,stroke-dasharray:5 5,color:#7f1d1d;
  class I inicio;
  class F fin;
  class DISP,COMPAT decision;
  class RESP mensaje;
  class N1,N2,N3,N4,N5 problema;
```

**Lectura del diagrama.** El ciclo `REC → CONS → DISP(No) → … → RECALC → REC` es el **retrabajo** que causa los retrasos. Mientras se recorre, las órdenes de fabricación esperan. Las anotaciones rojas relacionan cada actividad con los problemas P1–P6 de [01_Analisis_del_Proceso.md](01_Analisis_del_Proceso.md#15-problemas-identificados).

---

## 3.2 Proceso propuesto (TO-BE)

La descontinuación se registra **en cuanto el proveedor la notifica**. El ERP detecta el impacto, bloquea las compras inválidas y el agente recomienda sustitutos. El responsable técnico autoriza y el ERP aplica el cambio por revisión, con historial.

```mermaid
flowchart TB
  subgraph TOBE["Proceso TO-BE: gestión inteligente de componentes descontinuados"]
    direction TB
    subgraph PROV["Carril: Proveedor"]
      PCN(("PCN / EOL<br/>recibido"))
    end
    subgraph COMP["Carril: Comprador"]
      REG("Registrar estado de ciclo de vida,<br/>fecha LTB y fuente")
      STOCK{"¿Autorizar uso<br/>del stock existente?"}
      LTB{"¿Conviene compra<br/>de última vez?"}
      CUV("Emitir compra tipo<br/>ULTIMA_COMPRA")
    end
    subgraph ERP["Carril: ERP – BOM / Inventarios / MRP"]
      VAL{"¿Transición de<br/>estado válida?"}
      RECH("Rechazar cambio")
      F0((Fin))
      WU("Where-used multinivel:<br/>BOM afectadas, nivel y ruta")
      IMP("Cruzar existencias,<br/>órdenes abiertas y demanda")
      ALERTA("Generar alerta priorizada<br/>y notificar responsables")
      BLOQ("MRP: bloquear compras ordinarias<br/>y consumir stock autorizado")
      NUEVA("Crear nueva revisión de BOM<br/>y marcar anterior OBSOLETO")
      HIST("Registrar sustitución, autorización<br/>y evaluación de órdenes")
      MRP2("Recalcular MRP<br/>política agotar existencias")
    end
    subgraph IA["Carril: Agente inteligente"]
      FILT("Filtrar candidatos por<br/>compatibilidad técnica")
      HAY{"¿Existe candidato<br/>compatible?"}
      RANK("Puntuar y ordenar: inventario,<br/>proveedor, costo, entrega,<br/>ciclo de vida, impacto")
      JUST("Emitir top 3 con<br/>justificación")
      ESCAL("Escalar: rediseño o<br/>búsqueda externa")
    end
    subgraph TEC["Carril: Responsable técnico"]
      EVAL("Evaluar recomendación<br/>y validar en banco de pruebas")
      DEC{"¿Aprobar<br/>sustituto?"}
      APR("Registrar autorización<br/>APROBADA")
      RCH("Registrar RECHAZADA<br/>con motivo")
    end
    subgraph PROD["Carril: Producción"]
      ORD("Evaluar órdenes afectadas:<br/>conservar o replanificar")
    end
    subgraph BOMR["Carril: Responsable de BOM"]
      APL("Aplicar sustitución<br/>autorizada")
      F1((Fin))
    end
  end

  PCN -.->|mensaje| REG --> VAL
  VAL -->|No| RECH --> F0
  VAL -->|Sí| STOCK
  STOCK -->|Sí o No: se registra la decisión| WU --> IMP --> ALERTA
  ALERTA --> BLOQ
  ALERTA --> LTB
  LTB -->|Sí, antes de LTB| CUV
  ALERTA --> FILT --> HAY
  HAY -->|No| ESCAL --> EVAL
  HAY -->|Sí| RANK --> JUST --> EVAL --> DEC
  DEC -->|No| RCH --> FILT
  DEC -->|Sí| APR --> ORD --> APL --> NUEVA --> HIST --> MRP2 --> F1

  R1["RN-02: sin compras ordinarias<br/>de descontinuados"]
  R2["RN-04: detección multinivel"]
  R3["RN-05: compatibilidad técnica"]
  R4["RN-06: sin autorización<br/>no hay sustitución"]
  R5["RN-07: evaluar órdenes antes"]
  R6["RN-08: revisión nueva,<br/>historial inmutable"]
  R1 -.- BLOQ
  R2 -.- WU
  R3 -.- FILT
  R4 -.- APR
  R5 -.- ORD
  R6 -.- NUEVA

  classDef inicio fill:#dcfce7,stroke:#15803d,stroke-width:2px;
  classDef fin fill:#fee2e2,stroke:#b91c1c,stroke-width:4px;
  classDef decision fill:#fef3c7,stroke:#a16207;
  classDef mensaje fill:#e0f2fe,stroke:#0369a1,stroke-width:3px;
  classDef ia fill:#ede9fe,stroke:#6d28d9;
  classDef regla fill:#f1f5f9,stroke:#64748b,stroke-dasharray:5 5;
  class PCN mensaje;
  class F0,F1 fin;
  class VAL,STOCK,LTB,HAY,DEC decision;
  class FILT,RANK,JUST,ESCAL ia;
  class R1,R2,R3,R4,R5,R6 regla;
```

> **Nota.** Después de `ALERTA`, el bloqueo en MRP, la evaluación de la compra de última vez y el análisis del agente ocurren **en paralelo**, como en una compuerta paralela BPMN. Mermaid no tiene un símbolo propio para ella, por eso se dibujan tres flujos que salen del mismo nodo.

---

## 3.3 Comparación AS-IS vs TO-BE

| Aspecto | AS-IS | TO-BE |
|---|---|---|
| Momento de detección | Al intentar comprar (después del MRP) | Al registrar el PCN; alerta en ≤ 15 min |
| Fuente de la información | Llamada al proveedor | Estado de ciclo de vida en el maestro de artículos |
| Identificación de BOM afectadas | Manual, solo de uso directo | CTE recursiva con nivel y ruta |
| Compras del MRP | Incluye componentes descontinuados | Bloqueadas por trigger y por regla del MRP |
| Uso del stock existente | Sin control | Autorizado explícitamente; se agota antes del sustituto |
| Selección de sustituto | Investigación ad hoc | Filtro de compatibilidad + ranking explicable |
| Autorización | Informal | Rol `RESPONSABLE_TECNICO`, registro inmutable |
| Cambio en la BOM | Edición de la versión vigente | Nueva revisión; la anterior pasa a `OBSOLETO` |
| Órdenes en curso | No se evalúan | Se decide conservar o replanificar cada una |
| Trazabilidad | Ninguna | Alerta → recomendación → autorización → sustitución |
| Retrabajo | Ciclo MRP → compra → MRP | Sin ciclo: el MRP se recalcula una sola vez |
