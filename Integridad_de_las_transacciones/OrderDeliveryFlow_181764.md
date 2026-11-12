# Business Process Model and Notation
''' mermaid
flowchart TB
    Start["Inicio de Pedido"] --> CheckACID[" Iniciar Transacción ACID"]
    CheckACID --> CheckCredit["¿Límite de Crédito OK?"]
    CheckCredit -- Sí --> CheckPeriod["¿Período Contable Abierto?"]
    CheckCredit -- No --> AuthSup["Autorización Supervisor"]
    AuthSup -- Aprobado --> CheckPeriod
    AuthSup -- Denegado --> EndFail["Transacción Rechazada / Bloqueada"]
    CheckPeriod -- Abierto --> CheckInv["¿Existencias y Costos OK?"]
    CheckPeriod -- Cerrado --> EndFail
    CheckInv -- OK --> Accounting["Generar Asiento Contable"]
    CheckInv -- Error --> EndFail
    Accounting --> DBInt["Validar Integridad Referencial"]
    DBInt --> CheckState{"¿Fallo o Excepción?"}
    CheckState -- Sí (Fallo) --> Rollback[" Ejecutar Rollback Automático"]
    Rollback --> EndFail
    CheckState -- No (OK) --> Locking[" Aplicar Bloqueos Concurrencia"]
    Locking --> Audit[" Registrar Logs Inmutables"]
    Audit --> DataDB[("Base de Datos ERP")]
    DataDB -.-> EndSuccess["Transacción Exitosa"]
    DataDB --> EndSuccess

     Start:::startEvent
     CheckACID:::subprocessTask
     CheckCredit:::decision
     AuthSup:::serviceTask
     CheckPeriod:::decision
     CheckInv:::decision
     Accounting:::serviceTask
     DBInt:::serviceTask
     CheckState:::decision
     Rollback:::subprocessTask
     Locking:::serviceTask
     Audit:::serviceTask
     DataDB:::dataStore
     EndSuccess:::endNode
     EndFail:::endNode
    classDef startEvent fill:#76b900,stroke:#333,stroke-width:2px
    classDef serviceTask fill:#fef08a,stroke:#d97706,stroke-width:2px,stroke-dasharray: 2 2
    classDef subprocessTask fill:#fde047,stroke:#b45309,stroke-width:2px
    classDef decision fill:#22c55e,stroke:#15803d,stroke-width:2px
    classDef endNode fill:#ef4444,stroke:#991b1b,stroke-width:2px
    classDef dataStore fill:#ffffff,stroke:#333,stroke-width:1px

'''
