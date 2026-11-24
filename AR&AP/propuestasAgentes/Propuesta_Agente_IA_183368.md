# Propuesta de Agente de IA – Módulo A/R y A/P

*Para el proyecto Mini ERP · 13 Noviembre 2026*

## 1. Alcance (corto)

Un agente inteligente basado en conocimiento y objetivos que apoya las operaciones de A/R y A/P usando únicamente técnicas básicas de IA:

- **Lógica proposicional** para validar las reglas de negocio y explicar por qué se rechaza una operación.
- **Algoritmos de búsqueda** para proponer cómo aplicar un cobro o pago a una o varias facturas.
- **Optimización básica** para priorizar la cobranza y decidir qué facturas de proveedor pagar con un presupuesto limitado.

**No incluye** aprendizaje automático, entrenamiento de modelos ni grandes volúmenes de datos.

### Dentro del alcance

| # | Capacidad | Técnica |
|---|---|---|
| 1 | Validar reglas de negocio (cliente activo, folio único, límite de crédito, monto ≤ saldo, 3-way match) y explicar el motivo del rechazo | Lógica proposicional |
| 2 | Proponer la aplicación de un cobro o pago a varias facturas sin exceder saldos | Búsqueda  |
| 3 | Priorizar qué facturas cobrar primero | Optimización |
| 4 | Elegir qué facturas de proveedor pagar con un presupuesto disponible | Optimización |

### Fuera del alcance

- Cancelar o ajustar documentos de forma autónoma.
- Generar asientos contables por cuenta propia.
- Predicciones o modelos entrenados con datos históricos.

## 2. Tecnologías a usar

| Capa | Tecnología | Uso |
|---|---|---|
| Lenguaje | Python 3 | Implementación del agente |
| Lógica proposicional | Python puro (operadores `and`, `or`, `not`, implicación) o `sympy.logic` | Representar y evaluar reglas |
| Búsqueda y optimización | Python (`heapq`, listas, recursión) | BFS/DFS, costo uniforme, backtracking, voraz, programación dinámica |
| Base de datos | SQLite o PostgreSQL | Clientes, proveedores, facturas, pagos y bitácora |
| Interfaz | Línea de comandos, Flask o Streamlit | Capturar datos y mostrar la propuesta |
| Pruebas | `pytest` | Pruebas unitarias del documento de requerimientos |

## 2. Implementación teórica

### 2.1 Arquitectura del agente

```
Percepción (consulta a la BD)
        ↓
Base de conocimiento (reglas en lógica proposicional)
        ↓
Razonamiento: validación + búsqueda + optimización
        ↓
Acción (propuesta con explicación) → el usuario confirma → el ERP guarda
```

El agente **propone**; el usuario **confirma**; el ERP **ejecuta** dentro de una transacción.

### 2.2 Lógica proposicional: base de conocimiento

Cada condición de las reglas de negocio se define como una proposición:

| Símbolo | Significado |
|---|---|
| A | El cliente/proveedor está activo |
| U | El folio es único para ese cliente/proveedor |
| L | Saldo abierto + nueva factura ≤ límite de crédito |
| M | Monto del pago ≤ saldo de la factura |
| S | Las aplicaciones suman el monto del pago |
| P | Coincide el precio (factura = OC) |
| Q | Coincide la cantidad (factura = recepción = OC) |
| R | Coincide el artículo |
| D | La operación tiene motivo (cancelación/ajuste) |

**Reglas (fórmulas):**

- Facturar a cliente: `FacturarAR ⇒ A ∧ U ∧ L`
- Registrar factura de proveedor: `FacturarAP ⇒ A ∧ U ∧ R ∧ Q ∧ P`
- Aplicar pago: `AplicarPago ⇒ M ∧ S`
- Cancelar o ajustar: `Cancelar ⇒ D`

**Razonamiento:** el agente evalúa la conjunción. Si alguna proposición es falsa, aplica *modus tollens* y la operación se rechaza indicando cuál falló. Ejemplo:

> Entrada: A = V, U = V, L = F → `A ∧ U ∧ L` = F → **Rechazar: "se excede el límite de crédito"**.

