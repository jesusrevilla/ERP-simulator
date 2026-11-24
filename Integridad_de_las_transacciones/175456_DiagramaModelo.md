#Titulo

'''mermaid

flowchart TD
    %%Ortiz Castro Juan Daniel 175456
    classDef startEvent fill:#d4edda,stroke:#28a745,stroke-width:2px;
    classDef endEvent fill:#f8d7da,stroke:#dc3545,stroke-width:3px;
    classDef endSuccess fill:#d4edda,stroke:#28a745,stroke-width:3px;
    classDef task fill:#e2f0d9,stroke:#5c8141,stroke-width:1px;
    classDef gateway fill:#fff3cd,stroke:#ffc107,stroke-width:2px;

    
    subgraph Ventas [Módulo de Ventas]
        direction TB
        Inicio(((Inicio))) --> V1[Capturar pedido de venta]
        V1 --> G1{¿Cliente y<br>crédito válidos?}
        G1 -- No --> Error1(((Rechazo Pedido)))
        G1 -- Sí --> V2[Confirmar pedido]
    end

    
    subgraph Inventarios [Módulo de Inventarios]
        direction TB
        V2 --> I1[Bloquear registro de producto]
        I1 --> I2[Validar existencia disponible]
        I2 --> G2{¿Existencia >= Cantidad?}
        G2 -- No --> Rollback1[Revertir transacción/ROLLBACK]
        G2 -- Sí --> I3[Descontar inventario]
    end

    
    subgraph CuentasCobrar [Módulo de Cuentas por Cobrar]
        direction TB
        I3 --> C1[Registrar cuenta por cobrar / Factura]
    end

    
    subgraph Contabilidad [Módulo de Contabilidad]
        direction TB
        C1 --> Co1[Generar póliza contable balanceada]
    end

    
    subgraph Auditoria [Motor de Base de Datos / Sistema]
        direction TB
        Co1 --> S1[Registrar en bitácora de auditoría]
        S1 --> S2[Confirmar transacción/COMMIT]
        S2 --> FinExito(((Éxito)))
        
        Rollback1 --> FinError(((Fin)))
    end

    
    class Inicio startEvent;
    class FinExito endSuccess;
    class Error1,FinError endEvent;
    class G1,G2 gateway;
'''
