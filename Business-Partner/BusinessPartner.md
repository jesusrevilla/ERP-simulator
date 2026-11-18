SistemasERP - Módulo de Socios de Negocio (Business Partners) en SAP Business One
---
Requerimientos
1. Definición de Requerimientos Funcionales

Los requerimientos funcionales especifican qué debe hacer el sistema SAP Business One en el módulo de Socios de Negocio para cubrir la operación comercial, logística y financiera de la empresa.

- Clasificación y Tipos de Socios de Negocio:

  * El sistema debe permitir gestionar tres tipos principales de socios: Clientes (C), Proveedores (V) y Clientes Potenciales / Leads (L).
  * Capacidad de clasificar a los BPs en Grupos configurables (ej. Nacionales, Extranjeros, Mayoristas, Minoristas) para análisis estadísticos y segmentación de precios.

- Datos Maestros e Información General:

  * Registro de datos de identificación: Nombre fiscal, nombre comercial, RFC / Identificación fiscal, sitio web y datos de contacto principales.

- Gestión de Direcciones (Logística y Facturación):
  * Capacidad de almacenar múltiples direcciones por socio de negocio (direcciones de entrega y direcciones de factura), permitiendo seleccionarlas de forma dinámica en los documentos de ventas y compras.

- Personas de Contacto:
  * Administración de una lista de personas de contacto asociadas al BP (nombre, cargo, teléfono, correo electrónico, departamento) para la trazabilidad de la comunicación comercial.

- Información Financiera y Comercial:
  * Asignación de Condiciones de Pago predeterminadas (ej. Contado, 30 días, 60 días).
  * Asignación de Listas de Precios específicas y descuentos por volumen o artículo.
  * Definición de Moneda predeterminada para las transacciones (Moneda local, USD, etc.).
  * Definición de cuentas contables asociadas de clientes y proveedores (cuentas de mayor en el plan de cuentas).

* Conversión de Clientes Potenciales (Leads):
  * Funcionalidad para convertir un Lead en Cliente manteniendo el historial de interacciones, ofertas y documentos previos.

3. Descripción de las Reglas de Negocio que Aplican
   
Las reglas de negocio establecen las políticas, restricciones y validaciones automáticas que SAP Business One impone para garantizar la integridad de los datos y el control financiero.

- Validación de Crédito y Compromiso:
  * Regla: El sistema debe evaluar el Límite de Crédito y el Límite de Compromiso del cliente al momento de crear un documento de ventas (Oferta, Pedido o Factura de Deudor). Si se supera el límite establecido, el sistema puede emitir una advertencia o bloquear la creación del documento según los permisos y autorizaciones configuradas.

- Unicidad y Obligatoriedad de Datos Maestros:
  * Regla: El código del Socio de Negocio (CardCode) es único y no puede repetirse.
  * Regla: Los campos obligatorios para guardar un socio de negocio funcional son: Código, Nombre fiscal, Grupo de Socio de Negocio y la Identificación fiscal (RFC/NIT), para asegurar el cumplimiento fiscal y contable.

- Restricción por Bloqueo (Estado del Socio):
  * Regla: Si un socio de negocio se marca como "Bloqueado" (ya sea de manera general, o específicamente para ventas o compras), SAP Business One debe impedir estrictamente la generación de nuevos documentos transaccionales para ese socio, permitiendo únicamente consultar su historial y reportes.

- Consistencia de Moneda y Tipo de Cambio:
  * Regla: Si un socio de negocio opera en una moneda extranjera, todos los documentos de compras o ventas generados para él tomarán por defecto dicha moneda, aplicando automáticamente el tipo de cambio oficial registrado en la tabla de tipos de cambio de SAP B1 para la fecha del documento.

- Gestión de Impuestos (Grupos Impositivos):
  * Regla: El sistema debe asignar de forma automática el indicador de impuestos correspondiente según la ubicación fiscal (zona geográfica) del socio de negocio y su clasificación tributaria (ej. Gravado, Exento, Tasas especiales).

5. Pruebas Unitarias (Unit Testing)
Las pruebas unitarias validan de forma aislada los componentes individuales, campos específicos, restricciones a nivel de base de datos (OCRD) y validaciones lógicas dentro del formulario de Socio de Negocio.

- Validación de Unicidad del Código (CardCode):
  * Prueba: Intentar crear un Socio de Negocio utilizando un código que ya existe en el sistema.
  * Resultado esperado: SAP B1 debe bloquear el registro y emitir un mensaje de error indicando que la clave primaria ya está duplicada.

