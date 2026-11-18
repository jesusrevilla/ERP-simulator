Sección A/R y A/P

Descripción:

Cuentas por Cobrar y por Pagar
A/R, Accounts Receivable

A/P, Accounts Payable

Funcionalidades principales:

Catálogo de clientes y proveedores 

Registro de facturas de venta (A/R) y facturas de compra (A/P).

Registro y aplicación de cobros (A/R) y pagos (A/P), totales o parciales

Notas de crédito y notas de débito

Cálculo de fechas de vencimiento 

Estado de cuenta por cliente/proveedor.

Integración con otros módulos 

reglas de negocio

Toda factura pertenece a un cliente/proveedor activo

El folio es único por cliente/proveedor

Un pago no puede exceder el saldo de la factura

Un pago puede aplicarse a varias facturas del mismo cliente/proveedor

Toda cancelación o ajuste requiere motivo y queda en bitácora

integridad de los datos

llaves primarias en todas las tablas; RFC único; (proveedor + folio) único

…

Requerimientos no funcionales

Rendimiento Registrar una factura o un pago responde en menos de 2 s.

Disponibilidad Disponible 99% del tiempo en horario laboral

Usabilidad 	Mensajes de error claros y validaciones en pantalla
Pruebas funcionales

Alta de cliente

Registrar factura A/R

Registrar factura A/P

Dos usuarios pagan la misma factura a ala ve

```mermaid
flowchart TD
    A((Inicio)) --> B{"¿Qué operación?"}

    B -- Alta --> C["Registrar cliente / proveedor"]
    C --> D{"¿RFC único?"}
    D -- No --> X["Mostrar error"]
    D -- Sí --> E["Guardar cliente / proveedor"]

    B -- Factura --> F["Capturar factura A/R o A/P"]
    F --> G{"¿Cliente / proveedor activo<br/>y folio único?"}
    G -- No --> X
    G -- Sí --> H["Calcular fecha de vencimiento"]
    H --> I["Guardar factura"]

    B -- Cobro / Pago --> J["Capturar cobro o pago"]
    J --> K{"¿Monto ≤ saldo<br/>de la factura?"}
    K -- No --> X
    K -- Sí --> L["Aplicar a una o varias facturas<br/>y actualizar saldo"]

    B -- Nota / Ajuste --> M["Capturar nota de crédito / débito,<br/>cancelación o ajuste"]
    M --> N{"¿Tiene motivo?"}
    N -- No --> X
    N -- Sí --> O["Aplicar y guardar en bitácora"]

    B -- Estado de cuenta --> P["Generar estado de cuenta"]

    E --> Z(((Fin)))
    I --> Z
    L --> Z
    O --> Z
    P --> Z
    X --> Z
´´´
