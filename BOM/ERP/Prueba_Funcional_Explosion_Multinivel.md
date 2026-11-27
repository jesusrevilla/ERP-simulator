# Prueba funcional PF-BOM-004 — Explosión multinivel de Lista de Materiales (BOM) para equipos de cómputo

## Objetivo

Validar que, a partir de un **pedido de cliente** de computadoras **Gaming PC (PC001)**, el MRP explote una lista de materiales con subensambles y calcule correctamente las **necesidades brutas y netas** de cada nivel según las cantidades de la receta y las existencias de inventario.

> **Naturaleza del documento:** especificación de una prueba funcional **pendiente de ejecución**. Los materiales y existencias iniciales provienen de `sql/seeds.sql`. Los subensambles descritos abajo son **datos de prueba propuestos que no están registrados en dicho archivo**. Este documento no presupone que el esquema o el motor MRP soporten actualmente la explosión recursiva. No se modifican los datos, el esquema ni el código del simulador.

## Integrantes del equipo

| Matrícula | Nombre completo |
|---|---|
| 182934 | Bryan Yareth Gámez Contreras |
| 179761 | Coral Jazmín Domínguez García |
| 181914 | Yael Quintanilla Ramírez |

## Identificación

- **ID:** PF-BOM-004
- **Módulos involucrados:** BOM, ventas/pedidos, inventario y MRP
- **Tipo:** Prueba funcional positiva de explosión multinivel y cálculo de necesidades
- **Requerimientos BOM relacionados:** RF03, RF05 y RF07; reglas RN04, RN07 y RN08
- **Responsable:** Equipo BOM
- **Estado:** Pendiente de ejecución

## 1. Datos existentes en el simulador

Según `sql/seeds.sql`, existe el producto **PC001 — Gaming PC** con esta receta e inventario inicial:

| Código | Material | Cantidad por PC | Stock inicial |
|---|---|---:|---:|
| CPU001 | CPU Ryzen 7 | 1 | 50 |
| MB001 | Motherboard B650 | 1 | 45 |
| RAM001 | RAM 16GB DDR5 | 2 | 200 |
| SSD001 | SSD 1TB NVMe | 1 | 75 |
| PSU001 | Power Supply 750W | 1 | 40 |
| GPU001 | Graphics Card RTX | 1 | 20 |

**Limitación verificada en los datos:** `sql/seeds.sql` relaciona directamente los seis materiales con PC001; **no define subensambles**. Por ello, los datos iniciales por sí solos sirven para calcular necesidades de un nivel, pero no para comprobar una explosión multinivel.

El archivo de semillas indica que las órdenes de venta se crean dinámicamente mediante `seed_data.py` y `ORDER_QUANTITY`; no se ha verificado la ubicación ni el comportamiento de ese script. Para esta prueba se requiere un pedido de **30 PC001** generado o simulado en el ambiente de pruebas.

## 2. Estructura multinivel propuesta para la prueba

Para alcanzar tres niveles (0, 1 y 2) se propone reagrupar los **mismos seis materiales** en dos subensambles adicionales. Sus códigos son identificadores **ficticios de la prueba**, no registros confirmados en la base de datos.

| Nivel | Padre | Componente | Cantidad por padre | Clasificación |
|---|---|---|---:|---|
| 0 → 1 | PC001 | SUB-CPU — Módulo de procesamiento | 1 | Subensamble propuesto |
| 0 → 1 | PC001 | SUB-GPU — Módulo gráfico | 1 | Subensamble propuesto |
| 0 → 1 | PC001 | SSD001 — SSD 1TB NVMe | 1 | Material de compra |
| 0 → 1 | PC001 | PSU001 — Power Supply 750W | 1 | Material de compra |
| 1 → 2 | SUB-CPU | CPU001 — CPU Ryzen 7 | 1 | Material de compra |
| 1 → 2 | SUB-CPU | MB001 — Motherboard B650 | 1 | Material de compra |
| 1 → 2 | SUB-CPU | RAM001 — RAM 16GB DDR5 | 2 | Material de compra |
| 1 → 2 | SUB-GPU | GPU001 — Graphics Card RTX | 1 | Material de compra |

