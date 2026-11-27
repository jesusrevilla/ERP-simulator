# Investigación: ¿qué modelo LLM es el mejor para trabajar con `Rutas.md`?

## 1. Tarea evaluada

A partir de `Rutas.md` (flujo con requerimientos funcionales, reglas de negocio, pruebas unitarias, pruebas funcionales e integridad de datos), el modelo debe producir un artefacto ejecutable y trazable: las reglas de negocio en código y las pruebas que las verifican.

Artefacto entregado: `rutas_erp.py` (reglas) y `test_rutas_erp.py` (27 pruebas unitarias).

## 2. Criterios

| Criterio | Por qué importa en esta tarea |
|---|---|
| Fidelidad al diagrama | Implementar cada nodo (C1, C2, E1a, ...) sin agregar ni omitir reglas |
| Código ejecutable y pruebas útiles | Que el código corra y que las pruebas verifiquen las reglas |
| Consistencia entre archivos | Mantener nombres y etiquetas alineados con el diagrama y con los demás artefactos del equipo (SQL, JSON ISA-95, BPMN) |
| Salida estructurada | Generar Mermaid, SQL y JSON válidos |
| Contexto largo | Trabajar con varios archivos a la vez (el esquema SQL del equipo pesa unos 23 KB) |
| Costo y acceso | Precio por millón de tokens y disponibilidad |

## 3. Candidatos y evidencia (noviembre de 2026)

| Modelo | Posición y puntaje en coding (BenchLM) | Precio USD por millón de tokens (entrada / salida) | Nota |
|---|---|---|---|
| Claude Fable 5.2 (Anthropic) | 1.º, 89.8 | 8 / 40 | Primero en tareas de código largas y de varios archivos; el más caro |
| Gemini 4 Carbon (Google) | 2.º, 84 | 2 / 10 hasta el 30 de nov. de 2026; después 4 / 20 | Contexto de 1,048,576 tokens |
| Claude Opus 5.5 (Anthropic) | 3.º, 82.7 | 4 / 20 | |
| Claude Sonnet 5.5 (Anthropic) | 4.º | 2 / 10 | |
| GPT-6.1 Sol (OpenAI) | 8.º | 2 / 10 (el doble por encima de 272 K tokens) | |
| Kimi K3.1 Pro (Moonshot AI) | Mejor modelo de pesos abiertos | — | Se puede ejecutar localmente |

Otro agregador (llm-stats) mantiene el mismo orden entre los modelos de Anthropic: Fable 5.2 (50.9), Opus 5.5 (48.9) y Sonnet 5.5 (47.2) en su índice de coding.

## 4. Conclusión

- **Por desempeño general en código:** Claude Fable 5.2 encabeza las dos clasificaciones consultadas.
- **Para esta tarea concreta:** el diagrama es acotado y el resultado son unas 470 líneas entre código y pruebas, por lo que un modelo de gama media puede bastar. Las fuentes no muestran que el modelo más caro mejore este caso específico.
- **Relación costo-calidad:** Claude Sonnet 5.5, Claude Opus 5.5 o Gemini 4 Carbon (este último a precio introductorio y con contexto de 1M de tokens).
- **Si se generan todos los artefactos del equipo en una sola sesión:** conviene un modelo con contexto largo, como Fable 5.2 o Gemini 4 Carbon.

Limitaciones: las clasificaciones provienen de agregadores que en parte reproducen cifras de los propios proveedores y miden código en general, no la conversión de un diagrama a reglas y pruebas. La conclusión debe validarse con la prueba de la sección 5.

## 5. Prueba realizada

**Modelo utilizado: Claude Sonnet 5.5 (Anthropic).** Este modelo pertenece al mismo proveedor que tres de los de la tabla, por lo que su elección tiene un posible sesgo; por eso se incluye la rúbrica para comparar con otros modelos.

