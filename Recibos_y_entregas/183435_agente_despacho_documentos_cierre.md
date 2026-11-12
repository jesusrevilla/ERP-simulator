# Agente de despacho, documentos y cierre

**Módulo:** Recibos y Entregas 

## 1. Objetivo del agente

Revisar que el pedido haya superado las validaciones previas, generar y comprobar los documentos de expedición, y permitir la confirmación de salida únicamente cuando el despacho esté listo.

Al confirmar la salida, el descuento de inventario y el asiento contable deben tratarse como una sola operación. Si cualquiera falla antes de confirmar, se debe revertir la operación completa conforme a DI-02 para evitar que el stock y los documentos queden en estados distintos.

## 2. Eventos que atiende

El flujo de salida del archivo `Recibos_y_entregas/eventos.json` muestra los eventos en este orden:

| Código | Evento | Operación observada |
|---|---|---|
| RF-07 | Generación de documentos de expedición | `EMIT_PACKING_LIST`; el ejemplo incluye `package_id` y `carrier`. Eln el requerimiento también se pide etiqueta de bulto y guía de embarque. |
| RF-08 | Confirmación de salida (Goods Issue) y contabilización | `GOODS_ISSUE_DISCOUNT_STOCK`; el mensaje incluye `sales_order_id` y estado del asiento. |

Antes de RF-07/RF-08, el flujo pasa por RF-05 (pedido de venta), validaciones RN-01/RN-02 y RF-06 (picking/reserva con DI-01). El agente verifica el resultado comunicado por esos pasos.

## 3. Datos, tablas o servicios que necesita consultar

### Datos y servicios participantes en el flujo

- **Evento de entrada:** `msg_id`, `step_code`, `payload.operation`, pedido de venta, identificador de bulto, transportista y resultados de validaciones.
- **ShippingService:** aparece como receptor de RF-07. Se usaría para generar o consultar la lista de empaque, etiqueta y guía.
- **AccountingEngine:** aparece como receptor de RF-08. Se usaría para registrar o confirmar el asiento de salida.
- **ERP/servicio de inventario:** debe aplicar el movimiento de salida y devolver el resultado de la transacción.

### Esquema SQL 

En `item/schema/schema.sql` se definen `Inventory_Stock` (existencia por artículo y almacén) y `Inventory_Transaction` (efecto y cantidad ligados a un movimiento). En `sql/Inventory_Movements.sql` se define `Inventory_Movements`, con tipo, cantidad, almacén de origen/destino, lote/serie y estado, relacionado con `Item_Master`.

También existe `sales_orders` en `sql/init.sql`, con identificador, producto y cantidad. Hay esquemas diferentes pero no hay una tabla única que relacione todos estos esquemas con RF-07/RF-08.

**No hay una tabla de Packing List/guías ni una tabla de asientos contables.** Por eso, se estan tratando como servicios o dependencias requeridas, no como tablas existentes. 

## 4. Reglas que aplica

1. Procesar el evento por su `step_code` y `payload.operation`; ignorar eventos que no sean RF-07 o RF-08.
2. Para RF-07, exigir que las validaciones previas de RN-01 (stock suficiente/no negativo) y RN-02 (lote utilizable) estén aprobadas, que el picking/reserva esté confirmado y que existan datos del pedido y transportista.
3. No considerar RF-07 completo hasta que el servicio confirme la generación de los documentos requeridos: lista de empaque, etiqueta y guía. Si un documento falla, no habilitar RF-08.
4. Para RF-08, exigir que RF-07 esté completo y que la salida física esté confirmada.
5. Descontar inventario y registrar el asiento dentro de una única transacción ACID (DI-02). Confirmar con `COMMIT` solo si ambas operaciones tienen éxito; ejecutar `ROLLBACK` ante cualquier error previo al commit.
6. Evitar procesar dos veces el mismo mensaje o confirmar dos veces la misma salida. Usar `msg_id` y/o un identificador de operación como clave de idempotencia, si el sistema lo soporta.
7. No modificar un documento contabilizado; RN-04 indica que las correcciones requieren un documento compensatorio autorizado.

## 5. Decisiones y retroalimentación que devuelve

La respuesta propuesta es estructurada para que el operador o el sistema identifique el evento, la regla aplicada y la acción necesaria:

- `CONTINUAR`: documentos verificados o cierre confirmado.
- `NO_CERRAR`: faltan validaciones, picking, documentos o confirmación física.
- `REVERTIR`: falló inventario o contabilización dentro de RF-08 y se ejecutó rollback.
- `NO_APLICA`: el evento no corresponde a RF-07/RF-08.
- `REQUIERE_REVISION`: no se conoce el estado real de la transacción, por ejemplo, ante un corte de conexión después de solicitar el commit. Consultar el estado por el identificador de operación antes de reintentar.