```text
Nivel 0: PC001 — Gaming PC
├── Nivel 1: SUB-CPU (1)
│   ├── Nivel 2: CPU001 (1)
│   ├── Nivel 2: MB001 (1)
│   └── Nivel 2: RAM001 (2)
├── Nivel 1: SUB-GPU (1)
│   └── Nivel 2: GPU001 (1)
├── Nivel 1: SSD001 (1)
└── Nivel 1: PSU001 (1)
```

La reorganización conserva exactamente la cantidad de cada material requerida por una computadora. **No debe agregarse esta BOM multinivel sobre la receta plana existente sin reemplazar las relaciones equivalentes en un entorno de prueba**, porque duplicaría requerimientos.

## 3. Pedido, inventario y supuestos controlados

- **Pedido de cliente de prueba:** 30 unidades de PC001 — Gaming PC.
- **Fecha de demanda:** una fecha válida fijada al ejecutar la prueba.
- **Stock inicial de materiales:** valores de la tabla de `sql/seeds.sql`, sin otras reservas ni consumos.
- **Stock de PC001 terminadas:** 0 unidades (supuesto de prueba; no indicado en `seeds.sql`).
- **Stock de SUB-CPU y SUB-GPU:** 0 unidades (supuesto de prueba; no existen en `seeds.sql`).
- **Recepciones programadas, órdenes abiertas y reservas:** 0 (supuesto de prueba).
- **Tamaño de lote y cantidad mínima:** 1 unidad; sin redondeos adicionales.
- **Merma:** 0 %.
- **Unidad de medida:** piezas.
- **Versiones de BOM:** si el sistema maneja aprobación/vigencia, usar versiones aprobadas y válidas para la fecha de demanda; de no existir la función, registrar la limitación.

Los resultados siguientes son **valores esperados bajo estos supuestos**, no resultados observados de una ejecución.

## 4. Procedimiento

1. Preparar un ambiente aislado y verificar la existencia de PC001, CPU001, MB001, RAM001, SSD001, PSU001 y GPU001 con las cantidades e inventarios indicados en `sql/seeds.sql`.
2. Comprobar si la implementación actual admite subensambles fabricables y explosión recursiva de BOM. **Si no los admite, registrar el caso como bloqueado; no afirmar que fue validado.**
3. En el ambiente de prueba, disponer de la estructura propuesta de SUB-CPU y SUB-GPU, sin duplicar materiales en la BOM de PC001. Este paso es una **precondición de la ejecución**, no una instrucción para modificar los archivos del repositorio durante la redacción.
4. Configurar el inventario inicial de materiales y las existencias en cero de PC001, SUB-CPU y SUB-GPU.
5. Generar un **pedido de cliente de 30 PC001** con la fecha de demanda elegida, o usar el mecanismo de pedidos del simulador si permite establecer esa cantidad.
6. Ejecutar la planificación MRP sobre ese pedido.
7. Revisar el árbol de explosión en los niveles 0, 1 y 2 y las cantidades brutas y netas de subensambles y materiales.
8. Verificar que el inventario disponible se descuente **una sola vez** por artículo, que no se dupliquen los materiales y que se refleje la carencia de tarjetas gráficas.
9. Comparar los valores del sistema con las tablas siguientes y registrar la evidencia, las diferencias y el estado final.

## 5. Resultados esperados

### 5.1 Producto terminado y subensambles

Con stock supuesto de 0 unidades para PC001 y ambos subensambles:

| Artículo | Necesidad bruta | Stock disponible | Necesidad neta |
|---|---:|---:|---:|
| PC001 — Gaming PC | 30 | 0 | **30** |
| SUB-CPU — Módulo de procesamiento | 30 | 0 | **30** |
| SUB-GPU — Módulo gráfico | 30 | 0 | **30** |

