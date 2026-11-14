# Revisión del Proyecto ERP

El proyecto presenta una base estructurada y demuestra comprensión de la interacción entre los distintos módulos de un ERP. La lógica principal cumple su propósito inicial.

**Estado general:** En desarrollo.

A continuación, se detallan algunas observaciones y oportunidades de mejora para hacer el sistema más escalable y seguro.

## 1. Estructura General del Proyecto

* **Organización:** Existe una buena separación de responsabilidades. Las carpetas principales facilitan la navegación por el repositorio.
* **Base de Datos (`sql/`):** Separar los scripts de inicialización (`init.sql`, `seeds.sql`) es una buena práctica para el despliegue y control de versiones.
* **Código Fuente (`src/`):** Archivos como `mrp.py` y `check_shortages.py` indican una correcta división de la lógica de negocio.
* **Configuración y Pruebas:** La inclusión de `.env.example`, `requirements.txt` y un directorio de `tests/` refleja estándares adecuados de desarrollo.

## 2. Revisión de Código

### `init.sql` (Esquema de Base de Datos)

La estructura relacional es correcta y las llaves foráneas garantizan la integridad referencial.

* **Detalle observado:** Se utiliza el tipo de dato `INTEGER` para campos como `stock` y `quantity_required`.
* **Impacto:** En un entorno real, algunos materiales requieren unidades fraccionadas (por ejemplo, 1.5 litros o 2.5 metros).
* **Siguiente paso:** ¿Qué les parece cambiar estos campos a `DECIMAL` o `NUMERIC` para permitir un manejo de inventario más flexible?

### `check_shortages.py` (Cálculo de Faltantes)

La consulta SQL implementada resuelve el cruce entre órdenes de venta y materiales de manera eficiente.

* **Detalle observado:** Las credenciales de la base de datos (`password="erp"`) están escritas directamente en el código fuente.
* **Impacto:** Esto representa un riesgo de seguridad si el repositorio se comparte o se hace público.
* **Siguiente paso:** ¿Podrían aprovechar la estructura actual para cargar estas credenciales desde el archivo `.env` mediante variables de entorno?

### `mrp.py` (Planeación de Materiales)

La función `calculate_mrp` ejecuta correctamente la explosión de materiales multiplicando las cantidades.

* **Detalle observado:** El diccionario `BOM` con la lista de materiales está definido de forma estática (hardcoded) en el archivo.
* **Impacto:** Las listas de materiales son dinámicas por naturaleza. Mantenerlas fijas obligaría a realizar despliegues de código cada vez que se agregue o modifique un producto.
* **Siguiente paso:** ¿Cómo podríamos adaptar esta función para que ejecute una consulta a la tabla `bill_of_materials` en lugar de leer el diccionario local?

---
Buen avance general
