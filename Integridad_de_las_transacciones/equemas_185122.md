# Esquemas y estructura de la base de datos

## 1. Tablas principales

En el archivo `sql/init.sql` se encuentran definidas cinco tablas:

### Tabla `products`

Almacena la información de los productos.

| Campo | Tipo de dato | Descripción |
|---|---|---|
| `id` | SERIAL | Identificador del producto. |
| `code` | VARCHAR(20) | Código del producto. |
| `name` | VARCHAR(100) | Nombre del producto. |

### Tabla `materials`

Almacena la información de los materiales utilizados en el sistema.

| Campo | Tipo de dato | Descripción |
|---|---|---|
| `id` | SERIAL | Identificador del material. |
| `code` | VARCHAR(20) | Código del material. |
| `name` | VARCHAR(100) | Nombre del material. |

### Tabla `inventory`

Registra las existencias de cada material.

| Campo | Tipo de dato | Descripción |
|---|---|---|
| `material_id` | INTEGER | Identificador del material. |
| `stock` | INTEGER | Cantidad disponible del material. |

### Tabla `bill_of_materials`

Registra los materiales necesarios para fabricar cada producto.

| Campo | Tipo de dato | Descripción |
|---|---|---|
| `product_id` | INTEGER | Identificador del producto. |
| `material_id` | INTEGER | Identificador del material. |
| `quantity_required` | INTEGER | Cantidad de material necesaria. |

### Tabla `sales_orders`

Almacena las órdenes de venta.

| Campo | Tipo de dato | Descripción |
|---|---|---|
| `id` | SERIAL | Identificador de la orden. |
| `product_id` | INTEGER | Producto solicitado. |
| `quantity` | INTEGER | Cantidad solicitada. |
| `order_date` | TIMESTAMP | Fecha y hora de registro de la orden. |

## 2. Claves primarias y foráneas

Las tablas utilizan claves primarias para identificar sus registros y claves foráneas para relacionar información entre ellas.

| Tabla | Clave primaria | Claves foráneas |
|---|---|---|
| `products` | `id` | Ninguna |
| `materials` | `id` | Ninguna |
| `inventory` | `material_id` | `material_id` → `materials(id)` |
| `bill_of_materials` | `product_id`, `material_id` | `product_id` → `products(id)`; `material_id` → `materials(id)` |
| `sales_orders` | `id` | `product_id` → `products(id)` |

En `bill_of_materials` se utiliza una clave primaria compuesta por dos campos, lo que permite identificar cada combinación de producto y material.

## 3. Relaciones entre las tablas

Las principales relaciones de la base de datos son:

- **Products y sales_orders:** un producto puede estar relacionado con varias órdenes de venta. Cada orden corresponde a un producto existente.
- **Products y bill_of_materials:** un producto puede tener diferentes materiales registrados en su lista de materiales.
- **Materials e inventory:** cada registro de inventario corresponde a un material existente.
- **Materials y bill_of_materials:** un material puede formar parte de las listas de materiales de diferentes productos.

Estas relaciones permiten mantener conectada la información y evitan que se registren referencias a productos o materiales inexistentes.

## 4. Restricciones de integridad

En el archivo `sql/init.sql` se utilizan las siguientes restricciones:

- **PRIMARY KEY:** identifica de manera única cada registro de una tabla.
- **FOREIGN KEY:** garantiza que los valores relacionados correspondan a registros existentes en otra tabla.
- **UNIQUE:** evita que se repitan los códigos de productos y materiales.
- **NOT NULL:** impide que los campos obligatorios queden vacíos.
- **DEFAULT:** asigna automáticamente un valor cuando no se proporciona uno. En `sales_orders`, el campo `order_date` utiliza `CURRENT_TIMESTAMP`.

## 5. Ejemplos de integridad en la base de datos

**Ejemplo 1. Producto inexistente**

Si se intenta registrar una orden de venta con un `product_id` que no existe en la tabla `products`, la clave foránea impide guardar el registro.

**Ejemplo 2. Código duplicado**

Si se intenta registrar dos productos con el mismo código, la restricción `UNIQUE` del campo `code` evita que se repita.

**Ejemplo 3. Material inexistente**

Si se intenta registrar en `inventory` un `material_id` que no existe en `materials`, la clave foránea rechaza la operación.