# 4. Diagramas de flujo

Estos diagramas describen la **lógica** de cada etapa: detección, evaluación, autorización y sustitución. Cada uno corresponde a una función de `gestor_descontinuados.py` y a un objeto de `sql/schema_descontinuados.sql`.

---

## 4.1 Máquina de estados del ciclo de vida (RN-01)

```mermaid
stateDiagram-v2
    [*] --> ACTIVO: alta del componente
    ACTIVO --> PROXIMO_A_DESCONTINUAR: PCN / EOL anunciado
    PROXIMO_A_DESCONTINUAR --> ACTIVO: proveedor revoca el aviso
    ACTIVO --> DESCONTINUADO: discontinuación inmediata
    PROXIMO_A_DESCONTINUAR --> DESCONTINUADO: llega la fecha de fin
    DESCONTINUADO --> [*]

    note right of PROXIMO_A_DESCONTINUAR
        Alerta preventiva.
        Compras permitidas hasta la fecha LTB.
        Penalizado como sustituto.
    end note
    note right of DESCONTINUADO
        Estado final.
        Sin compras ordinarias (RN-02).
        Stock utilizable si está autorizado (RN-03).
    end note
```

---

## 4.2 Detección y generación de la alerta

Funciones: `ERP.cambiar_estado`, `ERP.boms_afectadas`, `ERP.generar_alerta`, `ERP.priorizar`. En SQL: `trg_ciclo_vida_cambio` y `fn_boms_afectadas`.

```mermaid
flowchart TD
    A([Cambio de estado solicitado]) --> B{¿Estado válido<br/>y transición permitida?}
    B -- No --> B1[Rechazar con error RN-01] --> Z0([Fin])
    B -- Sí --> C[Actualizar estado y<br/>guardar historial]
    C --> D{¿Nuevo estado es<br/>DESCONTINUADO o<br/>PROXIMO_A_DESCONTINUAR?}
    D -- No --> Z1([Fin])
    D -- Sí --> E[Inicializar cola con el SKU, nivel 1]
    E --> F{¿Cola vacía?}
    F -- No --> G[Tomar SKU buscado]
    G --> H[Buscar BOM ACTIVAS que lo<br/>contienen en sus líneas]
    H --> I{¿Padre ya está<br/>en la ruta?}
    I -- Sí: ciclo --> F
    I -- No --> J[Registrar BOM, nivel y ruta]
    J --> K[Encolar padre con nivel + 1]
    K --> F
    F -- Sí --> L[Buscar órdenes abiertas cuyo producto<br/>requiere el SKU en cualquier nivel]
    L --> M[Demanda abierta = Σ cantidad orden ×<br/>requerimiento por unidad]
    M --> N[Cobertura = min de existencias / demanda, 1]
    N --> P{Prioridad RN-10}
    P -- sin BOM --> P1[BAJA]
    P -- descontinuado + órdenes<br/>+ cobertura menor a 100 % --> P2[CRITICA]
    P -- órdenes, o descontinuado<br/>en ≥ 3 BOM --> P3[ALTA]
    P -- otro caso --> P4[MEDIA]
    P1 & P2 & P3 & P4 --> Q[Crear alerta + BOM afectadas<br/>Emitir evento BOM.DiscontinuedComponentAlert]
    Q --> R[Notificar a Responsable de BOM,<br/>Compras, Producción y Responsable técnico]
    R --> Z2([Fin])
```

**Ejemplo del escenario:** `MB-B550-PLUS` → 4 BOM (2 de nivel 1 y 2 de nivel 2), 3 órdenes abiertas, demanda de 45, existencias de 12, cobertura de 27 % → prioridad **CRITICA**.

---

## 4.3 Evaluación y recomendación de sustitutos (agente)

Funciones: `ERP.es_compatible`, `ERP.recomendar_sustitutos`.

```mermaid
flowchart TD
    A([Alerta abierta]) --> B[Obtener especificaciones del original<br/>y criterios de su categoría]
    B --> C[Listar candidatos de la misma categoría]
    C --> D{¿Quedan candidatos<br/>por evaluar?}
    D -- Sí --> E[Tomar candidato]
    E --> F{¿Está DESCONTINUADO?}
    F -- Sí --> X[Descartar con motivo] --> D
    F -- No --> G[Evaluar cada criterio:<br/>IGUAL → valor idéntico<br/>MINIMO → valor ≥ original]
    G --> H{¿Cumple todos?}
    H -- No --> X
    H -- Sí --> I[Calcular puntuaciones de 0 a 1:<br/>inventario = min existencias/faltante, 1<br/>proveedor = 1 si disponible<br/>costo = 1 − Δcosto%<br/>entrega = 1 − días/30<br/>ciclo de vida = 1 activo / 0.3 EOL<br/>impacto = 1 − 0.2 × especificaciones distintas]
    I --> J[Puntuación = Σ peso × puntuación<br/>0.25, 0.20, 0.20, 0.15, 0.10, 0.10]
    J --> K[Generar justificación textual] --> D
    D -- No --> L{¿Hay compatibles?}
    L -- No --> M[Escalar: sin sustituto directo,<br/>evaluar rediseño o compra LTB] --> Z([Fin])
    L -- Sí --> N[Ordenar por puntuación descendente<br/>y tomar los 3 mejores]
    N --> O[Guardar recomendaciones con detalle,<br/>justificación y versión del modelo]
    O --> Z
```

