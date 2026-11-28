CREATE TABLE proveedores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    contacto VARCHAR(100),
    telefono VARCHAR(20),
    email VARCHAR(100),
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE materiales (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo_material VARCHAR(50) UNIQUE NOT NULL,
    descripcion VARCHAR(150) NOT NULL,
    unidad_medida VARCHAR(20) NOT NULL
);

CREATE TABLE inventario (
    material_id INT PRIMARY KEY,
    stock_actual DECIMAL(12,4) NOT NULL DEFAULT 0.00,
    ultima_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (material_id) REFERENCES materiales(id)
);

CREATE TABLE ordenes_compra (
    id INT AUTO_INCREMENT PRIMARY KEY,
    proveedor_id INT NOT NULL,
    fecha_emision DATE NOT NULL,
    timestamp_erp TIMESTAMP NOT NULL,
    estado ENUM('PENDIENTE', 'PARCIAL', 'RECIBIDA', 'CANCELADA') DEFAULT 'PENDIENTE',
    observaciones TEXT,
    FOREIGN KEY (proveedor_id) REFERENCES proveedores(id)
);

CREATE TABLE detalles_orden_compra (
    id INT AUTO_INCREMENT PRIMARY KEY,
    orden_compra_id INT NOT NULL,
    material_id INT NOT NULL,
    cantidad_solicitada DECIMAL(12,4) NOT NULL,
    FOREIGN KEY (orden_compra_id) REFERENCES ordenes_compra(id),
    FOREIGN KEY (material_id) REFERENCES materiales(id)
);
CREATE TABLE recepciones_mercancia (
    id INT AUTO_INCREMENT PRIMARY KEY,
    orden_compra_id INT NOT NULL,
    timestamp_mes TIMESTAMP NOT NULL,
    estado ENUM('BORRADOR', 'APROBADA') DEFAULT 'BORRADOR',
    usuario_recibe VARCHAR(100),
    observaciones TEXT,
    FOREIGN KEY (orden_compra_id) REFERENCES ordenes_compra(id)
);

CREATE TABLE detalles_recepcion (
    id INT AUTO_INCREMENT PRIMARY KEY,
    recepcion_id INT NOT NULL,
    material_id INT NOT NULL,
    cantidad_esperada DECIMAL(12,4) NOT NULL,
    cantidad_recibida DECIMAL(12,4) NOT NULL,
    piezas_faltantes DECIMAL(12,4) DEFAULT 0.00,
    piezas_dañadas DECIMAL(12,4) DEFAULT 0.00,
    FOREIGN KEY (recepcion_id) REFERENCES recepciones_mercancia(id),
    FOREIGN KEY (material_id) REFERENCES materiales(id)
);

CREATE TABLE log_eventos_dispositivos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nivel_isa95 VARCHAR(30) NOT NULL,
    evento_id VARCHAR(20) NOT NULL,
    actividad VARCHAR(150) NOT NULL,
    detalles TEXT NOT NULL,
    timestamp_dispositivo TIMESTAMP NOT NULL,
    recepcion_id INT,
    dispositivo_origen VARCHAR(100),
    FOREIGN KEY (recepcion_id) REFERENCES recepciones_mercancia(id)
);
