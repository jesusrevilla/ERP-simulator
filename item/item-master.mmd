flowchart TD
    %% Definición de estilos para simular BPMN
    classDef event fill:#d5e8d4,stroke:#82b366,stroke-width:2px;
    classDef endEvent fill:#f8cecc,stroke:#b85450,stroke-width:3px;
    classDef task fill:#dae8fc,stroke:#6c8ebf,stroke-width:1px;
    classDef gateway fill:#fff2cc,stroke:#d6b656,stroke-width:2px;

    subgraph Operacion ["Usuario / Jefe de Almacén"]
        direction TB
        Start(((Inicio))) --> Solicitud[Registrar Solicitud de Movimiento]
        Solicitud --> Tipo{Tipo de <br>Movimiento}
        
        Tipo -->|Entrada| ValEntrada[Verificar Mercancía y Lotes/Series]
        Tipo -->|Salida| ValSalida[Seleccionar Mercancía para Despacho]
        Tipo -->|Transferencia| ValTrans[Asignar Almacén Origen y Destino]
    end

    subgraph ERP ["Sistema ERP (Reglas e Integridad)"]
        direction TB
        ValEntrada --> SysEntrada[Procesar Entrada en Almacén]
        ValSalida --> ReglaStock{¿Stock Actual <br>>= Cantidad Solicitada?}
        ValTrans --> ReglaStock
        
        ReglaStock -->|No| Bloqueo[Bloquear Operación <br>Regla: Cero Inventario Negativo]
        ReglaStock -->|Sí| SysSalida[Descontar Stock de Almacén Origen]
        
        SysEntrada --> BD[Registrar Transacción <br>Pruebas de Integridad ACID]
        SysSalida --> EsTrans{¿Es <br>Transferencia?}
        
        EsTrans -->|Sí| ReglaDestino[Validar Almacén Destino Activo]
        ReglaDestino --> SysDestino[Sumar Stock en Almacén Destino]
        SysDestino --> BD
        
        EsTrans -->|No| BD
    end

    Bloqueo --> FinError(((Fin <br>Rechazado)))
    BD --> FinExito(((Fin <br>Procesado)))

    %% Asignación de estilos BPMN
    class Start event;
    class FinError,FinExito endEvent;
    class Solicitud,ValEntrada,ValSalida,ValTrans,SysEntrada,SysSalida,SysDestino,BD,Bloqueo,ReglaDestino task;
    class Tipo,ReglaStock,EsTrans gateway;
