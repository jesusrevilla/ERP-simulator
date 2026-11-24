import psycopg2
from psycopg2 import DatabaseError

class GestorCompensacionERP:
    """
    Agente encargado de la reversión segura de operaciones (Patrón Saga transaccional).
    Garantiza que al cancelar una venta, el inventario regrese, la deuda se cancele
    y la contabilidad refleje la partida doble inversa, evitando deadlocks.
    """
    def __init__(self, db_connection):
        self.conn = db_connection

    def ejecutar_cancelacion_venta(self, folio_venta, id_cliente, carrito_devuelto, total, subtotal, iva, usuario):
        """
        Cancela una venta aplicando reversión de inventario y contra-póliza contable.
        :param carrito_devuelto: lista de diccionarios [{'id_producto': int, 'cantidad': numeric}]
        """
        cursor = self.conn.cursor()
        try:
            # 1. Validación de Integridad Financiera en memoria (Pre-Commit)
            # Evita procesar transacciones descuadradas desde el frontend
            if abs(total - (subtotal + iva)) > 0.01:
                raise ValueError("Inconsistencia financiera: El total a revertir no cuadra con subtotal + IVA.")

            # 2. Iniciar transacción explícita
            cursor.execute("BEGIN;")

            # 3. PREVENCIÓN DE DEADLOCKS (Crucial para concurrencia)
            # Ordenar los IDs de menor a mayor asegura que múltiples transacciones 
            # bloqueen las filas en el mismo orden, evitando abrazos mortales en PostgreSQL.
            productos_ordenados = sorted(carrito_devuelto, key=lambda x: x['id_producto'])

            # 4. Bloqueo Pesimista (FOR UPDATE) y reintegración de inventario
            for item in productos_ordenados:
                id_prod = item['id_producto']
                cant_devolver = item['cantidad']
                
                # Bloquear fila específica del producto
                cursor.execute(
                    "SELECT existencia FROM inventario WHERE id_producto = %s FOR UPDATE;", 
                    (id_prod,)
                )
                if not cursor.fetchone():
                    raise ValueError(f"Violación de integridad: El producto {id_prod} no existe.")

                # Reintegrar las unidades al stock
                cursor.execute(
                    "UPDATE inventario SET existencia = existencia + %s WHERE id_producto = %s;",
                    (cant_devolver, id_prod)
                )

            # 5. Cancelación de la Cuenta por Cobrar
            # En lugar de borrar, se actualiza el estatus para mantener trazabilidad
            cursor.execute(
                "UPDATE cuenta_por_cobrar SET estatus = 'CANCELADO' WHERE folio = %s AND id_cliente = %s;",
                (folio_venta, id_cliente)
            )

            # 6. Asiento Contable de Reverso (Contra-póliza)
            # En contabilidad real no se borran pólizas, se hace el movimiento inverso.
            # Lo que antes fue un cargo, ahora es abono, y viceversa.
            folio_reverso = f"REV-{folio_venta}"
            cursor.execute(
                """INSERT INTO poliza_detalle (id_poliza, cuenta, cargo, abono) VALUES 
                   (%s, 'Ventas', %s, 0),
                   (%s, 'IVA trasladado', %s, 0),
                   (%s, 'Clientes', 0, %s);""",
                (folio_reverso, subtotal, folio_reverso, iva, folio_reverso, total)
            )

            # 7. Bitácora de Auditoría (Regla RN-11)
            cursor.execute(
                "INSERT INTO bitacora (usuario, fecha, accion, documento) VALUES (%s, NOW(), 'CANCELAR_VENTA', %s);",
                (usuario, folio_venta)
            )

            # 8. Confirmar todos los cambios
            self.conn.commit()
            return {"status": "exito", "mensaje": f"Venta {folio_venta} revertida. Inventario y contabilidad ajustados."}

        except (Exception, DatabaseError) as error:
            # 9. Reversión total si cualquier paso falla
            self.conn.rollback()
            return {"status": "error", "mensaje": f"Fallo en la compensación (ROLLBACK): {str(error)}"}
        finally:
            cursor.close()
