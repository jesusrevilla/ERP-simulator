178561 - Palau Andrade Arturo - CNO VI Sistemas ERP
```mermaid
graph TD
    A[Inicio: Definición de Requerimientos y Reglas de Negocio] --> B[Registro de Recursos en SAP Business One]
    B --> C[Asignación de Calendarios, Horarios y Días No Laborables]
    C --> D[Validación de Capacidad Disponible y Mantenimiento]
    D --> E{¿Recurso y Capacidad Disponibles?}
    E -- Sí --> F[Programación y Asignación de Órdenes de Producción]
    E -- No --> G[Bloqueo y Notificación de Indisponibilidad]
    F --> H[Ejecución de Pruebas Unitarias, Funcionales y Validación de Datos]
    G --> C
    H --> I[Fin: Planeación Operativa Optimizada]
