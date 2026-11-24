# Proceso MRP y Socios de Negocio (BPMN)

Este diagrama representa el flujo de interacción entre los **Socios de Negocio**, el **Motor de MRP** y el **Planificador**, basado en la notación BPMN (*Business Process Model and Notation*).

```mermaid
graph TD
    subgraph Planificador ["Rol: Planificador / Usuario"]
        A([Inicio: Definir Pedidos y Previsiones]) --> B[Ejecutar Asistente de MRP]
        G[Revisar Informe de Recomendaciones] --> H{¿Aprobar Recomendaciones?}
        H -- Sí --> I[Convertir Recomendaciones a Órdenes de Compra]
    end

    subgraph MRP ["Rol: Sistema / Motor de MRP"]
        B --> C{¿Socio de Negocio Activo / No Bloqueado?}
        C -- No --> C1[Excluir automáticamente de cálculos de demanda/abastecimiento]
        C -- Sí --> D[Consolidar Demanda Bruta:<br/>- Sales Orders<br/>- Forecasts]
        D --> E[Aplicar Reglas de Negocio de Proveedores:<br/>- Asignar Proveedor Preferente<br/>- Calcular Lead Time y Fechas de Liberación<br/>- Ajustar por Múltiplos y MOQ]
        E --> F[Agrupar Recomendaciones por Proveedor]
        F --> G
        I --> J[Generar Documentos Preliminares / Órdenes de Compra<br/>Heredando precios y acuerdos marco]
    end

    subgraph BPF ["Rol: Socios de Negocio (Proveedores / Clientes)"]
        J --> K([Fin: Envío de Órdenes de Compra al Proveedor])
    end

    classDef planificador stroke:#818cf8,fill:#eef2ff;
    classDef mrp stroke:#2dd4bf,fill:#f0fdfa;
    classDef bpf stroke:#a78bfa,fill:#f5f3ff;
    
    class Planificador planificador;
    class MRP mrp;
    class BPF bpf;
```

---
### Resumen del Flujo
1. **Validación:** Se filtran automáticamente los Socios de Negocio bloqueados o inactivos.
2. **Cálculo y Reglas:** Se consolidan *Sales Orders* y *Forecasts*, aplicando *Lead Time*, *MOQ* y proveedor preferente.
3. **Generación:** Al aprobar las recomendaciones, se emiten las Órdenes de Compra correspondientes heredando las condiciones comerciales.

## Validación de socios antes de crear órdenes

En el escenario de Business Partners, el validador consulta el estado del socio antes de autorizar una orden simulada. Para compras requiere un proveedor activo y habilitado para compras. Para ventas requiere un cliente activo, habilitado para ventas y con crédito disponible. En ambos casos verifica la moneda y registra el motivo de cada rechazo.

- [Guía de requisitos y escenarios](CristianGodinez_BusinessPartners.md)
- [Catálogo de 22 eventos de socios](CristianGodinez_BP_events.json)
- [Validador en Python](CristianGodinez/business_partner_events_cristian.py), [demo en Neo4j](CristianGodinez/neo4j_business_partners_cristian.py) y [pruebas](CristianGodinez/tests)

Para aplicar esta validación a las [recomendaciones de MRP](sql/mrp_recommendations.sql), queda pendiente vincular `supplier_code` con el `CardCode` del socio antes de convertir una recomendación en orden de compra.
