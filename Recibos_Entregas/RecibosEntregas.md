# Especificación Funcional: Módulo de Recibos y Entregas
## Proyecto: ERP Simulator

Este documento detalla la especificación técnica y funcional para el subproceso de **Gestión de Recibos (Inbound)** y **Entregas (Outbound)** dentro del ecosistema del simulador de ERP[cite: 1].

---

### 1. Requerimientos Funcionales
* **Recepción (Inbound):** Registrar entradas parciales o totales vinculadas a una Orden de Compra (OC)[cite: 1].
* **Inventario:** Actualizar automáticamente el stock al confirmar el documento[cite: 1].
* **Entrega (Outbound):** Procesar salidas ligadas a una Orden de Venta (OV) y emitir guías de despacho[cite: 1].
* **Incidencias:** Permitir el registro de discrepancias (faltantes o mercancía dañada)[cite: 1].

---

### 2. Reglas de Negocio
* **RN-01 (Estados):** Solo se recibe mercancía si la OC está en estado *Emitida/Aprobada*[cite: 1].
* **RN-02 (Sobre-recepción):** Bloqueo si excede lo pendiente (salvo tolerancia permitida)[cite: 1].
* **RN-03 (Stock Mínimo):** Se prohíben entregas si el stock es menor al solicitado (evita inventarios negativos)[cite: 1].
* **RN-04 (Inmutabilidad):** Los registros confirmados no se pueden editar; requieren notas de crédito o ajustes[cite: 1].

---

### 3. Pruebas Unitarias
* **PU-01:** Validación de sumatoria exacta en `actualizarStockEntrada`[cite: 1].
* **PU-02:** Verificación de límites en la recepción (`cantidadRecibida` vs `cantidadPendienteOC`)[cite: 1].
* **PU-03:** Comprobación del descuento correcto en `procesarSalidaInventario`[cite: 1].
* **PU-04:** Bloqueo de cambios en documentos con estado *Completado*[cite: 1].

---

### 4. Pruebas Funcionales
* **PF-01 (Inbound):** Ciclo completo de OC $\rightarrow$ Recibo Parcial $\rightarrow$ Cierre de OC[cite: 1].
* **PF-02 (Outbound):** Ciclo completo de OV $\rightarrow$ Verificación de stock $\rightarrow$ Despacho[cite: 1].
* **PF-03 (Excepciones):** Bloqueo automático ante intentos de entrega con stock insuficiente[cite: 1].
* **PF-04 (Incidencias):** Exclusión de productos dañados del stock disponible y generación de alertas[cite: 1].

---

### 5. Integridad de los Datos
* **Transaccionalidad ACID:** Uso estricto de bloques transaccionales (`COMMIT` / `ROLLBACK`) para evitar desincronizaciones[cite: 2].
* **Llaves Foráneas (FK):** Enlace obligatorio de productos, bodegas y detalles de movimiento[cite: 2].
* **Restricciones (CHECK):** Garantía a nivel de base de datos de que las cantidades y stocks sean $\ge 0$[cite: 2].
* **Auditoría:** Registro obligatorio de trazabilidad (`usuario_id`, `fecha_hora_creacion`, `estado_registro`)[cite: 2].


  
```mermaid
flowchart TD
    subgraph Inbound ["Proceso Inbound (Recepción)"]
        A1["🚚 Inicio: Recepción de Mercancía"] --> A2{"📋 RN-01: ¿OC Emitida / Aprobada?"}
        A2 -- No --> A3["⛔ Bloqueo / Rechazar Recibo"]
        A2 -- Sí --> A4["📄 Registrar Entrada Parcial o Total"]
        A4 --> A5{"⚖️ RN-02: ¿Excede Cantidad Pendiente?"}
        A5 -- Sí --> A6["⚠️ Bloqueo por Sobre-recepción"]
        A5 -- No --> A7{"❓ ¿Existen Discrepancias / Daños?"}
        A7 -- Sí --> A8["🛠️ Registrar Incidencia / Excluir Dañados"]
        A7 -- No --> A9["✅ Confirmar Recibo y Actualizar Stock"]
        A8 --> A9
    end

    subgraph Outbound ["Proceso Outbound (Entrega)"]
        B1["🚀 Inicio: Solicitud de Despacho"] --> B2{"📦 RN-03: ¿Stock Disponible >= Solicitado?"}
        B2 -- No --> B3["❌ Bloqueo: Stock Insuficiente"]
        B2 -- Sí --> B4["🛒 Procesar Salida de Inventario"]
        B5["📋 Emitir Guía de Despacho"]
        B4 --> B5
    end

    subgraph DataIntegrity ["Integridad de Datos y Transaccionalidad"]
        C1["🗄️ Bloque Transaccional ACID"] --> C2{"⚡ ¿Falla la Operación?"}
        C2 -- Sí --> C3["🔄 Ejecutar ROLLBACK"]
        C2 -- No --> C4["💾 Ejecutar COMMIT"]
        C5["🛡️ Aplicar FK, Restricciones CHECK >= 0 y Auditoría"]
        C4 --> C5
    end

    A9 --> C1
    B5 --> C1
