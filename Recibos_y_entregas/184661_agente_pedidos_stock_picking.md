# Integrante 3: Agente de pedidos, stock y picking
## 1. Objetivo del agente

El agente revisa los **eventos de salida del pedido** en el Andén de Expedición y decide si el pedido puede surtirse. Para ello:

1. Valida que el pedido pueda procesarse, es decir, que traiga folio y una cantidad válida.
2. Verifica que haya **stock suficiente** para que el inventario no quede en negativo (RN-01).
3. Comprueba que el **lote** no esté vencido ni bloqueado (RN-02).
4. Si todo se cumple, **reserva el stock** con bloqueo de fila (DI-01), para que no se asigne simultáneamente a otro pedido.

Si alguna validación falla, **no reserva nada** y devuelve retroalimentación estructurada. Si todo pasa, el pedido continúa a `RF-07` (packing list y guía de embarque).

---

## 2. Eventos que atiende

En `eventos.json`, los eventos del agente están en la línea `LINE-OUTBOUND-01`:

| Código RF | `msg_id` | Emisor → Receptor | Tipo de evento | Qué hace el agente |
| --- | --- | --- | --- | --- |
| `RF-05` | `MSG-OUT-001` | `ERP.SalesModule` → `Outbound.Dispatch01` | `PROCESS_SALES_ORDER` | Recibe y valida el pedido. |
| `GW_RN01_RN02` | `MSG-OUT-002` | `ERP.BusinessRulesEngine` → `Outbound.Dispatch01` | Validación RN-01 y RN-02 | Aplica las reglas de stock y lote. |
| `RF-06` | `MSG-OUT-003` | `Dispatch01.OperatorTerminal` → `ERP.Database` | `ROW_LEVEL_LOCK_ALLOCATION` | Confirma la reserva con bloqueo de fila (DI-01). |

También **lee** un evento de la línea de entrada, sin atenderlo:

| Código RF | `msg_id` | Tipo de evento | Para qué lo lee |
| --- | --- | --- | --- |
| `RF-02` | `MSG-IN-003` | `CAPTURE_TRACEABILITY` | Obtener el lote (`batch_id`) y su caducidad (`expiry_date`). |

**Cómo identifica cada evento:** por el campo `payload.operation`. El mensaje `MSG-OUT-002` no trae `operation`, así que se identifica por su `step_code` (`GW_RN01_RN02`). Los eventos `RF-07` y `RF-08` son de otro agente y este los ignora.

---

## 3. Datos o tablas que necesita consultar

| Dato | Campos | De dónde sale en `eventos.json` |
| --- | --- | --- |
| **Pedido** | `sales_order_id`, `requested_qty`, fecha | `MSG-OUT-001` → `SO-2026-5511`, 20 unidades, `2026/11/10` |
| **Inventario** | `available_stock`, `item_id` | `MSG-OUT-002` → 100 disponibles; `MSG-OUT-003` → `PROD-FINISHED-01` |
| **Lotes** | `batch_id`, `expiry_date`, estado | `MSG-IN-003` → `L-2026-11-04-X`, caduca `2028-11-10` |

El JSON no trae el **estado del lote** (`DISPONIBLE` o `BLOQUEADO`). El agente lo da por `DISPONIBLE` si no viene, y lo rechaza si llega como `BLOQUEADO`.

Para trabajar contra una base de datos real, se proponen estas tablas mínimas (**propuesta**, no existen en el repositorio):

| Tabla | Campos | Uso |
| --- | --- | --- |
| `sales_orders` | `sales_order_id`, `item_id`, `requested_qty`, `status` | Pedido a surtir |
| `inventory` | `item_id`, `stock`, `reserved` | `available_stock = stock - reserved` |
| `lots` | `batch_id`, `item_id`, `expiry_date`, `status` | Vigencia y bloqueo del lote |

---

## 4. Reglas que aplica

### RN-01: Stock negativo

El pedido solo se reserva si `available_stock >= requested_qty`; así, el inventario nunca queda en negativo.

| Caso | Resultado |
| --- | --- |
| 100 disponibles, 20 pedidas | `PASSED` (quedan 80) |
| 100 disponibles, 120 pedidas | `FAILED` → *Stock insuficiente* |

### RN-02: Lotes vencidos o bloqueados

El lote solo es despachable si **no está bloqueado** y su `expiry_date` es **igual o posterior** a la fecha del pedido.

