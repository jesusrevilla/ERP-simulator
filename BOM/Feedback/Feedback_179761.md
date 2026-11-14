# FEEDBACK evaluación del Módulo BOM

**Veredicto general:** La estructura base de la base de datos (`schema.sql`) está bien planteada para empezar, **pero el módulo aún no está listo para darse por terminado**. Sirve para guardar datos básicos, pero actualmente deja pasar errores críticos de negocio y permite modificar información histórica que debería estar protegida.

**NO ENCONTRE EL MODULO DE IA
---

## 1. Lo que ya funciona bien
* **Sin traslape de versiones:** La base de datos garantiza que un producto no pueda tener dos recetas (BOM) activas al mismo tiempo.
* **Orden y estructura básica:** Las tablas principales existen, evitan valores negativos y mantienen el orden básico entre productos y componentes.

---

## 2. Los riesgos principales 

* **Entran datos inválidos:** Hoy el sistema deja crear una receta para una materia prima (como un tornillo), usar piezas descontinuadas, asignar unidades absurdas (ej. pedir *"1 kilo de memoria RAM"*) o registrar cantidades con decimales para piezas indivisibles (como *"0.5 procesadores"*).
* **Riesgo de bucles infinitos:** No hay nada que impida que un producto se contenga a sí mismo (ej. una PC que lleva dentro una tarjeta madre, y esa tarjeta madre lleva dentro la misma PC).
* **Se puede alterar la historia:** Si una receta ya está aprobada o se está usando en una orden de fabricación, cualquiera puede editarla o borrarla. Además, no hay una bitácora que registre quién cambió qué valor y cuándo.
* **Aprobaciones sin filtro:** Se puede marcar una receta como "Activa" aunque esté completamente vacía o aunque sus piezas internas no tengan recetas válidas.
* **Faltan los cálculos del negocio:** La base de datos guarda la información, pero todavía no existen las rutinas (en BD o en el código de la aplicación) para calcular el costo total acumulado, explotar materiales para compras o saber en qué productos se usa una pieza (*where-used*).

---

## 3. Contradicciones entre los documentos del proyecto
Antes de programar lo que falta, el equipo debe ponerse de acuerdo en 4 reglas donde los documentos se contradicen entre sí:

1. **Nombres de estados:** Un documento usa *Borrador / Aprobada / Obsoleta* y otro usa *Borrador / Activo / Inactivo / Obsoleto*. Hay que unificarlos.
2. **Fórmula de merma (desperdicio):** Un documento calcula la merma dividiendo y otro multiplicando (con un 10% de merma, uno da `11.11` piezas y el otro `11`). Hay que definir cuál es la regla oficial.
3. **Clonación:** Definir si copiar una receta sirve solo para sacar una nueva versión del mismo producto o también para crear un modelo distinto desde cero.
4. **Eventos del sistema:** Hay dos listas de eventos con nombres y estructuras diferentes. Hay que acordar un estándar único y definir dónde se van a guardar.

---

## 4. Pasos recomendados para cerrar el módulo
1. **Blindar la entrada de datos:** Bloquear piezas inactivas, unidades incompatibles, decimales en piezas enteras y bucles circulares.
2. **Congelar lo aprobado:** Impedir cambios en recetas activas o vinculadas a órdenes de producción, obligando a crear una nueva versión si hay cambios.
3. **Conectar órdenes y auditoría:** Asegurar que las órdenes de producción guarden una "foto" exacta e inalterable de la receta que usaron, y crear una tabla de auditoría para rastrear cambios.
4. **Probar escenarios reales:** No dar por cerrado el módulo hasta correr pruebas que intenten romper estas reglas (ej. intentar editar dos usuarios a la vez o crear un bucle) y verificar que el sistema las rechace.
