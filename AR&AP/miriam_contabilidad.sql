-- MIRIAM:Contabilidad y Auditoria
-- Avance 1:Catalogo de cuentas contables
CREATE TABLE IF NOT EXISTS CuentasContables (
    id_cuenta   SERIAL PRIMARY KEY,
    codigo      VARCHAR(10)  NOT NULL UNIQUE,
    nombre      VARCHAR(100) NOT NULL,
    tipo        CHAR(1)      NOT NULL
                CHECK (tipo IN ('A','P','C','I','G')),
    activa      BOOLEAN      NOT NULL DEFAULT TRUE
);
-- tipo: A=Activo, P=Pasivo, C=Capital, I=Ingreso, G=Gasto
-- asientos automaticos
INSERT INTO CuentasContables (codigo, nombre, tipo) VALUES
    ('1100', 'Clientes',          'A'),
    ('1200', 'Bancos',            'A'),
    ('1300', 'Inventario',        'A'),
    ('1400', 'IVA acreditable',   'A'),
    ('2100', 'Proveedores',       'P'),
    ('2200', 'IVA trasladado',    'P'),
    ('4100', 'Ventas',            'I')
ON CONFLICT (codigo) DO NOTHING;