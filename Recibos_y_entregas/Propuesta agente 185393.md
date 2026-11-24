# Agente de validación de recepción de compras

## 1. Objetivo del agente

Verificar que los productos recibidos de un proveedor cumplan con las condiciones de la orden de compra antes de permitir su ingreso al inventario.

El agente revisa que la orden exista, esté aprobada, que el proveedor se encuentre activo y que las cantidades recibidas sean correctas. Su función es detectar errores y evitar que se registren productos que no cumplen con las condiciones establecidas.

## 2. Eventos que atiende

El agente participa en los eventos relacionados con la recepción de productos:

- **`GET_PURCHASE_ORDER`:** Consulta la orden de compra para comprobar que exista y esté aprobada.
- **Eventos de recepción de mercancía:** Revisa las cantidades recibidas y las compara con las solicitadas en la orden de compra.

Estos eventos forman parte del proceso de recepción de compras. El código RF específico deberá asociarse con el requerimiento correspondiente del módulo.

## 3. Datos o tablas que necesita consultar

Para realizar las validaciones, el agente necesita consultar tres fuentes principales:

| Tabla | Información que consulta |
|---|---|
| Orden de compra | Identificador, estado de aprobación y cantidades solicitadas. |
| Proveedor | Identificador y estado actual del proveedor. |
| Detalle de artículos | Productos incluidos en la orden, cantidades solicitadas y cantidades recibidas. |

Esta información permite comprobar que la recepción corresponda con una compra autorizada.

## 4. Reglas que aplica

El agente debe cumplir las siguientes reglas:

1. **Existencia de la orden:** La orden de compra debe estar registrada en el sistema.
2. **Aprobación:** Solo se pueden recibir productos de órdenes aprobadas.
3. **Proveedor activo:** El proveedor debe encontrarse activo.
4. **Verificación de artículos:** Los productos recibidos deben corresponder con los incluidos en la orden.
5. **Validación de cantidades:** La cantidad recibida no debe superar la cantidad pendiente, considerando la tolerancia permitida.
6. **Exceso de productos:** Si la cantidad recibida supera la tolerancia, el agente debe generar una alerta y solicitar autorización antes de continuar.

La tolerancia debe ser definida por las reglas del sistema y no por el agente.

## 5. Decisiones y retroalimentación que devuelve

Después de revisar la información, el agente puede devolver tres decisiones:

- **`CONTINUAR`:** La recepción cumple con todas las condiciones.
- **`RECHAZAR`:** Existe un problema que impide continuar con la recepción.
- **`SOLICITAR_AUTORIZACION`:** La cantidad recibida supera el límite permitido y necesita revisión.

### Ejemplos de retroalimentación

| Situación | Decisión | Mensaje |
|---|---|---|
| La orden no existe | `RECHAZAR` | No se encontró la orden de compra. |
| La orden no está aprobada | `RECHAZAR` | La orden de compra no está aprobada. |
| El proveedor está inactivo | `RECHAZAR` | El proveedor no se encuentra activo. |
| El artículo no pertenece a la orden | `RECHAZAR` | El artículo no está registrado en la orden. |
| La cantidad supera la tolerancia | `SOLICITAR_AUTORIZACION` | La cantidad recibida supera el límite permitido. |
| Todos los datos son correctos | `CONTINUAR` | Recepción validada correctamente. |

La retroalimentación también debe incluir el identificador del mensaje, la regla que se incumplió y la acción sugerida para corregir el problema.

## 6. Fragmento de código de ejemplo

El siguiente ejemplo muestra cómo el agente puede validar una recepción mediante Python.

```python
def validar_recepcion(evento, orden, proveedor):

    if not orden:
        return {
            "decision": "RECHAZAR",
            "motivo": "La orden de compra no existe"
        }

    if orden["status"] != "Approved":
        return {
            "decision": "RECHAZAR",
            "motivo": "La orden no está aprobada"
        }

    if not proveedor or proveedor["status"] != "Active":
        return {
            "decision": "RECHAZAR",
            "motivo": "El proveedor no está activo"
        }

    articulo = evento["payload"]["article_id"]
    cantidad = evento["payload"]["quantity"]

    if articulo not in orden["articulos"]:
        return {
            "decision": "RECHAZAR",
            "motivo": "El artículo no pertenece a la orden"
        }

    if cantidad <= 0:
        return {
            "decision": "RECHAZAR",
            "motivo": "La cantidad debe ser mayor a cero"
        }

    pendiente = orden["articulos"][articulo]["pendiente"]
    tolerancia = orden["articulos"][articulo]["tolerancia"]

    if cantidad > pendiente + tolerancia:
        return {
            "decision": "SOLICITAR_AUTORIZACION",
            "motivo": "Cantidad superior a la permitida"
        }

    return {
        "decision": "CONTINUAR",
        "motivo": "Recepción validada correctamente"
    }
```

**Explicación del funcionamiento:**

El agente comienza comprobando la existencia y aprobación de la orden de compra. Después verifica el estado del proveedor y que el artículo pertenezca a la orden.

Finalmente, compara la cantidad recibida con la cantidad pendiente y la tolerancia permitida. Si encuentra algún problema, devuelve un mensaje indicando el motivo. Si todo es correcto, permite continuar con el proceso.

### Ejemplo práctico

Supongamos que una empresa tiene una orden de compra con las siguientes condiciones:

- Cantidad pendiente: 100 unidades.
- Tolerancia permitida: 5 unidades.
- Proveedor: activo.
- Orden de compra: aprobada.

**Caso 1:** Se reciben 103 unidades.

El agente permite continuar porque la cantidad se encuentra dentro del límite permitido de 105 unidades.

**Caso 2:** Se reciben 110 unidades.

El agente devuelve `SOLICITAR_AUTORIZACION`, ya que se supera la tolerancia establecida.

**Caso 3:** Se reciben 100 unidades, pero la orden no está aprobada.

El agente devuelve `RECHAZAR`, porque la recepción no cumple con las condiciones necesarias.

## 7. Qué tendría que ampliarse si llegan eventos nuevos

Si se agregan nuevos eventos al sistema, el agente deberá poder reconocerlos y realizar las validaciones correspondientes.

Algunas posibles ampliaciones son:

- **Recepciones parciales:** Revisar las cantidades pendientes cuando los productos lleguen en varias entregas.
- **Cancelación de órdenes:** Evitar recepciones relacionadas con órdenes canceladas.
- **Devoluciones:** Identificar productos devueltos y comprobar su relación con la compra original.
- **Nuevas autorizaciones:** Permitir que un responsable apruebe cantidades superiores a las establecidas.
- **Nuevos eventos:** Identificar el tipo de operación y aplicar las reglas correspondientes, sin depender de un solo evento.