La explosión a materiales parte de las **30 unidades de cada subensamble que se necesitan fabricar**, puesto que no hay existencias de subensambles.

### 5.2 Materias primas y materiales de compra

Fórmula simplificada bajo los supuestos indicados:

`Necesidad neta = max(0, necesidad bruta − stock disponible)`

| Código | Cálculo de necesidad bruta | Necesidad bruta | Stock | Necesidad neta |
|---|---|---:|---:|---:|
| CPU001 | 30 SUB-CPU × 1 | 30 | 50 | **0** |
| MB001 | 30 SUB-CPU × 1 | 30 | 45 | **0** |
| RAM001 | 30 SUB-CPU × 2 | 60 | 200 | **0** |
| SSD001 | 30 PC001 × 1 | 30 | 75 | **0** |
| PSU001 | 30 PC001 × 1 | 30 | 40 | **0** |
| GPU001 | 30 SUB-GPU × 1 | 30 | 20 | **10** |

**Resultado esperado:** la única necesidad neta de compra en este escenario es **10 unidades de GPU001**, siempre que no existan otras demandas, reservas, límites de lote o suministros pendientes. El MRP también debe identificar la necesidad de fabricar 30 PC001 y los 30 subensambles de cada tipo.

**Interpretación de niveles:** SUB-CPU y SUB-GPU son elementos intermedios fabricables; no deben sumarse como materias primas finales junto con sus propios componentes.

**Importante:** el cálculo numérico anterior usa el inventario inicial completo de `seeds.sql` para una única demanda de prueba. No demuestra que el motor MRP implemente efectivamente estas operaciones hasta que se ejecute y se contraste el resultado.

## 6. Criterios de aceptación

- **Aprobado:** existe un pedido identificable de 30 PC001; el MRP recorre correctamente los niveles 0, 1 y 2; muestra las necesidades brutas, descuenta existencias para calcular las netas y coincide con todas las tablas sin omisiones ni duplicaciones.
- **Fallido:** el flujo se ejecuta, pero hay errores de cantidades, inventarios, niveles, duplicaciones o asignación de necesidades.
- **Bloqueado:** el sistema carece de soporte para subensambles/explosión multinivel, no permite generar el pedido o faltan datos o funcionalidades indispensables. No se debe marcar como aprobado un cálculo manual.
- **No ejecutado:** el caso está documentado, pero todavía no se ha corrido en el simulador.

## 7. Evidencia a registrar

- Identificador y captura o respuesta de API del pedido del cliente de 30 PC001.
- Catálogo de artículos, estructura multinivel utilizada y, si aplica, versiones de BOM.
- Inventario inicial consultado antes de ejecutar el MRP.
- Árbol de explosión y resultados de necesidades brutas y netas en cada nivel.
- Recomendaciones/órdenes de fabricación y compra generadas por el MRP, si la funcionalidad está disponible.
- Fecha, ambiente, versión o commit, responsable, resultado observado, diferencias respecto a lo esperado y estado final.

## 8. Registro de ejecución

| Campo | Valor |
|---|---|
| Fecha de ejecución | Pendiente |
| Ambiente y versión | Pendiente |
| Pedido de cliente | Pendiente |
| Responsable | Equipo BOM |
| Resultado observado | Pendiente |
| Estado | **No ejecutada** |
| Evidencia | Pendiente |

## Referencias

- `sql/seeds.sql`: PC001, seis materiales, recetas directas y existencias iniciales.
- `BOM/ERP/BOM requeriments.md`: especificación del módulo BOM y referencia de prueba PF03 de explosión multinivel.
- Instrucción de la actividad: *Generar un pedido de cliente para un producto terminado con al menos 2 o 3 niveles de subensambles y materias primas, y validar necesidades brutas y netas calculadas por el MRP*.