- Campos Obligatorios (Mandatory Fields):
  * Prueba: Intentar guardar un BP sin completar campos críticos como Nombre del Socio (CardName), Grupo de Socios (GroupCode), o el Registro Federal de Contribuyentes / Identificación Fiscal (LicTradNum).
  * Resultado esperado: El sistema impide el guardado y resalta los campos faltantes obligatorios.

- Asignación de Moneda por Defecto:
  * Prueba: Seleccionar una moneda extranjera (ej. USD) en la pestaña de finanzas de un nuevo cliente.
  * Resultado esperado: El campo de moneda se fija correctamente y hereda esta configuración en los documentos comerciales futuros.

- Validación de Formatos Fiscales (UDFs o Validaciones Nativas):
  * Prueba: Ingresar una estructura de RFC o ID fiscal con formato incorrecto o caracteres inválidos.
  * Resultado esperado: Activación de alertas nativas o validaciones (Stored Procedures de usuario o validaciones estándar) que rechacen el formato antes de confirmar en la base de datos de SAP HANA o MS SQL Server.

6. Pruebas Funcionales (Functional Testing)
Las pruebas funcionales evalúan flujos de negocio completos y la interacción entre el módulo de Socios de Negocio y los módulos transaccionales (Ventas, Compras, Finanzas).

- Conversión de Cliente Potencial (Lead) a Cliente (Customer):
  * Prueba: Tomar un registro clasificado como Lead (L), iniciar el proceso de conversión a Cliente (C) y verificar la retención de datos.
  * Resultado esperado: El sistema cambia el tipo de socio manteniendo intacto el historial de ofertas de ventas previas, contactos y direcciones vinculadas.

- Bloqueo de Transacciones por Socio Inactivo / Bloqueado:
  * Prueba: Marcar un cliente como "Bloqueado" (general o para ventas) e intentar generar un Pedido de Ventas (ORDR) o una Factura de Deudor.
  * Resultado esperado: SAP B1 interrumpe la operación mostrando un mensaje de advertencia impidiendo la creación del documento.

Diagrama de Flujo Integral de Requerimientos y Procesos
Estructura completa y validación de Socios de Negocio en diagrama:
```mermaid
graph TD
    classDef startNode fill:#2E7D32,stroke:#fff,stroke-width:2px,color:#fff;
    classDef processNode fill:#E65100,stroke:#fff,stroke-width:2px,color:#fff;
    classDef decisionNode fill:#0277BD,stroke:#fff,stroke-width:2px,color:#fff;
    classDef testNode fill:#6A1B9A,stroke:#fff,stroke-width:2px,color:#fff;
    classDef endNode fill:#4A148C,stroke:#fff,stroke-width:2px,color:#fff;

    Start([Inicio: Solicitud de Alta de BP]) --> Tipos[Definir Tipo: Cliente C, Proveedor V o Lead L]:::startNode
    Tipos --> General[Registrar Datos Maestros: CardCode, Nombre, RFC/ID]:::processNode
    General --> Test1{Pruebas Unitarias: ¿CardCode único y campos obligatorios?}:::testNode

    Test1 -->|No| Error1[Bloquear registro y reportar campos faltantes/duplicados]:::processNode
    Error1 --> General

    Test1 -->|Sí| Direcciones[Configurar Múltiples Direcciones y Personas de Contacto]:::processNode
    Direcciones --> Finanzas[Asignar Moneda, Listas de Precios y Cuentas de Mayor]:::processNode
    Finanzas --> DecisionLead{¿Es un Lead?}:::decisionNode

    DecisionLead -->|Sí| Conversion[Convertir Lead a Cliente conservando historial de ofertas]:::processNode
    DecisionLead -->|No| Funcionales[Evaluación Funcional: Límite de Crédito y Estado]:::processNode
    Conversion --> Funcionales

    Funcionales --> Test2{Pruebas Funcionales y Reglas de Negocio}:::testNode
    
    Test2 -->|Socio Bloqueado| Bloqueo[Restringir estrictamente transacciones comerciales]:::processNode
    Test2 -->|Crédito Excedido| Autorizacion[Activar Autorización / Advertencia de Crédito]:::processNode
    Test2 -->|Aprobado| Integridad[Validar Integridad Referencial OCRD y Plan de Cuentas]:::processNode

    Bloqueo --> Fin([Fin del Ciclo / Operación Rechazada]):::endNode
    Autorizacion --> Fin
    Integridad --> Success([Socio Operativo Registrado en OCRD]):::endNode
