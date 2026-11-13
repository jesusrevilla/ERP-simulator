# Agente 2: Agente de trazabilidad y ubicación

## 1. Objetivo del agente

El objetivo de este agente es verificar que los artículos recibidos tengan correctamente registrada su información de trazabilidad y que cuenten con una ubicación válida dentro del almacén.

Su función es evitar que se registren artículos sin los datos necesarios para identificarlos y localizarlos posteriormente.

## 2. Eventos que atiende

El agente participa en dos actividades del proceso de recepción:

- **RF-02 – Capturar número de lote, serie y fecha de caducidad:** Revisa el evento `CAPTURE_TRACEABILITY` para comprobar que los datos de identificación del artículo estén completos.
- **RF-03 – Asignar ubicación automática (Putaway):** Revisa el evento `ASSIGN_BIN_LOCATION` para comprobar que la ubicación propuesta sea válida para el artículo.

## 3. Datos que necesita consultar

Para realizar sus validaciones, el agente utiliza los siguientes datos:

- **Maestro de artículos:** Consulta si el artículo requiere número de lote, número de serie o fecha de caducidad.
- **Lotes:** Verifica que el lote proporcionado exista y corresponda al artículo recibido.
- **Series:** Comprueba que los números de serie estén registrados y que su cantidad coincida con las unidades recibidas.
- **Ubicaciones:** Consulta las ubicaciones disponibles y verifica que sean compatibles con el artículo.

## 4. Reglas de validación

El agente aplica las siguientes reglas:

1. **Validación de lote:** Si el artículo requiere lote, comprueba que se haya proporcionado un número de lote válido.
2. **Validación de series:** Si el artículo requiere números de serie, verifica que se registre uno por cada unidad recibida.
3. **Validación de caducidad:** Si el artículo requiere fecha de caducidad, comprueba que el dato esté presente y sea válido.
4. **Validación de ubicación:** Comprueba que la ubicación propuesta exista y que esté permitida para almacenar el artículo.
5. **Resultado:** Si toda la información es correcta, permite continuar con el proceso. Si encuentra algún problema, rechaza la validación y genera una alerta.

## 5. Ejemplos de alertas

| Situación | Alerta |
|---|---|
| Faltan números de serie | La cantidad de números de serie no coincide con las unidades recibidas. |
| Falta el número de lote | El artículo requiere un lote para su identificación. |
| Falta la fecha de caducidad | No se proporcionó la fecha de caducidad obligatoria. |
| Lote inexistente | El lote indicado no se encuentra registrado para este artículo. |
| Ubicación incorrecta | La ubicación propuesta no es válida para el artículo recibido. |

## 6. Ejemplo de código

El siguiente código representa una parte de las validaciones que realizaría el agente:

```python
def validar_trazabilidad(evento, requiere_serie, cantidad_recibida):
    payload = evento["payload"]

    series = payload.get("serial_numbers", [])

    if requiere_serie and len(series) != cantidad_recibida:
        return {
            "decision": "RECHAZAR",
            "motivo": "La cantidad de series no coincide"
        }

    return {"decision": "CONTINUAR"}
```

**Aplicación al JSON del proyecto:**

En el evento `CAPTURE_TRACEABILITY` se registra el artículo `PROD-001`, que requiere números de serie. Sin embargo, en el proceso de recepción se indican 105 unidades recibidas y solamente aparecen tres números de serie.

Por lo tanto, el agente detectaría que faltan 102 números de serie y devolvería una alerta, evitando que el proceso continúe con información incompleta.

## 7. Decisiones y retroalimentación

El agente puede devolver dos resultados:

- **CONTINUAR:** Cuando los datos de trazabilidad están completos y la ubicación es válida.
- **RECHAZAR:** Cuando falta información obligatoria o la ubicación propuesta no cumple con las condiciones del artículo.

En caso de rechazo, informa qué dato necesita corregirse para que el proceso pueda continuar.