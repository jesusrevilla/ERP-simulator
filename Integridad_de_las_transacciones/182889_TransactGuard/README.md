# TransactGuard AI — Agente de Integridad de las Transacciones en ERP

- **Alumno:** Oscar Octavio García Maya
- **Matrícula:** 182889
- **Rama de trabajo:** `feature/182889`
- **Tema:** Integridad de las Transacciones

## 1. Descripción del Agente
**TransactGuard AI** audita y garantiza la integridad referencial, financiera y de control interno de las transacciones dentro de un ERP combinando un **Knowledge Graph en Neo4j** (Orden de Compra → Recepción → Factura → Pago) con un **Sistema Experto y módulo de planeación en Python**.

## 2. Reglas de Inferencia
- `R1_THREE_WAY_MATCH`: Verifica que toda factura esté respaldada por Orden de Compra y Recepción de Almacén.
- `R2_DISCREPANCIA_MONTO`: Valida que la diferencia entre Orden de Compra y Factura no supere el 2%.
- `R3_VIOLACION_SOD`: Detecta conflictos de Segregación de Funciones (un mismo usuario creando y aprobando).
- `R4_PAGO_DUPLICADO`: Identifica facturas liquidadas por múltiples pagos activos.

## 3. Ejecución
1. Ejecutar `182889_grafo_integridad.cypher` en Neo4j Browser.
2. Instalar dependencias: `pip install -r requirements.txt`
3. Ejecutar el agente: `python 182889_agente_transactguard.py`
