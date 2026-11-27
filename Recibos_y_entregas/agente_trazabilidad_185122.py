
import os
import json
import psycopg2
from psycopg2 import sql
from datetime import date


def conectar_bd():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        database=os.getenv("POSTGRES_DB", "erpdb"),
        user=os.getenv("POSTGRES_USER", "erp"),
        password=os.getenv("POSTGRES_PASSWORD", "erp")
    )



def buscar_articulo(codigo):
    conexion = conectar_bd()
    cursor = conexion.cursor()

    tablas = ["products", "materials"]
    columnas_codigo = [
        "code", "sku", "item_code",
        "product_code", "material_code"
    ]

    try:
        for tabla in tablas:
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = %s
            """, (tabla,))

            columnas = [fila[0] for fila in cursor.fetchall()]

            columna_codigo = next(
                (c for c in columnas_codigo if c in columnas),
                None
            )

            if columna_codigo:
                consulta = sql.SQL(
                    "SELECT * FROM {} WHERE {} = %s LIMIT 1"
                ).format(
                    sql.Identifier(tabla),
                    sql.Identifier(columna_codigo)
                )

                cursor.execute(consulta, (codigo,))

                if cursor.fetchone():
                    return True

        return False

    finally:
        cursor.close()
        conexion.close()


def validar_trazabilidad(evento):
    alertas = []

    grafo = {
        "INICIO": "ARTICULO",
        "ARTICULO": "TRAZABILIDAD",
        "TRAZABILIDAD": "UBICACION",
        "UBICACION": "FIN"
    }

    estado = "INICIO"

    while estado != "FIN":
        siguiente = grafo[estado]

        if siguiente == "ARTICULO":
            if not buscar_articulo(evento["item_code"]):
                alertas.append("El artículo no existe en la base de datos.")
                break

        elif siguiente == "TRAZABILIDAD":
            reglas = evento.get("item_rules", {})
            cantidad = evento.get("received_qty", 0)

            if reglas.get("requires_lot"):
                if not evento.get("lot_id"):
                    alertas.append("Falta registrar el lote.")

            if reglas.get("requires_serial"):
                series = evento.get("serial_numbers", [])

                if len(series) != cantidad:
                    alertas.append(
                        "La cantidad de números de serie no coincide "
                        "con la cantidad recibida."
                    )

                if any(not serie for serie in series):
                    alertas.append("Hay números de serie vacíos.")

                if len(series) != len(set(series)):
                    alertas.append("Existen números de serie duplicados.")

            if reglas.get("requires_expiry"):
                vencimiento = evento.get("expiry_date")

                try:
                    fecha = date.fromisoformat(vencimiento)

                    if fecha < date.today():
                        alertas.append("El producto está caducado.")

                except (ValueError, TypeError):
                    alertas.append("La fecha de caducidad no es válida.")

        elif siguiente == "UBICACION":
            ubicacion = evento.get("location_code")
            ubicaciones = evento.get("valid_locations", [])

            if not ubicacion:
                alertas.append("No se indicó una ubicación.")

            elif ubicacion not in ubicaciones:
                alertas.append("La ubicación propuesta no es válida.")

        if alertas:
            break

        estado = siguiente

    if alertas:
        return {
            "resultado": "RECHAZAR",
            "alertas": alertas
        }

    return {
        "resultado": "CONTINUAR",
        "mensaje": "Trazabilidad y ubicación validadas correctamente."
    }


def main():
    evento = json.loads(os.environ["EVENTO_JSON"])

    if evento.get("event_type") not in [
        "CAPTURE_TRACEABILITY",
        "ASSIGN_BIN_LOCATION"
    ]:
        print("Tipo de evento no reconocido.")
        raise SystemExit(1)

    if not evento.get("item_code"):
        print("Falta el código del artículo.")
        raise SystemExit(1)

    resultado = validar_trazabilidad(evento)

    print(json.dumps(resultado, indent=4, ensure_ascii=False))

    if resultado["resultado"] == "RECHAZAR":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
