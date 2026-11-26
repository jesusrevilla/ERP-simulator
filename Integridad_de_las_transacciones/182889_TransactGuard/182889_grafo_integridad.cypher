// TransactGuard AI - Knowledge Graph de Integridad Transaccional (Matrícula: 182889)
MATCH (n) DETACH DELETE n;

CREATE CONSTRAINT usuario_id IF NOT EXISTS FOR (u:Usuario) REQUIRE u.id IS UNIQUE;
CREATE CONSTRAINT proveedor_id IF NOT EXISTS FOR (p:Proveedor) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT oc_id IF NOT EXISTS FOR (oc:OrdenCompra) REQUIRE oc.id IS UNIQUE;
CREATE CONSTRAINT rec_id IF NOT EXISTS FOR (r:Recepcion) REQUIRE r.id IS UNIQUE;
CREATE CONSTRAINT fac_id IF NOT EXISTS FOR (f:Factura) REQUIRE f.id IS UNIQUE;
CREATE CONSTRAINT pago_id IF NOT EXISTS FOR (pg:Pago) REQUIRE pg.id IS UNIQUE;

CREATE (u1:Usuario {id: 'USR-01', nombre: 'Ana Sofía Morales', rol: 'Comprador', departamento: 'Compras'})
CREATE (u2:Usuario {id: 'USR-02', nombre: 'Carlos Mendoza', rol: 'Gerente Compras', departamento: 'Compras'})
CREATE (u3:Usuario {id: 'USR-03', nombre: 'Luis Fernando Ruiz', rol: 'Almacenista', departamento: 'Almacén'})
CREATE (u4:Usuario {id: 'USR-04', nombre: 'Mariana Torres', rol: 'Analista CXP', departamento: 'Finanzas'})
CREATE (u5:Usuario {id: 'USR-05', nombre: 'Roberto Vega', rol: 'Tesorero', departamento: 'Finanzas'})

CREATE (prov1:Proveedor {id: 'PROV-10', razon_social: 'Aceros y Perfiles del Centro S.A.', rfc: 'APC190512HT1', estatus: 'ACTIVO'})
CREATE (prov2:Proveedor {id: 'PROV-20', razon_social: 'Suministros Industriales Potosí', rfc: 'SIP200815KL9', estatus: 'ACTIVO'})
CREATE (prov3:Proveedor {id: 'PROV-30', razon_social: 'Logística y Empaques Bajío', rfc: 'LEB180322MN4', estatus: 'ACTIVO'})

// ESCENARIO A: Transacción Íntegra (3-Way Match válido)
CREATE (oc1:OrdenCompra {id: 'OC-1001', fecha: '2026-11-10', monto: 15000.00, moneda: 'MXN', estado: 'APROBADA'})
CREATE (rec1:Recepcion {id: 'REC-2001', fecha: '2026-11-12', cantidad_recibida: 100, estado: 'COMPLETA'})
CREATE (fac1:Factura {id: 'FAC-3001', uuid_fiscal: 'A1B2-0001', fecha: '2026-11-13', monto: 15000.00, estado: 'VALIDADA'})
CREATE (pag1:Pago {id: 'PAG-4001', fecha: '2026-11-15', monto: 15000.00, metodo: 'SPEI', estado: 'LIQUIDADO'})

CREATE (u1)-[:CREA {timestamp: '2026-11-10T09:15:00'}]->(oc1)
CREATE (u2)-[:APRUEBA {timestamp: '2026-11-10T11:30:00'}]->(oc1)
CREATE (oc1)-[:DIRIGIDA_A]->(prov1)
CREATE (u3)-[:REGISTRA]->(rec1)
CREATE (rec1)-[:RESPALDA]->(oc1)
CREATE (fac1)-[:FACTURA_DE]->(oc1)
CREATE (fac1)-[:AMPARADA_POR]->(rec1)
CREATE (prov1)-[:EMITE]->(fac1)
CREATE (u4)-[:CONTABILIZA]->(fac1)
CREATE (u5)-[:AUTORIZA_PAGO]->(pag1)
CREATE (pag1)-[:LIQUIDA]->(fac1)

