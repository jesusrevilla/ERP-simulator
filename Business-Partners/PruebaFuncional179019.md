# Prueba Funcional: Business Partners (SAP Business One)

## Descripción del Módulo: Business Partners (Socios de Negocio)
Los **Business Partners** representan a las entidades externas con las que la empresa mantiene relaciones comerciales y financieras: **Clientes** (Customer), **Proveedores** (Supplier) y **Prospectos/Leads** (Lead). Su Dato Maestro centraliza información clave para la operación diaria: datos generales, condiciones de pago, moneda, límites de crédito, direcciones de facturación/entrega y cuentas contables asociadas.

---

## Caso de Prueba: BP-01 - Validación de límite de crédito y condición de pago en Cliente

* **Módulo:** Ventas - Clientes / Datos Maestros de Socio de Negocio
* **Objetivo:** Verificar que SAP Business One herede la condición de pago y aplique el control de límite de crédito configurado en el Dato Maestro de un Socio de Negocio (Cliente) al registrar un documento comercial.

### Precondiciones
1. Existe un Socio de Negocio tipo **Cliente** activo con **Límite de crédito** configurado en $10,000.00 (con advertencia o bloqueo activo en *Parametrizaciones generales*) y **Condición de pago** Crédito 30 días.
2. El cliente cuenta con un **Saldo de cuenta** actual de $8,500.00 por documentos abiertos previos.
3. Existe un artículo activo para venta con precio unitario de $500.00.

### Pasos de Ejecución

| Paso | Acción | Datos de Entrada | Resultado Esperado |
| :--- | :--- | :--- | :--- |
| 1 | Ingresar a **Ventas - Clientes > Pedido de cliente** (o Factura de clientes). | N/A | Se abre el formulario de creación del documento comercial. |
| 2 | Seleccionar el Socio de Negocio de prueba en la cabecera del documento. | Código de Cliente de prueba | Se cargan los datos del cliente y en la pestaña **Finanzas** se hereda automáticamente la condición Crédito 30 días. |
| 3 | Agregar una línea de detalle con el artículo configurado. | Artículo de prueba, Cantidad: 5, Precio: $500.00 | El total del documento calcula $2,500.00 (elevando la exposición total del cliente a $11,000.00). |
| 4 | Hacer clic en el botón **Crear** para registrar el documento. | N/A | El sistema detecta que $11,000.00 supera el límite de $10,000.00 y dispara la alerta o bloqueo de límite de crédito. |

### Resultado Esperado Final
SAP Business One aplica las reglas financieras definidas en el Dato Maestro del Socio de Negocio: hereda la condición de pago (Crédito 30 días) y detiene o advierte la creación del documento al excederse el límite de crédito ($8,500.00 de saldo + $2,500.00 del nuevo documento > $10,000.00), exigiendo autorización si el bloqueo está habilitado.
