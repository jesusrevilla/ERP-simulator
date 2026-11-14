# Aportación al ERP-Simulator: módulo comercial (inventarios, compras y ventas)

**Alumno:** Cristian Ricardo Godinez Limones  
**Materia:** CNO VI Sistemas ERP  
**Grupo:** A26-T51A  
**Docente:** Mtro. Jesús Alberto Revilla Silva  
**Universidad:** Universidad Politécnica de San Luis Potosí  
**Fecha:** 10 de noviembre de 2026

## Objetivo y alcance

Implementar un prototipo funcional de operaciones comerciales para **TechAssembly S.A.**, empresa ficticia del caso ERP-Simulator. Se modelan productos, proveedores, clientes, compras, ventas e inventario, manteniendo reglas de negocio, trazabilidad y consistencia de datos.

La implementación usa **Python 3 y SQLite**, ambos disponibles sin instalar un servidor adicional. Es **independiente del MRP original**: no modifica el modelo PostgreSQL, los servicios MongoDB/Neo4j ni el workflow existente. Su integración con esos componentes queda como trabajo futuro.

## Archivos añadidos

| Archivo | Propósito |
|---|---|
| src/erp_comercial_cristian.py | Reglas comerciales, sesiones, roles, consultas y transacciones. |
| sql/comercial_schema_sqlite.sql | Esquema de usuarios, productos, socios, compras, ventas, movimientos y auditoría. |
| tests/test_erp_comercial_cristian.py | 31 pruebas unitarias, de flujo y de integridad. |
| demo_comercial.py | Ejemplo reproducible en consola. |
| documentacion/Cristian_Godinez_ERP_Simulator.md | Este documento. |

## Requisitos funcionales

| ID | Comportamiento cubierto |
|---|---|
| RF-01 | Inicio y cierre de sesión, con contraseñas almacenadas como hashes PBKDF2. |
| RF-02 | Roles administrador, compras, ventas y almacén; autorización por operación. |
| RF-03 | Alta, consulta, búsqueda y desactivación de productos con SKU, precio, costo y stock. |
| RF-04 | Registro de proveedores vinculados a compras. |
| RF-05 | Registro de clientes vinculados a ventas. |
| RF-06 | Recepciones en borrador y confirmadas que incrementan existencias. |
| RF-07 | Ventas en borrador y confirmadas, con descuento atómico de stock. |
| RF-08 | Movimientos de inventario consultables por producto. |
| RF-09 | Alertas cuando existencias son menores o iguales al mínimo. |
| RF-10 | Reportes de ventas y compras filtrables por periodo y SKU. |
| RF-11 | Cancelación de ventas, restitución única de stock y motivo obligatorio. |
| RF-12 | Rechazo de SKU repetido, cantidades inválidas, referencias inexistentes e importes fuera de rango. |

## Reglas de negocio

- **RN-01:** cada producto posee un SKU único.
- **RN-02:** precio mayor a cero y costos/existencias no negativos.
- **RN-03:** líneas comerciales con cantidades enteras positivas.
- **RN-04:** no se confirma venta sin disponibilidad suficiente.
- **RN-05:** productos inactivos no admiten nuevas operaciones.
- **RN-06:** recepción aumenta inventario únicamente al confirmarla.
- **RN-07:** venta descuenta inventario únicamente al confirmarla.
- **RN-08:** cancelación de venta única y justificada.
- **RN-09:** ajustes exclusivos de roles autorizados con motivo.
- **RN-10:** importes calculados en centavos exactos, evitando errores binarios de punto flotante.
- **RN-11:** referencias a productos y socios comerciales existentes.
- **RN-12:** auditoría histórica de movimientos sin borrado de ventas confirmadas.

## Modelo e integridad

El esquema utiliza tablas prefijadas con **commercial_** para evitar colisiones de nombres con el repositorio base. Hay claves primarias, restricciones **UNIQUE**, **CHECK**, **NOT NULL** y claves foráneas. Las confirmaciones de compras/ventas, cancelaciones y ajustes se ejecutan con transacciones **BEGIN IMMEDIATE**. Si una operación falla, se revierte el cambio completo, incluidos inventario, estado y movimientos.

El test de concurrencia intenta confirmar dos ventas de 7 unidades sobre un stock de 10. Se acepta como máximo una, preservando un stock final no negativo. Las ventas canceladas generan un movimiento compensatorio y no se pueden cancelar nuevamente.

## Ejecución

Desde la raíz del repositorio, con Python y pytest disponibles:

~~~bash
python demo_comercial.py
python -m pytest tests/test_erp_comercial_cristian.py -q
python -m pytest -v
~~~

Si pytest no está instalado: \`python -m pip install -r requirements.txt\`.

### Demostración esperada

~~~text
Compra borrador | Stock: 10
Compra confirmada | Stock: 18
Venta confirmada | Total: $375.00
Stock tras venta: 15
Venta cancelada | Stock: 18
Movimientos registrados: 4
Ventas en reporte: 1
~~~

### Validación local

- **31 pruebas aprobadas, 0 fallidas**, ejecutadas localmente el 10/11/2026.
- 12 casos unitarios (**PU**); 7 flujos de servicio (**PF**); 6 casos de integridad (**PI**) y 6 pruebas adicionales.
- Los casos PF prueban el flujo de negocio mediante Python, **no una interfaz gráfica**.
- No se afirma que se haya ejecutado todavía el workflow remoto de GitHub Actions.

## Flujo de operaciones

~~~mermaid
flowchart TD
    A[Inicio de sesión] --> B{Rol autorizado}
    B -- No --> Z[Operación denegada]
    B -- Sí --> C[Compra o venta en borrador]
    C --> D{Tipo}
    D -- Compra --> E[Confirmar recepción]
    E --> F[Sumar stock y registrar movimiento]
    D -- Venta --> G{Stock suficiente}
    G -- No --> Z
    G -- Sí --> H[Descontar stock y registrar movimiento]
    H --> I{Cancelar venta}
    I -- Sí --> J[Devolver stock una vez y auditar]
    I -- No --> K[Conservar venta confirmada]
    F --> L[Reporte e historial]
    J --> L
    K --> L
~~~

## Siguientes pasos

Integrar con PostgreSQL y las órdenes de venta del MRP existente; desarrollar endpoints y una interfaz para pruebas funcionales de usuario; y evaluar conexiones con los módulos de BOM, artículos e inventarios del repositorio original.

**Repositorio base:** https://github.com/jesusrevilla/ERP-simulator, rama \`development\`.