// ESCENARIO B: Factura sin Recepción de Mercancía
CREATE (oc2:OrdenCompra {id: 'OC-1002', fecha: '2026-11-14', monto: 28500.00, moneda: 'MXN', estado: 'APROBADA'})
CREATE (fac2:Factura {id: 'FAC-3002', uuid_fiscal: 'A1B2-0002', fecha: '2026-11-16', monto: 28500.00, estado: 'PENDIENTE_PAGO'})

CREATE (u1)-[:CREA {timestamp: '2026-11-14T10:00:00'}]->(oc2)
CREATE (u2)-[:APRUEBA {timestamp: '2026-11-14T14:20:00'}]->(oc2)
CREATE (oc2)-[:DIRIGIDA_A]->(prov2)
CREATE (fac2)-[:FACTURA_DE]->(oc2)
CREATE (prov2)-[:EMITE]->(fac2)

// ESCENARIO C: Violación de Segregación de Funciones (Auto-aprobación)
CREATE (oc3:OrdenCompra {id: 'OC-1003', fecha: '2026-11-18', monto: 42000.00, moneda: 'MXN', estado: 'APROBADA'})
CREATE (rec3:Recepcion {id: 'REC-2003', fecha: '2026-11-19', cantidad_recibida: 50, estado: 'COMPLETA'})
CREATE (fac3:Factura {id: 'FAC-3003', uuid_fiscal: 'A1B2-0003', fecha: '2026-11-20', monto: 42000.00, estado: 'VALIDADA'})

CREATE (u2)-[:CREA {timestamp: '2026-11-18T16:05:00'}]->(oc3)
CREATE (u2)-[:APRUEBA {timestamp: '2026-11-18T16:06:00'}]->(oc3)
CREATE (oc3)-[:DIRIGIDA_A]->(prov3)
CREATE (u3)-[:REGISTRA]->(rec3)
CREATE (rec3)-[:RESPALDA]->(oc3)
CREATE (fac3)-[:FACTURA_DE]->(oc3)
CREATE (fac3)-[:AMPARADA_POR]->(rec3)
CREATE (prov3)-[:EMITE]->(fac3)

// ESCENARIO D: Discrepancia de Monto y Pago Duplicado
CREATE (oc4:OrdenCompra {id: 'OC-1004', fecha: '2026-11-19', monto: 10000.00, moneda: 'MXN', estado: 'APROBADA'})
CREATE (rec4:Recepcion {id: 'REC-2004', fecha: '2026-11-20', cantidad_recibida: 20, estado: 'COMPLETA'})
CREATE (fac4:Factura {id: 'FAC-3004', uuid_fiscal: 'A1B2-0004', fecha: '2026-11-21', monto: 12500.00, estado: 'PAGADA'})
CREATE (pag4a:Pago {id: 'PAG-4004A', fecha: '2026-11-22', monto: 12500.00, metodo: 'SPEI', estado: 'LIQUIDADO'})
CREATE (pag4b:Pago {id: 'PAG-4004B', fecha: '2026-11-22', monto: 12500.00, metodo: 'SPEI', estado: 'LIQUIDADO'})

CREATE (u1)-[:CREA {timestamp: '2026-11-19T08:40:00'}]->(oc4)
CREATE (u2)-[:APRUEBA {timestamp: '2026-11-19T12:10:00'}]->(oc4)
CREATE (oc4)-[:DIRIGIDA_A]->(prov1)
CREATE (u3)-[:REGISTRA]->(rec4)
CREATE (rec4)-[:RESPALDA]->(oc4)
CREATE (fac4)-[:FACTURA_DE]->(oc4)
CREATE (fac4)-[:AMPARADA_POR]->(rec4)
CREATE (prov1)-[:EMITE]->(fac4)
CREATE (u5)-[:AUTORIZA_PAGO]->(pag4a)
CREATE (u5)-[:AUTORIZA_PAGO]->(pag4b)
CREATE (pag4a)-[:LIQUIDA]->(fac4)
CREATE (pag4b)-[:LIQUIDA]->(fac4);

MATCH (n) RETURN n;