**Resultado en el escenario:**

| Pos. | Candidato | Puntuación | Observación |
|---|---|---|---|
| 1 | `MB-B550-PRO` | 0.9620 | Igual especificación, +6.5 % de costo, 40 en stock |
| 2 | `MB-B550-LEGACY` | 0.8800 | Compatible pero con EOL anunciado (penalizado) |
| 3 | `MB-X570-ELITE` | 0.6578 | +56.5 % de costo, stock de 10 para un faltante de 28 |
| — | `MB-A520M-LITE` | descartado | factor de forma mATX, PCIe 3, una sola ranura M.2 |
| — | `MB-B650-AURA` | descartado | socket AM5, memoria DDR5 |

---

## 4.4 Autorización y aplicación de la sustitución

Funciones: `ERP.autorizar`, `ERP.aplicar_sustitucion`. En SQL: `trg_validar_sustitucion` y `trg_*_inmutables`.

```mermaid
flowchart TD
    A([Recomendación seleccionada]) --> B{¿Rol del usuario es<br/>RESPONSABLE_TECNICO?}
    B -- No --> B1[Rechazar: RN-06] --> Z0([Fin])
    B -- Sí --> C{¿Decisión?}
    C -- Rechazar --> C1[Registrar RECHAZADA<br/>con comentario] --> Z1([Volver al agente])
    C -- Aprobar --> D{¿Revalidación de<br/>compatibilidad OK?}
    D -- No --> D1[Rechazar: RN-05] --> Z0
    D -- Sí --> E[Registrar autorización APROBADA<br/>inmutable]
    E --> F[Evaluar órdenes abiertas afectadas<br/>en todos los niveles]
    F --> G{Estado de la orden}
    G -- LIBERADA / EN_PROCESO --> G1[CONSERVAR versión<br/>snapshot]
    G -- PLANIFICADA --> G2[REPLANIFICAR]
    G1 & G2 --> H[Por cada BOM con uso directo]
    H --> I[Crear revisión vN+1 copiando líneas<br/>y reemplazando original → sustituto]
    I --> J[Marcar vN como OBSOLETO y<br/>cerrar su vigencia]
    J --> K[Reasignar órdenes PLANIFICADA<br/>de vN a vN+1]
    K --> L[Insertar en sustituciones_bom<br/>trigger valida autorización]
    L --> M{¿Más BOM directas?}
    M -- Sí --> H
    M -- No --> N[Cerrar alerta: RESUELTA<br/>Emitir BOM.SubstitutionApplied]
    N --> O[Disparar recálculo de MRP] --> Z2([Fin])
```

> Las BOM de nivel superior (por ejemplo `PC-OFI-100`) **no se versionan**. Referencian al subensamble `ENS-BASE-AM4` y, al explotarse, toman su revisión vigente (`v2`). Así se evita multiplicar revisiones innecesarias.

Todo el bloque de E a N se ejecuta en **una transacción** (RNF-02): si falla un paso, no se aplica ninguno.

---

## 4.5 Regla del MRP para componentes descontinuados

Función: `ERP.mrp`. En SQL: `trg_bloquear_compra_descontinuado`.

```mermaid
flowchart TD
    A([Corrida MRP]) --> B[Explosión multinivel de la demanda<br/>→ necesidades brutas por SKU]
    B --> C{¿Quedan SKU?}
    C -- No --> Z([Publicar recomendaciones])
    C -- Sí --> D[Tomar SKU y requerido]
    D --> E{¿SKU es sustituto de un<br/>descontinuado con stock<br/>autorizado?}
    E -- Sí --> E1[Consumir primero el stock<br/>del original<br/>política AGOTAR_EXISTENCIAS] --> F
    E -- No --> F[Neto = requerido − existencias]
    F --> G{¿SKU DESCONTINUADO?}
    G -- No --> H{¿Neto > 0?}
    H -- Sí --> H1[Recomendación ORDINARIA] --> C
    H -- No --> C
    G -- Sí --> I{¿Uso de stock<br/>autorizado?}
    I -- Sí --> I1[Consumir existencias disponibles]
    I -- No --> I2[No consumir]
    I1 & I2 --> J{¿Queda faltante?}
    J -- Sí --> J1[Faltante BLOQUEADO:<br/>requiere sustitución<br/>sin recomendación de compra] --> C
    J -- No --> C
```

**Escenario (pedido de 30 `PC-OFI-100` + 10 `PC-WS-300`):**

| Momento | `MB-B550-PLUS` | `MB-B550-PRO` | Otras compras |
|---|---|---|---|
| AS-IS | **Compra 28** (inválida) | — | RAM 20, SSD 30, PSU 25 |
| TO-BE, sustitución pendiente | Consume 12; **28 bloqueadas** | — | RAM 20, SSD 30, PSU 25 |
| TO-BE, sustitución aplicada | Consume 12 (agotar existencias) | 28 desde stock (40) → sin compra | RAM 20, SSD 30, PSU 25 |