| Caso | Resultado |
| --- | --- |
| `L-2026-11-04-X`, caduca `2028-11-10`, pedido del `2026/11/10` | `PASSED` |
| Lote vencido o con estado `BLOQUEADO` | `FAILED` → *Lote vencido o bloqueado* |

**Orden:** primero RN-02 y después RN-01. Así, el stock de un lote que no se puede vender no cuenta como disponible.

### DI-01: Reserva con bloqueo de fila

Solo se acepta `ROW_LEVEL_LOCK_ALLOCATION` (`RF-06`) si RN-01 y RN-02 pasaron y si `reserved_qty` es igual a lo pedido. La reserva bloquea la fila del artículo, de modo que un segundo pedido simultáneo espera y vuelve a leer el stock ya actualizado:

```sql
BEGIN;
SELECT stock, reserved FROM inventory WHERE item_id = 'PROD-FINISHED-01' FOR UPDATE;
UPDATE inventory SET reserved = reserved + 20 WHERE item_id = 'PROD-FINISHED-01';
COMMIT;
```

---

## 5. Decisiones y retroalimentación que devuelve

| Decisión | Cuándo |
| --- | --- |
| `CONTINUAR` | El pedido (`RF-05`) es válido y pasa a validación. |
| `RESERVAR` | RN-01 y RN-02 pasan (`GW_RN01_RN02`). |
| `RESERVADO` | La reserva de `RF-06` coincide con lo validado; sigue `RF-07`. |
| `RECHAZAR` | Falla una regla, el pedido es inválido o se intenta reservar sin validación. |
| `REVISAR` | Llega un evento de salida que el agente no conoce. |

Cada respuesta es **estructurada**: `msg_id`, `step_code`, `evento`, `decision` y, cuando hay problema, `regla_fallida`, `motivo` y `accion_sugerida`.

### Resultado con `eventos.json` (caso real)

Salida obtenida al ejecutar el código de la sección 6 con el archivo:

```json
{"msg_id": "MSG-OUT-001", "step_code": "RF-05", "evento": "PROCESS_SALES_ORDER", "decision": "CONTINUAR", "sales_order_id": "SO-2026-5511"}
{"msg_id": "MSG-OUT-002", "step_code": "GW_RN01_RN02", "evento": "GW_RN01_RN02", "decision": "RESERVAR", "sales_order_id": "SO-2026-5511", "reglas": {"RN-01": "PASSED", "RN-02": "PASSED"}}
{"msg_id": "MSG-OUT-003", "step_code": "RF-06", "evento": "ROW_LEVEL_LOCK_ALLOCATION", "decision": "RESERVADO", "item_id": "PROD-FINISHED-01", "reserved_qty": 20, "siguiente_paso": "RF-07"}
```

### Qué sucede si no hay existencias

Prueba cambiando `requested_qty` de `MSG-OUT-001` a **120**:

```json
{"msg_id": "MSG-OUT-002", "step_code": "GW_RN01_RN02", "evento": "GW_RN01_RN02", "decision": "RECHAZAR", "regla_fallida": "RN-01", "motivo": "Stock insuficiente", "accion_sugerida": "Dejar el pedido pendiente y reabastecer el faltante", "disponible": 100, "solicitado": 120, "faltante": 20}
{"msg_id": "MSG-OUT-003", "step_code": "RF-06", "evento": "ROW_LEVEL_LOCK_ALLOCATION", "decision": "RECHAZAR", "motivo": "Reserva sin validación aprobada", "accion_sugerida": "No bloquear stock hasta que RN-01 y RN-02 pasen"}
```

1. Se rechaza en `GW_RN01_RN02` con la regla, el motivo y el **faltante** (20 unidades).
2. **No se reserva nada**: si llega el `RF-06`, el agente lo rechaza para no bloquear stock de otros pedidos.
3. El pedido queda **pendiente** y no avanza a `RF-07` ni `RF-08`.
4. La acción sugerida es reabastecer; la mercancía entraría de nuevo por la línea Inbound (`RF-01` a `RF-04`).

### Lote vencido

Prueba cambiando `expiry_date` de `MSG-IN-003` a `2026-01-01`:

```json
{"msg_id": "MSG-OUT-002", "step_code": "GW_RN01_RN02", "evento": "GW_RN01_RN02", "decision": "RECHAZAR", "regla_fallida": "RN-02", "motivo": "Lote vencido o bloqueado", "accion_sugerida": "Surtir de otro lote vigente o liberar el lote con Calidad", "batch_id": "L-2026-11-04-X"}
```

### Detalles detectados en `eventos.json`

