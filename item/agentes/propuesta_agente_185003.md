# Propuesta #1 de Agente Inteligente: "ItemMaster Guardian & Inventory Optimizer"


## 1. Resumen Ejecutivo y Visión del Agente
Para el ecosistema de manufactura de "TechAssembly S.A." (enfocado en la línea de ensamble de PCs Gaming), la integridad de los componentes, la precisión del MRP y la consistencia transaccional en bases de datos son críticas. Proponemos un agente híbrido autónomo denominado "ItemMaster Guardian".

Este agente opera de forma cíclica (en segundo plano durante los pipelines de integración continua o eventos transaccionales) y también permite activación manual vía comandos de validación. Su propósito principal es supervisar en tiempo real el flujo de los artículos, prevenir inconsistencias lógicas en las estructuras de materiales (BOM) y anticiparse a bloqueos por falta de stock o errores de inventario negativo, fusionando la lógica simbólica con la optimización matemática.

## 2. Arquitectura de Funcionamiento y Ciclo del Agente
El agente se divide lógicamente en dos sub-agentes concurrentes que trabajan en paralelo dentro del mismo espacio de ejecución:

Agente Supervisor de Estructuras (Símbolo-Lógico): Monitorea de forma continua la creación de SKUs, las relaciones de componentes (como los 6 elementos clave de la Gaming PC: CPU Ryzen 7, Motherboard B650, RAM, SSD, PSU y GPU) y las rutas de producción.

Agente Predictor de Movimientos de Almacén (Optimización y Restricciones): Analiza los flujos reflejados en el diagrama de transacciones del almacén (Entradas, Salidas y Transferencias) para evaluar la disponibilidad de stock antes de que el motor de base de datos rechace la operación por la regla de Cero Inventario Negativo.

# Algoritmos Aplicados
- Agentes Basados en Conocimiento y Model Checking (Lógica Proposicional)
- Satisfacción de Restricciones (CSP) y Propagación de Arcos (AC-3)
- Búsqueda Local y Optimización (Hill Climbing con Restricciones de Lead Time)

## Propuesta de mejora para aplicar el agente
Añadir en los esquemas JSON de los ítems una propiedad explícita de "Umbral de Alerta Temprana de Stock". Esto permitirá que el agente lea directamente el umbral y ejecute alertas proactivas antes de que el inventario llegue a cero crítico.

<br>
<br>
<br>
<br>

# Propuesta #2 de Agente Inteligente: "Assembly-QA Diagnostic & Routing Oracle"
## 1.- ¿En que consiste el agente?
Este agente es el estratega del piso de producción y control de calidad. Analizando los JSON proporcionados, notamos que la Planta (ubicada en San Luis Potosí) ejecuta operaciones complejas de montaje (ComponentMounting), pruebas de estrés (PowerOnSelfTest) y validación de código mediante integración continua (pytest en GitHub Actions).
El "Assembly-QA Oracle" es un agente autónomo diseñado para orquestar la secuencia lógica de ensamblaje en las celdas de trabajo y diagnosticar de forma inteligente cualquier falla técnica o de software reportada durante las pruebas. Se ejecuta de forma cíclica escuchando los eventos de la línea de producción y del pipeline de CI/CD

## 2. ¿Cómo es que funciona?
Este agente actúa sobre dos frentes operativos simultáneos:
1. Agente Secuenciador de Ruta (Routing & Constraint Solver): Monitorea los eventos de ensamblaje físico (ej. ACT-PREP-MB-01 y ACT-ENSAMBLE-CHASIS-01). Se asegura de que la ruta de producción fluya sin cuellos de botella y que ningún operario o brazo robótico intente ensamblar piezas en un orden lógicamente imposible.
2. Agente Diagnosticador de Calidad (Logical Trouble-shooter): Se conecta a los logs generados en MongoDB durante el EVT-QA-001 (Primer encendido) y ACT-05-PRUEBAS-UNITARIAS (pytest). Si una PC falla el POST o un test unitario no pasa, el agente deduce la causa raíz exacta y sugiere la reparación o rollback automático.

## Algoritmos Aplicados
- Lógica Proposicional e Inferencia (Model Checking) para Diagnóstico
- Satisfacción de Restricciones (CSP) para la Secuencia de Ensamblaje
- Búsqueda Local (Simulated Annealing) para Balanceo de Carga en Pruebas

## Propuesta de mejora para aplicar el agente
Modificar al documento de OperationsPerformance: agregar un campo obligatorio llamado "FailureCode" o "DiagnosticFlag" dentro de los OperationsEvent de Calidad. Esto le dará a el agente de Lógica Proposicional las variables exactas que necesita para evaluar la tabla de verdad y automatizar el diagnóstico.