Una **tabla de verdad** cubre los casos de prueba. La explicación en lenguaje claro sale de asociar a cada proposición un mensaje de error.

### 2.3 Búsqueda: aplicación de un pago a varias facturas

**Formulación como problema de búsqueda:**

| Elemento | Definición |
|---|---|
| Estado | (monto restante del pago, lista de saldos por factura) |
| Estado inicial | (monto del pago, saldos actuales) |
| Acciones | Aplicar una cantidad x a la factura *i*, con 0 < x ≤ saldo *i* y x ≤ monto restante |
| Prueba de meta | Monto restante = 0 (la suma de aplicaciones es igual al pago) |
| Costo | Prioridad: aplicar primero a las facturas más próximas a vencer (o ya vencidas) |

**Algoritmos propuestos:**

- **Estrategia voraz:** ordenar facturas por fecha de vencimiento y aplicar hasta agotar el monto (rápido y suficiente en la mayoría de los casos).
- **Backtracking con poda:** cuando el cobro debe conciliarse exactamente con un conjunto de facturas (por ejemplo, el cliente paga $2,320 y hay facturas de $1,160, $500 y $660, $1,160), se buscan subconjuntos cuya suma sea igual al monto. Se poda cuando la suma parcial supera el monto.
- **Costo uniforme / A\*:** si se desea minimizar el costo definido (por ejemplo, el atraso acumulado), se expande primero el estado de menor costo.

**Pseudocódigo (backtracking):**

```
función conciliar(monto, facturas, i, seleccion):
    si monto == 0: devolver seleccion
    si i == len(facturas) o monto < 0: devolver None
    # opción 1: incluir la factura i
    r = conciliar(monto - facturas[i].saldo, facturas, i+1, seleccion + [i])
    si r != None: devolver r
    # opción 2: omitirla
    devolver conciliar(monto, facturas, i+1, seleccion)
```

### 2.4 Optimización

**a) Priorizar la cobranza (voraz)**

Función de utilidad para cada factura vencida:

```
prioridad = saldo × días_de_atraso
```

Se ordenan las facturas de mayor a menor prioridad; el agente sugiere a quién cobrar primero.

**b) Pagos a proveedores con presupuesto limitado (mochila 0/1)**

| Elemento | Definición |
|---|---|
| Variable | Pagar o no pagar cada factura *i* (xᵢ ∈ {0,1}) |
| Restricción | Σ saldoᵢ · xᵢ ≤ presupuesto disponible en bancos |
| Función objetivo | Maximizar Σ valorᵢ · xᵢ |
| Valor | Mayor para facturas vencidas o con descuento por pronto pago |



### 2.5 Flujo completo de un cobro

1. El usuario captura: "cobro de $X del cliente C".
2. **Lógica:** el agente verifica A (cliente activo) y M (monto ≤ saldo total abierto).
3. **Búsqueda:** propone la distribución del monto entre facturas.
4. **Lógica:** verifica S (las aplicaciones suman el monto) y que ninguna exceda su saldo.
5. El usuario confirma y el ERP guarda con bloqueo de fila (`SELECT … FOR UPDATE`) para evitar doble aplicación.
6. Se registra en bitácora el origen "agente" y la regla evaluada.

## 3. Pruebas

| Función | Entrada | Resultado esperado |
|---|---|---|
| `validarLimiteCredito` | Límite $5,000, saldo $4,500, factura $1,160 | Rechaza (L = F) |
| `aplicarPago` | Saldo $1,160, pago $500 | Saldo $660 |
| `aplicarPago` | Saldo $660, pago $700 | Error: pago mayor al saldo (M = F) |
| `validar3WayMatch` | Precio de factura distinto al de la OC | Rechaza (P = F) |
| `conciliar` | Cobro $1,820; facturas $1,160, $500, $660 | Selecciona $1,160 + $660 |
| `priorizarCobranza` | Dos facturas con distinto saldo y atraso | Orden descendente por saldo × atraso |
| `elegirPagos` | Presupuesto $2,000; facturas con distinto valor | Subconjunto de mayor valor dentro del presupuesto |
