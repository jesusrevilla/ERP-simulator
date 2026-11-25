# Investigación: ¿qué modelo LLM es el mejor para trabajar con `Rutas.md`?

**Autor:** Ari Maximiliano Muñiz Moncada (182698)
**Materia:** Ingeniería de Software II, UPSLP
**Fecha de consulta de las fuentes:** 23 de noviembre de 2026

## 1. Tarea evaluada

A partir de `Rutas.md` (diagrama Mermaid con requerimientos funcionales, reglas de negocio, pruebas unitarias, pruebas funcionales e integridad de datos), el modelo debe producir un artefacto **ejecutable y trazable**: las reglas de negocio en código y las pruebas que las verifican.

Es una tarea **acotada**: un diagrama de unos 30 nodos que se convierte en unas 250 líneas de código y 30 pruebas. No requiere razonamiento de horizonte largo ni editar un repositorio grande.

## 2. Criterios

| Criterio | Por qué importa en esta tarea |
|---|---|
| Fidelidad al diagrama | Implementar cada nodo (C1, C2, E1a, ...) sin inventar ni omitir reglas |
| Código ejecutable y pruebas útiles | Que el código corra y que las pruebas verifiquen reglas reales |
| Consistencia entre archivos | Mantener nombres y etiquetas alineados con el diagrama, el BPMN y el JSON ISA-95 del equipo |
| Salida estructurada | Generar Python, Mermaid y JSON válidos |
| Contexto | Poder leer varios archivos a la vez (esquema SQL, BPMN, JSON) |
| Costo y acceso | Precio por millón de tokens y disponibilidad |

## 3. Evidencia encontrada

Los rankings de coding **no coinciden entre sí**, lo cual es el hallazgo principal:

| Fuente (fecha) | Qué dice |
|---|---|
| AnotherWrapper (12 nov 2026) | DeepSeek-V4-Pro-0813 es el 1.º en SWE-bench Verified con 96.4 %, a 1.32 USD (entrada) y 3.96 USD (salida) por millón de tokens |
| DataCamp (25 sep 2026) | En la tabla de Vals AI, Claude Opus 5 (97.0 %), DeepSeek V4 Pro 0813 (96.4 %) y GPT-5.6 Sol (96.2 %) quedan a menos de 1 punto. Entre los modelos en la nube más fuertes cita a Claude Opus 5.5, Claude Fable 5.1, GPT-6 Astra y Gemini 3.8 Flash, todos con contexto cercano a 1 M de tokens. Recomienda no creer diferencias menores a 3 puntos sin una réplica independiente |
| Gradually (consultada en nov 2026) | Claude Fable 5.2, Claude Opus 5.5 y GPT-6 Astra están prácticamente empatados arriba; Claude Sonnet 5.5 es el más barato de los diez primeros |
| Onyx (actualizada 13 oct 2026) | Para corregir errores reales en repositorios destaca Claude Opus 5.5, Grok 4.6, Claude Fable 5 y Claude Sonnet 5.5; advierte tomar con cautela las cifras que reportan los propios proveedores |
| iTechGuides y DEV Community (2026) | Coinciden en que no hay un mejor modelo único: depende de la carga de trabajo, el costo y el entorno |

## 4. Conclusión

- **No hay un ganador claro.** Los modelos de gama alta (Claude Fable 5.2, Claude Opus 5.5, GPT-6 Astra, DeepSeek V4 Pro) están empatados dentro del margen de error de estas pruebas.
- **Los benchmarks miden otra cosa.** SWE-bench y Terminal-Bench miden corrección de errores en repositorios y tareas de terminal, no la conversión de un diagrama en reglas y pruebas.
- **Para esta tarea concreta** el diagrama es corto, así que lo que decide es la relación costo-calidad y la fidelidad al diagrama, no el contexto ni el razonamiento largo.

**Recomendación:** un modelo de gama media o alta con buen costo (Claude Sonnet 5.5 o Claude Opus 5.5 como opciones principales, DeepSeek V4 Pro como alternativa económica). Claude Fable 5.2 solo se justifica si se generan todos los artefactos del equipo en una sola sesión larga.

