# Agente de despacho, documentos y cierre

## Objetivo del agente

El agente revisa si un despacho puede avanzar a su cierre. Comprueba que las validaciones previas hayan pasado, que exista un picking válido, que los documentos de envío estén confirmados y que la salida no se cierre si el inventario y el asiento contable aparecen en estados distintos.

## Eventos que atiende

- **RF-07:** generación y confirmación de la lista de empaque, etiqueta y guía.
- **RF-08:** confirmación de la salida y revisión del resultado de inventario y contabilidad.

Los pasos previos de validación y picking se consultan como antecedentes para decidir si RF-07 puede continuar.

## Datos o servicios que consulta

Obtiene los eventos de `Recibos_y_entregas/eventos.json`. Revisa los estados previos, la reserva de picking, los datos del bulto y transportista, la generación de documentos y el resultado reportado para inventario y contabilidad.

El grafo del ejemplo se guarda en Neo4j como pasos de despacho y relaciones de secuencia.

## Reglas que aplica

- No continuar si las validaciones previas no están aprobadas.
- No generar el cierre si falta un picking válido.
- RF-07 requiere los datos de expedición y los documentos confirmados.
- RF-08 solo puede completar el cierre cuando inventario y asiento contable se confirman juntos.
- Si la transacción reporta rollback, verificar que no haya quedado un efecto parcial.
- Si el estado conjunto no puede comprobarse, detener el cierre y solicitar revisión para evitar repetir una salida.

Estas reglas siguen el principio de DI-02: ambos efectos se confirman juntos o se revierten juntos.

## Decisiones y retroalimentación

El agente devuelve una decisión, la regla revisada, el motivo y una acción sugerida. Puede indicar que no se cierre, que está listo para confirmar, que se continúe tras la confirmación conjunta, que se revierta o que el resultado requiere revisión.

## Ejemplo

~~~python
def validar_cierre(validaciones_ok, documentos_generados,
                   inventario_confirmado, asiento_confirmado):
    if not validaciones_ok:
        return {"decision": "NO_CERRAR",
                "motivo": "Hay validaciones pendientes"}
    if not documentos_generados:
        return {"decision": "NO_CERRAR",
                "motivo": "Faltan documentos de despacho"}
    if inventario_confirmado and asiento_confirmado:
        return {"decision": "CONTINUAR"}
    return {"decision": "REQUIERE_REVISION",
            "motivo": "Inventario y contabilidad no se confirmaron juntos"}
~~~


## Ampliación para eventos nuevos

Si se agregan eventos, el flujo debe identificarlos por su código y tipo de operación, y no depender de que solo exista un ejemplo fijo. Para los nuevos eventos se deberán documentar sus datos requeridos, reglas, estados posibles y acciones de retroalimentación. La respuesta debe conservar el identificador del mensaje, la regla que falló, el motivo y la acción sugerida.