Campos de retroalimentación sugeridos: `msg_id`, `decision`, `rule_id`, `motivo`, `accion_sugerida` y `operation_id`.

## 6. Ejemplo

En este ejemplo se muestra la lógica de decisión. Las funciones de consulta, generación de documentos y transacción son dependencias que sirven para ejemplificar.

```python
def evaluar_evento(evento, estado):
    payload = evento.get("payload", {})
    operacion = payload.get("operation")
    codigo = evento.get("step_code")
    msg_id = evento.get("msg_id")

    if (codigo, operacion) not in {
        ("RF-07", "EMIT_PACKING_LIST"),
        ("RF-08", "GOODS_ISSUE_DISCOUNT_STOCK"),
    }:
        return {
            "msg_id": msg_id,
            "decision": "NO_APLICA",
            "rule_id": None,
            "motivo": "El evento no corresponde al agente de despacho y cierre.",
            "accion_sugerida": "Enrutar al agente responsable.",
        }

    if operacion == "EMIT_PACKING_LIST":
        validaciones_ok = (
            estado.get("rn01_stock_ok") is True
            and estado.get("rn02_lote_ok") is True
            and estado.get("picking_confirmado") is True
        )
        if not validaciones_ok:
            return {
                "msg_id": msg_id,
                "decision": "NO_CERRAR",
                "rule_id": "RN-01/RN-02/DI-01",
                "motivo": "Faltan validaciones previas o confirmación del picking.",
                "accion_sugerida": "Corregir o completar el paso previo indicado.",
            }

        if not payload.get("package_id") or not payload.get("carrier"):
            return {
                "msg_id": msg_id,
                "decision": "NO_CERRAR",
                "rule_id": "RF-07",
                "motivo": "Falta el identificador del bulto o el transportista.",
                "accion_sugerida": "Completar los datos de expedición.",
            }

        # Dependencia propuesta: confirmar que ShippingService generó
        # lista de empaque, etiqueta y guía.
        if estado.get("documentos_generados") is not True:
            return {
                "msg_id": msg_id,
                "decision": "NO_CERRAR",
                "rule_id": "RF-07",
                "motivo": "No se confirmó la generación de todos los documentos.",
                "accion_sugerida": "Revisar ShippingService y reintentar de forma segura.",
            }

        return {
            "msg_id": msg_id,
            "decision": "CONTINUAR",
            "rule_id": "RF-07",
            "motivo": "Documentos de expedición confirmados.",
            "accion_sugerida": "Esperar confirmación física para RF-08.",
        }

    if estado.get("rf07_completo") is not True:
        return {
            "msg_id": msg_id,
            "decision": "NO_CERRAR",
            "rule_id": "RF-07",
            "motivo": "RF-07 no está completo.",
            "accion_sugerida": "Generar y verificar los documentos de expedición.",
        }

    if estado.get("salida_fisica_confirmada") is not True:
        return {
            "msg_id": msg_id,
            "decision": "NO_CERRAR",
            "rule_id": "RF-08",
            "motivo": "La salida física aún no está confirmada.",
            "accion_sugerida": "Confirmar el despacho en el andén.",
        }

    # esta operación debe agrupar el descuento
    # de inventario y el asiento contable en una única transacción ACID.
    resultado = ejecutar_goods_issue_y_asiento_atomicos(
        sales_order_id=payload.get("sales_order_id"),
        operation_id=msg_id,
    )

    if resultado.get("commit") is True:
        return {
            "msg_id": msg_id,
            "decision": "CONTINUAR",
            "rule_id": "DI-02",
            "motivo": "Inventario y asiento quedaron confirmados juntos.",
            "accion_sugerida": "Cerrar el despacho.",
        }

    if resultado.get("rollback") is True:
        return {
            "msg_id": msg_id,
            "decision": "REVERTIR",
            "rule_id": "DI-02",
            "motivo": resultado.get("error", "Falló inventario o contabilización."),
            "accion_sugerida": "Verificar que no se confirmó ningún efecto parcial y reportar el error.",
        }

    return {
        "msg_id": msg_id,
        "decision": "REQUIERE_REVISION",
        "rule_id": "DI-02",
        "motivo": "No se pudo determinar el resultado final de la operación.",
        "accion_sugerida": "Consultar el estado por operation_id antes de reintentar.",
    }
```

En el ejemplo de RF-08, el nombre `ejecutar_goods_issue_y_asiento_atomicos` representa una interfaz que tendría que implementarse. Para cumplir DI-02, el servicio debe poder revertir tanto el movimiento de inventario como el asiento si ambos pertenecen a la misma base de datos/transacción. Si intervienen servicios externos, el equipo debe definir una estrategia de confirmación/reversión e idempotencia; no se debe afirmar que un rollback SQL revierte por sí solo una operación remota.