| `msg_id` | Detalle | Acción sugerida |
| --- | --- | --- |
| `MSG-OUT-001` | El pedido no trae `item_id`; el artículo solo aparece hasta `MSG-OUT-003`. | Incluir `item_id` en `PROCESS_SALES_ORDER`. |
| `MSG-OUT-002` | No indica qué lote se validó ni trae `operation`. | Agregar `operation`, `batch_id` y `expiry_date`. |
| `MSG-OUT-003` | Se reserva `PROD-FINISHED-01`, pero en la entrada se recibió `PROD-001` (`MSG-IN-002`). | Confirmar si es el mismo artículo; si no, el lote `L-2026-11-04-X` no aplica a este pedido. |
| `MSG-OUT-002` | `available_stock` es 100, pero en `MSG-IN-004` se recibieron 105. | Verificar si las 5 unidades extra entraron al inventario. |

---

## 6. Fragmento de código de ejemplo

El código **lee `eventos.json`**, recorre la jerarquía ISA-95 e identifica cada evento por su tipo. Usa la función `validar_salida` tal como se definió para este agente.

```python
import json
from datetime import datetime, date

OUTBOUND = "LINE-OUTBOUND-01"


def validar_salida(stock_disponible, cantidad_solicitada, lote_despachable):
    if not lote_despachable:
        return {"decision": "RECHAZAR", "motivo": "Lote vencido o bloqueado"}
    if stock_disponible < cantidad_solicitada:
        return {"decision": "RECHAZAR", "motivo": "Stock insuficiente"}
    return {"decision": "RESERVAR"}


def cargar_mensajes(ruta):
    """Recorre la jerarquía ISA-95 de eventos.json y devuelve los mensajes en orden."""
    with open(ruta, encoding="utf-8") as archivo:
        datos = json.load(archivo)
    mensajes = []
    for linea in datos["isa_95_hierarchy"]["manufacturing_lines"]:
        for maquina in linea["machines"]:
            for paso in maquina["sequence_activities"]:
                for mensaje in paso["messages"]:
                    mensajes.append({**mensaje, "line_id": linea["line_id"],
                                     "step_code": paso["step_code"]})
    return mensajes


def tipo_evento(mensaje):
    # MSG-OUT-002 no trae "operation", así que se identifica por su step_code
    return mensaje["payload"].get("operation") or mensaje["step_code"]


def fecha_de(mensaje):
    return datetime.strptime(mensaje["timestamp"], "%Y/%m/%dT%H:%M:%S").date()


def es_lote_despachable(lote, fecha_pedido):
    if lote is None:
        return False
    if lote.get("status", "DISPONIBLE") == "BLOQUEADO":
        return False
    return date.fromisoformat(lote["expiry_date"]) >= fecha_pedido


def retro(mensaje, decision, regla=None, motivo=None, accion=None, **extra):
    """Retroalimentación estructurada común a todos los eventos."""
    resultado = {"msg_id": mensaje["msg_id"], "step_code": mensaje["step_code"],
                 "evento": tipo_evento(mensaje), "decision": decision}
    if regla:
        resultado["regla_fallida"] = regla
    if motivo:
        resultado["motivo"] = motivo
    if accion:
        resultado["accion_sugerida"] = accion
    resultado.update(extra)
    return resultado


class AgentePedidosStockPicking:
    def __init__(self, mensajes):
        # Lotes registrados en la entrada (CAPTURE_TRACEABILITY)
        self.lotes = {m["payload"]["batch_id"]: m["payload"]
                      for m in mensajes if tipo_evento(m) == "CAPTURE_TRACEABILITY"}
        self.pedido = None
        self.decision = None
        # Tipo de evento -> función que lo atiende
        self.manejadores = {
            "PROCESS_SALES_ORDER": self.procesar_pedido,
            "GW_RN01_RN02": self.validar_reglas,
            "ROW_LEVEL_LOCK_ALLOCATION": self.reservar_stock,
        }

    def atender(self, mensaje):
        if mensaje["line_id"] != OUTBOUND or mensaje["step_code"] in ("RF-07", "RF-08"):
            return None  # eventos que atienden otros agentes
        manejador = self.manejadores.get(tipo_evento(mensaje))
        if manejador is None:
            return retro(mensaje, "REVISAR", motivo="Evento no soportado por el agente",
                         accion="Dar de alta el evento en el agente")
        return manejador(mensaje)

    # RF-05
    def procesar_pedido(self, mensaje):
        p = mensaje["payload"]
        qty = p.get("requested_qty")
        if not p.get("sales_order_id") or type(qty) is not int or qty <= 0:
            return retro(mensaje, "RECHAZAR", motivo="Pedido incompleto o cantidad inválida",
                         accion="Corregir el pedido en el módulo de ventas")
        self.pedido = {"sales_order_id": p["sales_order_id"], "requested_qty": qty,
                       "fecha": fecha_de(mensaje)}
        return retro(mensaje, "CONTINUAR", sales_order_id=p["sales_order_id"])

    # GW_RN01_RN02
    def validar_reglas(self, mensaje):
        if self.pedido is None:
            return retro(mensaje, "RECHAZAR", motivo="Validación sin pedido previo",
                         accion="Reenviar PROCESS_SALES_ORDER")
        p = mensaje["payload"]
        lote = next(iter(self.lotes.values()), None)  # el JSON no indica qué lote surtir
        resultado = validar_salida(p["available_stock"], self.pedido["requested_qty"],
                                   es_lote_despachable(lote, self.pedido["fecha"]))
        self.decision = resultado["decision"]
        if resultado.get("motivo") == "Lote vencido o bloqueado":
            return retro(mensaje, "RECHAZAR", "RN-02", resultado["motivo"],
                         "Surtir de otro lote vigente o liberar el lote con Calidad",
                         batch_id=lote and lote["batch_id"])
        if resultado.get("motivo") == "Stock insuficiente":
            faltante = self.pedido["requested_qty"] - p["available_stock"]
            return retro(mensaje, "RECHAZAR", "RN-01", resultado["motivo"],
                         "Dejar el pedido pendiente y reabastecer el faltante",
                         disponible=p["available_stock"],
                         solicitado=self.pedido["requested_qty"], faltante=faltante)
        return retro(mensaje, "RESERVAR", sales_order_id=self.pedido["sales_order_id"],
                     reglas={"RN-01": "PASSED", "RN-02": "PASSED"})

    # RF-06
    def reservar_stock(self, mensaje):
        p = mensaje["payload"]
        if self.decision != "RESERVAR":
            return retro(mensaje, "RECHAZAR", motivo="Reserva sin validación aprobada",
                         accion="No bloquear stock hasta que RN-01 y RN-02 pasen")
        if p["reserved_qty"] != self.pedido["requested_qty"]:
            return retro(mensaje, "RECHAZAR", motivo="La cantidad reservada no coincide con el pedido",
                         accion="Reservar exactamente la cantidad solicitada")
        return retro(mensaje, "RESERVADO", item_id=p["item_id"], reserved_qty=p["reserved_qty"],
                     siguiente_paso="RF-07")


if __name__ == "__main__":
    import sys
    mensajes = cargar_mensajes(sys.argv[1] if len(sys.argv) > 1 else "eventos.json")
    agente = AgentePedidosStockPicking(mensajes)
    for mensaje in mensajes:
        respuesta = agente.atender(mensaje)
        if respuesta:
            print(json.dumps(respuesta, ensure_ascii=False))
```

