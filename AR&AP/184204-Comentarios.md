# Documentación Técnica: Datos Maestros, Control de Accesos y Cancelaciones
Alexis Israel Rivas Lara (184204)

Mini ERP – A/R y A/P

**Fuente principal:** `AR&AP/AR&AP-Req.md` y `AR&AP/Tablas-Alexis.sql`

## 1. Arquitectura de Datos Maestros y Catálogos

Los datos maestros constituyen la base relacional del moudulo. Sin el registro previo de entidades, no es posible generar operaciones comerciales ni financieras.

### 1.1 Tablas Implementadas en PostgreSQL (`Tablas-Alexis.sql`)

* **`condiciones_pago`**: Administra los plazos de crédito permitidos (`contado`, `15`, `30` o `60` días).
  * *Campos:* `id_condicion` (PK), `nombre`, `dias`.
* **`impuestos`**: Define las tasas de IVA aplicables a las transacciones (`16 %`, `0 %` o exento).
  * *Campos:* `id_impuesto` (PK), `nombre`, `tasa`.
* **`clientes`**: Almacena el padrón de clientes y su capacidad crediticia.
  * *Campos:* `id_cliente` (PK), `codigo`, `razon_social`, `rfc`, `direccion`, `contacto`, `id_condicion` (FK), `limite_credito`, `estatus`.
* **`proveedores`**: Almacena el padrón de proveedores con la misma estructura base que clientes (sin límite de crédito).
  * *Campos:* `id_proveedor` (PK), `codigo`, `razon_social`, `rfc`, `direccion`, `contacto`, `id_condicion` (FK), `estatus`.
* **`usuarios`**: Gestiona las cuentas de acceso y el perfil operativo dentro del sistema.
  * *Campos:* `id_usuario` (PK), `nombre_usuario`, `rol`, `estatus`.


 ### 1.2 Reglas de Integridad Implementadas

 1. **Integridad de Dominio (`CHECK` y Tipos de Datos):**
   * Los montos monetarios como `limite_credito` utilizan `DECIMAL(12, 2)` y las tasas en `impuestos` usan `DECIMAL(5, 4)` para evitar errores de precisión de punto flotante.
   * El campo `estatus` en `clientes` y `proveedores` está restringido a los valores `'A'` (Activo), `'I'` (Inactivo) y `'X'` (Cancelado).
   * La columna `tasa` en `impuestos` solo acepta `0.0000` o `0.1600`.
   * El campo `dias` en `condiciones_pago` y `limite_credito` en `clientes` exigen valores mayores o iguales a `0`.
2. **Integridad de Entidad (`UNIQUE` y `NOT NULL`):**
   * Los campos `codigo` y `rfc` en `clientes` y `proveedores`, así como `nombre_usuario` en `usuarios`, cuentan con restricción `UNIQUE` para impedir duplicados en los catálogos.

-- Fragmento de validación que implemente en Tablas-Alexis.sql
CREATE TABLE clientes (
    id_cliente SERIAL PRIMARY KEY,
    codigo VARCHAR(20) UNIQUE NOT NULL,
    razon_social VARCHAR(150) NOT NULL,
    rfc VARCHAR(13) UNIQUE NOT NULL,
    direccion TEXT NOT NULL,
    contacto VARCHAR(100),
    id_condicion INT NOT NULL REFERENCES condiciones_pago(id_condicion),
    limite_credito DECIMAL(12, 2) NOT NULL CHECK (limite_credito >= 0),
    estatus CHAR(1) NOT NULL CHECK (estatus IN ('A', 'I', 'X'))
);
