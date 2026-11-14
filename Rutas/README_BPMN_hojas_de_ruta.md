# BPMN – Hojas de ruta (MRP)

Diagrama del proceso de hojas de ruta del proyecto integrador MRP, basado en el documento de definición inicial de requerimientos (RF, RN, PU, PF y DI). GitHub renderiza el bloque Mermaid directamente.

## Diagrama

```mermaid
flowchart TB
  classDef ini fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
  classDef fin fill:#ffcdd2,stroke:#c62828,stroke-width:4px
  classDef usr fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
  classDef sis fill:#f3e5f5,stroke:#6a1b9a,stroke-width:2px
  classDef apr fill:#fff3e0,stroke:#e65100,stroke-width:2px
  classDef pla fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
  classDef gw fill:#fff8e1,stroke:#f9a825,stroke-width:2px

  subgraph C["Ingeniero de procesos (Creador)"]
    INI(("Nueva hoja<br/>de ruta"))
    T1("Capturar datos generales<br/>RF-01")
    T4("Agregar operaciones, centros<br/>y tiempos RF-02")
    T6("Asignar a materiales<br/>y rango de lote RF-03")
    T8("Enviar a revisión<br/>RF-05")
    F1((("Liberación<br/>rechazada")))
    E2(("Cambio o baja<br/>de hoja liberada"))
    G8{"¿Qué se<br/>requiere?"}
    T9("Indicar motivo<br/>RN-17")
  end

  subgraph S["Sistema MRP"]
    V1("Validar datos y asignar número<br/>RN-01 a RN-05")
    G1{"¿Datos<br/>válidos?"}
    V2("Validar operaciones y centros<br/>RN-06 a RN-08")
    G2{"¿Operaciones<br/>válidas?"}
    V3("Validar material propio<br/>y rangos sin cruce RN-09, RN-10")
    G3{"¿Asignación<br/>válida?"}
    V4("Verificar 1+ operación RN-11<br/>Estatus En revisión")
    G4{"¿Cumple<br/>requisito?"}
    S1("Validar segregación<br/>de funciones RN-12")
    G6{"¿Aprobador<br/>≠ creador?"}
    S2("Pasar a Liberada y<br/>registrar historial RF-07")
    S3("Seleccionar hoja por<br/>material y lote RF-08, RN-14")
    G7{"¿Hoja liberada<br/>y vigente?"}
    S4("Copiar hoja a la orden y<br/>calcular tiempo total<br/>RF-04, RN-15, RN-18")
    F3((("Orden creada")))
    S5("Crear nueva versión en Borrador<br/>RF-06, RN-13")
    F4((("Versión nueva<br/>en Borrador")))
    S6("Marcar Bloqueada u Obsoleta<br/>RF-11, RN-16")
    F5((("Hoja fuera<br/>de uso")))
  end

  subgraph A["Jefe de producción (Aprobador)"]
    A1("Revisar hoja de ruta<br/>RF-05")
    G5{"¿Aprueba?"}
    A2("Liberar hoja<br/>RF-05")
  end

  subgraph P["Planeador de producción"]
    P1("Crear orden<br/>de producción")
    F2((("No existe<br/>hoja liberada")))
  end

  INI --> T1 --> V1 --> G1
  G1 -->|"No"| T1
  G1 -->|"Sí"| T4 --> V2 --> G2
  G2 -->|"No"| T4
  G2 -->|"Sí"| T6 --> V3 --> G3
  G3 -->|"No"| T6
  G3 -->|"Sí"| T8 --> V4 --> G4
  G4 -->|"No"| T8
  G4 -->|"Sí"| A1 --> G5
  G5 -->|"No: regresa a Borrador"| T4
  G5 -->|"Sí"| A2 --> S1 --> G6
  G6 -->|"No"| F1
  G6 -->|"Sí"| S2 --> P1 --> S3 --> G7
  G7 -->|"No"| F2
  G7 -->|"Sí"| S4 --> F3

  E2 --> G8
  G8 -->|"Modificar"| S5 --> F4
  G8 -->|"Bloquear u obsoletar"| T9 --> S6 --> F5

  class INI,E2 ini
  class F1,F2,F3,F4,F5 fin
  class T1,T4,T6,T8,T9 usr
  class V1,V2,V3,V4,S1,S2,S3,S4,S5,S6 sis
  class A1,A2 apr
  class P1 pla
  class G1,G2,G3,G4,G5,G6,G7,G8 gw
```

> Versión con carriles fijos: [`hojas_de_ruta_bpmn.svg`](hojas_de_ruta_bpmn.svg)

## Leyenda

| Símbolo | Significado |
|---|---|
| Círculo verde | Evento de inicio |
| Círculo rojo (borde grueso) | Evento de fin |
| Rectángulo redondeado | Tarea (usuario o sistema) |
| Rombo | Compuerta exclusiva (decisión) |
| Subgrafo | Carril (rol responsable) |

## Trazabilidad

| Etapa | Requerimientos | Reglas de negocio |
|---|---|---|
| Captura y validación de datos generales | RF-01 | RN-01 a RN-05 |
| Operaciones y centros de trabajo | RF-02 | RN-06 a RN-08 |
| Asignación a materiales y lotes | RF-03 | RN-09, RN-10 |
| Envío a revisión | RF-05 | RN-11 |
| Liberación (segregación de funciones) | RF-05, RF-07 | RN-12 |
| Selección de hoja y cálculo de tiempo | RF-04, RF-08 | RN-14, RN-15, RN-18 |
| Nueva versión | RF-06 | RN-13, RN-15 |
| Bloqueo u obsolescencia | RF-11 | RN-16, RN-17 |