**Resultado:** 27 pruebas aprobadas con `python -m unittest -v test_rutas_erp` (también se ejecutan con `pytest`).

| Nodo de `Rutas.md` | Función | Prueba |
|---|---|---|
| C1 Secuencia entera y correlativa | `validar_secuencia` | `TestSecuencia` |
| B3 y B4 Run Time y días de espera | `programar_fechas` | `test_run_time_y_dias_de_espera` |
| C2 Fechas dentro del horizonte | `crear_orden` | `test_fechas_dentro_del_horizonte`, `test_fechas_fuera_del_horizonte_se_rechazan` |
| C3 y C4 Despacho previo completo | `emitir_para_produccion` | `test_bloqueo_hasta_completar_el_despacho_previo` |
| D1 Guardado del maestro de etapas | `Ruta.agregar_etapa` | `test_guardado_del_maestro_de_etapas` |
| D2 Total Run Time | `Ruta.total_run_time` | `test_total_run_time_se_actualiza` |
| D3 Reenumeración al insertar | `insertar_etapa` | `test_reenumeracion_al_insertar_una_secuencia` |
| E1 Orden con 3 etapas | `crear_orden`, `liberar_orden` | `test_orden_con_tres_etapas_liberada` |
| E1a Filtro de la Etapa 1 | `lineas_para_despacho` | `test_filtro_de_la_etapa_1` |
| E1b Descuento de inventario | `emitir_para_produccion` | `test_descuento_correcto_del_inventario` |
| E1c Auditoría de costos | `auditar_costos`, `finalizar_orden` | `test_auditoria_de_costos_al_finalizar` |
| E2 Cambio de almacén tras la Etapa 1 | `cambiar_almacen` | `test_cambio_de_almacen_despues_de_la_etapa_1` |
| F1 Líneas huérfanas | `lineas_huerfanas` | `test_lineas_huerfanas` |
| F2 Borrado de etapa con movimientos | `borrar_etapa` | `test_no_se_borra_etapa_con_movimientos_en_orden_liberada` |
| F3 La orden conserva su ruta | `crear_orden` (copia de la ruta) | `test_la_orden_conserva_su_ruta_original` |

**Supuestos declarados:** jornada de 480 minutos por día para convertir el Run Time en días; costos y almacenes de ejemplo; "después de la Etapa 1" se interpreta como Etapa 1 completamente despachada. Las etapas y materiales del Gaming PC provienen del JSON ISA-95 del equipo.

**Prompt de referencia:**

```
A partir del diagrama Mermaid de Rutas.md, implementa en Python las reglas de
negocio (secciones 2 y 5) y el despacho de inventario (sección 4), y escribe
pruebas unitarias que cubran las secciones 3 y 4. Cada función debe indicar el
nodo del diagrama que implementa. No agregues reglas que no estén en el
diagrama; si necesitas un supuesto, decláralo. Usa como ejemplo la ruta de un
Gaming PC con tres etapas.
```

**Rúbrica para comparar modelos** (0 = no cumple, 1 = parcial, 2 = cumple):

| Criterio | Modelo A | Modelo B | Modelo C |
|---|---|---|---|
| Cubre todos los nodos sin inventar reglas | | | |
| El código corre sin cambios | | | |
| Las pruebas pasan y verifican reglas reales | | | |
| Mantiene nombres y etiquetas del diagrama | | | |
| Declara sus supuestos | | | |
| Total | | | |

## 6. Fuentes (consultadas en noviembre de 2026)

- BenchLM, Best LLM for Coding: https://benchlm.ai/coding
- BuildMVPFast, Best AI for Coding, November 2026: https://www.buildmvpfast.com/articles/best-llms-2026-guide/coding-ai
- Morph, Best AI Model for Coding: https://www.morphllm.com/best-ai-model-for-coding
- LLM Stats, Best AI for Coding: https://llm-stats.com/leaderboards/best-ai-for-coding