**Limitaciones:** las fuentes son agregadores y blogs que en parte reproducen cifras de los proveedores, y ninguna mide esta tarea específica. La conclusión se debe validar con la prueba de la sección 5.

## 5. Prueba realizada

**Modelo utilizado: Claude Sonnet 5.5 (Anthropic).** Declaro un posible sesgo: tres de los modelos recomendados son del mismo proveedor. Por eso se incluye la rúbrica para repetir la prueba con otros modelos.

**Resultado:** 30 pruebas aprobadas con `python -m unittest -v test_rutas_erp` (también corren con `pytest`).

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
| E1a Filtro de la Etapa 1 | `lineas_de_etapa` | `test_filtro_de_la_etapa_1` |
| E1b Descuento de inventario | `emitir_para_produccion` | `test_descuento_correcto_del_inventario` |
| E1c Auditoría de costos | `auditar_costos`, `finalizar_orden` | `test_auditoria_de_costos_al_finalizar` |
| E2 Cambio de almacén tras la Etapa 1 | `cambiar_almacen` | `test_cambio_de_almacen_despues_de_la_etapa_1` |
| F1 Líneas huérfanas | `lineas_huerfanas` | `test_lineas_huerfanas` |
| F2 Borrado de etapa con movimientos | `borrar_etapa` | `test_no_se_borra_etapa_con_movimientos_en_orden_liberada` |
| F3 La orden conserva su ruta | `crear_orden` (copia de la ruta) | `test_la_orden_conserva_su_ruta_original` |

Además, `TestPruebaFuncionalGamingPC` recorre los 5 pasos de la prueba funcional del equipo (2 Gaming PC, 210 min, costo planificado y real de 2,330 USD, diferencia 0).

**Supuestos declarados** (también están en el encabezado de `rutas_erp.py`):

- Jornada de 480 min por día; cada etapa ocupa al menos un día.
- "Despacho previo completo" significa todas las líneas de las etapas anteriores al 100 %.
- "Cambio de almacén después de la Etapa 1" significa que solo se cambia en etapas 2 en adelante, una vez despachada la Etapa 1.
- Solo una orden LIBERADA puede despachar.

**Validaciones extra** que no están en el diagrama, para evitar datos inválidos: cantidad de despacho positiva, ruta sin etapas y costo faltante para un material.

**Prompt de referencia:**

```
A partir del diagrama Mermaid de Rutas.md, implementa en Python las reglas de
negocio (secciones 2 y 5) y el despacho de inventario (sección 4), y escribe
pruebas unitarias que cubran las secciones 3 y 4. Cada función debe indicar el
nodo del diagrama que implementa. No agregues reglas que no estén en el
diagrama; si necesitas un supuesto, decláralo. Usa como ejemplo la ruta de un
Gaming PC con tres etapas.
```

**Rúbrica para comparar modelos** (0 = no cumple, 1 = parcial, 2 = cumple). Solo llené lo que verifiqué al ejecutar; el resto se califica al revisar cada resultado.

| Criterio | Sonnet 5.5 | Modelo B | Modelo C |
|---|---|---|---|
| Cubre todos los nodos sin inventar reglas | por revisar | | |
| El código corre sin cambios | 2 | | |
| Las pruebas pasan y verifican reglas reales | 2 | | |
| Mantiene nombres y etiquetas del diagrama | por revisar | | |
| Declara sus supuestos | por revisar | | |
| Total | | | |

## 6. Fuentes (consultadas el 23 de noviembre de 2026)

- AnotherWrapper, Coding leaderboard: https://anotherwrapper.com/tools/llm-pricing/leaderboards/coding
- DataCamp, Best LLM for Coding in 2026: https://www.datacamp.com/blog/best-llm-for-coding
- Gradually, Best LLM for coding: https://www.gradually.ai/en/best-llm/coding/
- Onyx, Best LLMs for Coding in 2026: https://onyx.app/insights/best-llms-for-coding-2026
- DEV Community, Best LLM for Coding in 2026: https://dev.to/nishilbhave/best-llm-for-coding-in-2026-7-models-ranked-by-use-case-2nb7