Para ejecutarlo, con el script y `eventos.json` en la misma carpeta:

```bash
python agente_pedidos.py eventos.json
```

---

## 7. Qué tendría que ampliarse si llegan eventos nuevos

El agente no depende de un ejemplo fijo: decide qué hacer según el **tipo de evento**. Para atender uno nuevo, basta con agregar su función al diccionario `self.manejadores`, sin tocar las reglas existentes. Si llega un evento de salida que todavía no está dado de alta, responde `REVISAR` en lugar de fallar.

| Evento nuevo posible | Qué tendría que hacer el agente |
| --- | --- |
| Cancelación del pedido | Liberar el stock reservado con el mismo bloqueo DI-01. |
| Cambio de cantidad del pedido | Volver a validar RN-01 por la diferencia y ajustar la reserva. |
| Pedido con varios artículos | Validar RN-01 y RN-02 por artículo y reservar todo o nada. |
| Pedido que requiere varios lotes | Repartir la cantidad entre lotes vigentes, primero el que caduca antes. |
| Bloqueo de un lote por Calidad | Liberar las reservas de ese lote y revalidar los pedidos afectados. |

Además:

- **Validar campos obligatorios** de cada evento nuevo antes de aplicar reglas, por ejemplo `item_id` y las cantidades.
- **Ligar el lote al pedido:** cuando el JSON indique qué `batch_id` se surte, usar ese lote en lugar del único registrado.
- **Mantener el mismo formato de retroalimentación** (`msg_id`, `regla_fallida`, `motivo`, `accion_sugerida`) que los otros tres agentes.
