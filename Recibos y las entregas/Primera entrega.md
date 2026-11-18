UNIVERSIDAD POLITÉCNICA DE SAN LUIS POTOSÍ
Sistemas ERP  
3er Parcial
Alumno: Domínguez Hernández Ailton Israel (182234)
Profesor: Jesús Alberto Revilla
Fecha de entrega: Martes, 3 de noviembre de 2026
---
1. Definición de requerimientos funcionales
Para el módulo de Recibos:
El sistema debe permitir registrar la llegada de mercancía relacionándola con una orden de compra previa.
El sistema debe permitir anotar si llegó la cantidad exacta, si faltaron piezas o si llegó producto dañado.
El sistema debe actualizar automáticamente el inventario sumando los nuevos productos recibidos en cuanto se apruebe el recibo.
Para el módulo de Entregas:
El sistema debe permitir seleccionar los productos que un cliente compró para armar su paquete de envío.
El sistema debe generar un comprobante o nota de salida de la mercancía que sale del almacén.
El sistema debe actualizar automáticamente el inventario restando los productos que ya fueron entregados.
---
2. Descripción de las reglas de negocio que aplican
Reglas para Recibos:
No recibir de más: No se puede aceptar en el almacén más cantidad de la que se pidió originalmente en la orden de compra (a menos que haya una autorización especial del gerente).
Proveedor activo: No se puede registrar un recibo de mercancía si el proveedor está dado de baja o suspendido en el sistema.
Reglas para Entregas:
Validación de inventario: No se puede confirmar una entrega si el almacén no cuenta con la cantidad física suficiente del producto (evitar vender lo que no hay).
Estado del pedido: Solo se pueden despachar productos de pedidos que estén previamente aprobados y pagados (o con crédito autorizado).
---
3. Pruebas unitarias
Probar componentes individuales aislados (ej. validar que la función de suma en inventarios o el cálculo de pesos funcione correctamente por separado).
---
4. Pruebas funcionales
Simular el proceso completo de principio a fin como lo haría un usuario (ej. desde registrar la llegada de una compra hasta ver reflejado el aumento en el inventario).
---
5. Integridad de los datos
Garantizar que los números cuadren ($\text{Entradas} - \text{Salidas} = \text{Stock actual}$) y que los registros cerrados no se puedan borrar ni alterar.


```mermaid
graph TD

    %% PISCINA: PROCESO DE GESTIÓN DE ALMACÉN (RECIBOS Y ENTREGAS)

    subgraph Almacen ["Piscina: Sistema de Gestión de Almacén"]
        
        %% ==========================================
        %% CARRIL 1: MÓDULO DE RECIBOS
        %% ==========================================
        subgraph Recibos ["Carril: Módulo de Recibos (Llegada de Mercancía)"]
            StartR(("● Inicio:<br/>Llegada de mercancía")) --> T1["Registrar llegada<br/>(Asociar con Orden de Compra)"]
            T1 --> T2["Verificar Estado del Proveedor"]
            
            T2 --> GW_Prov{"¿Proveedor Activo?"}
            GW_Prov -- No --> EndR_Cancel(("● Fin:<br/>Rechazar Recibo"))
            
            GW_Prov -- Sí --> T3["Anotar Cantidades:<br/>Exactas, Faltantes o Dañadas"]
            T3 --> GW_Cant{"¿Cantidad <= Pedido<br/>o Autorización Especial?"}
            
            GW_Cant -- No --> EndR_Exceso(("● Fin:<br/>Exceso No Autorizado"))
            
            GW_Cant -- Sí --> T4["Aprobar Recibo"]
            T4 --> T5["Actualizar Inventario:<br/>Sumar productos (+Stock)"]
            
            T5 -.-> DataInv[("Base de Datos:<br/>Inventario Actual")]
            T5 --> EndR_Success(("● Fin:<br/>Recibo Completado"))
        end

        %% ==========================================
        %% CARRIL 2: MÓDULO DE ENTREGAS
        %% ==========================================
        subgraph Entregas ["Carril: Módulo de Entregas (Despacho de Cliente)"]
            StartE(("● Inicio:<br/>Solicitud de Despacho")) --> T6["Verificar Estado del Pedido"]
            
            T6 --> GW_Ped{"¿Aprobado y Pagado<br/>o Crédito Autorizado?"}
            GW_Ped -- No --> EndE_Rechazado(("● Fin:<br/>Pedido no Autorizado"))
            
            GW_Ped -- Sí --> T7["Seleccionar Productos<br/>para Envíos"]
            T7 --> T8["Validar Stock Físico"]
            
            T8 -.-> DataInv
            T8 --> GW_Stock{"¿Stock Físico<br/>Suficiente?"}
            
            GW_Stock -- No --> EndE_SinStock(("● Fin:<br/>Stock Insuficiente"))
            
            GW_Stock -- Sí --> T9["Armar Paquete de Envío"]
            T9 --> T10["Generar Comprobante /<br/>Nota de Salida"]
            T10 --> T11["Actualizar Inventario:<br/>Restar productos (-Stock)"]
            
            T11 -.-> DataInv
            T11 --> EndE_Success(("● Fin:<br/>Entrega Completada"))
        end

    end

    %% ESTILOS BPMN
    classDef startEvent fill:#85e3a5,stroke:#2e7d32,stroke-width:2px,color:#000;
    classDef endEvent fill:#f8bbd0,stroke:#c62828,stroke-width:3px,color:#000;
    classDef activity fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#000,rx:5px,ry:5px;
    classDef gateway fill:#fff9c4,stroke:#fbc02d,stroke-width:2px,color:#000;
    classDef dataStore fill:#e1bee7,stroke:#6a1b9a,stroke-width:2px,color:#000;

    class StartR,StartE startEvent;
    class EndR_Cancel,EndR_Exceso,EndR_Success,EndE_Rechazado,EndE_SinStock,EndE_Success endEvent;
    class T1,T2,T3,T4,T5,T6,T7,T8,T9,T10,T11 activity;
    class GW_Prov,GW_Cant,GW_Ped,GW_Stock gateway;
    class DataInv dataStore;
```
