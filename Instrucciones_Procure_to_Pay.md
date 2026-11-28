# Algoritmo de Orquestación Compra-a-Pago (Procure-to-Pay-Orchestrator)

## 1. Descripción general

El algoritmo orquesta a cinco agentes del ERP-Simulator para resolver el ciclo completo de una compra: generar la orden a partir de la necesidad neta del MRP, recibir la mercancía, conciliar la factura en cuentas por pagar y dejar todo auditado. Complementa al `BOM-Manufacturing-Orchestrator` (que cubre estructura y explosión de materiales).

## 2. Agentes involucrados

| Agente | Rol | Reglas que aplica |
|---|---|---|
| Proveedores y datos maestros | Filtra la entrada: proveedor aprobado y SKU activo | RN-01 |
| Órdenes de compra | Convierte la necesidad neta en OC | RN-02 (MOQ y múltiplo) |
| Recibos y entregas | Registra la llegada contra la OC y suma al inventario | No recibir de más, proveedor activo, piezas dañadas |
| Conciliación de cuentas por pagar | Concilia orden – recepción – factura | RN-03, RN-04, RF-05 |
| Integridad transaccional y auditoría | Envoltorio ACID y bitácora | Commit / Rollback, Entradas − Salidas = Stock |

## 3. Flujo de resolución (pipeline secuencial)

1. **Apertura ACID:** el agente de integridad toma un snapshot del estado y abre la transacción.
2. **Filtro de maestros:** se valida que el proveedor esté aprobado y el SKU activo. Si no, se rechaza y se hace rollback.
3. **Orden de compra:** `cantidad = max(necesidad_neta, MOQ)` redondeada hacia arriba al múltiplo del proveedor. La OC queda abierta como compromiso de pago.
4. **Recibo:** se acepta hasta el pendiente de la OC (más solo con autorización del gerente). Al aprobar, el inventario suma `recibido − dañadas`.
5. **Conciliación A/P:** la factura se programa para pago solo si su cantidad es menor o igual a lo recibido y la variación de precio está dentro de la tolerancia (2 % por defecto). La variación aceptada ajusta el costo del inventario.
6. **Cierre y trazabilidad:** commit y registro en bitácora (usuario, fecha, valores antes y después); ante cualquier fallo, rollback. Al final se verifica que Entradas − Salidas = Stock.

## 4. Ejecución

Requisitos: Python 3.9 o superior. CrewAI solo es necesario para el modo crew.

```bash
# Simulación local (sin API key): ejecuta la lógica real de cada agente
python procure_to_pay_orchestrator.py

# Orquestación con CrewAI (requiere instalar crewai y configurar un LLM, p. ej. OPENAI_API_KEY)
pip install crewai
python procure_to_pay_orchestrator.py --crew
```

## 5. Resultado esperado de la simulación

| Paso | Caso | Resultado |
|---|---|---|
| 1 | Necesidad 120, MOQ 100, múltiplo 50 | OC por **150** |
| 2 | OC a proveedor bloqueado | Rechazada (RN-01), rollback |
| 3 | Recibo de 200 contra OC de 150 | Rechazado: no recibir de más |
| 4 | Recibo de 150 con 10 dañadas | Inventario = **140** |
| 5 | Factura 150 a 10.10 (1 % de variación) | Programada para pago, ajuste de costo 15.00 |
| 6 | Factura por 200 (recibido 150) | Retenida (RN-04) |

## 6. Estructura del código

- `agente_proveedores`, `agente_ordenes_compra`, `agente_recibos`, `agente_conciliacion_ap`: lógica de negocio de cada agente.
- `agente_integridad`: envoltorio que aplica snapshot, commit o rollback y escribe la bitácora.
- `verificar_integridad`: comprueba que el inventario cuadre con los movimientos.
- `Procure_to_Pay_Orchestrator`: define los `Agent`, `Task` y `Crew` de CrewAI con proceso secuencial.

## 7. Fuentes de requerimientos

Documentos "MRP, A/R y A/P" (RF-02 a RF-05, RN-01 a RN-04) y "Recibos y las entregas" (reglas de recibos e integridad de datos).
