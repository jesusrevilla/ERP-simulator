// Tablas del modulo de Reglas de Orden de Compra (OC) y Orden de Produccion (OP).
// Las validaciones de la seccion 3 del documento (tipos de dato, campos
// obligatorios, estados del catalogo y cantidades nunca negativas) las aplica
// MongoDB con $jsonSchema: strict + error rechaza el insert o el update invalido.
//
// Uso: mongosh "mongodb://localhost:27017/erp_mrp" reglas_oc_y_op/esquema_mongodb.js

const CANTIDAD = { bsonType: ["int", "double"], minimum: 0 };          // nunca negativa
const CANTIDAD_POSITIVA = { bsonType: ["int", "double"], exclusiveMinimum: 0 };

const TABLAS = {
  // Toda OC debe tener asociado un proveedor activo
  proveedores: {
    required: ["_id", "nombre", "activo"],
    properties: {
      _id: { bsonType: "string", pattern: "^PROV-[0-9]{3}$" },
      nombre: { bsonType: "string", minLength: 3 },
      activo: { bsonType: "bool" }
    }
  },

  // Materia prima / componente
  materiales: {
    required: ["_id", "descripcion", "stock_fisico", "stock_reservado", "punto_reorden", "unidad_medida"],
    properties: {
      _id: { bsonType: "string", pattern: "^MP-[0-9]{2,4}$" },
      descripcion: { bsonType: "string", minLength: 3 },
      stock_fisico: CANTIDAD,
      stock_reservado: CANTIDAD,
      stock_transito: CANTIDAD,
      punto_reorden: CANTIDAD,
      unidad_medida: { enum: ["PZA", "KG", "LT", "MT", "CAJA"] }
    }
  },

  // Producto terminado con su lista de materiales (BOM)
  productos_terminados: {
    required: ["_id", "descripcion", "stock_fisico", "bom"],
    properties: {
      _id: { bsonType: "string", pattern: "^PT-[0-9]{2,4}$" },
      descripcion: { bsonType: "string", minLength: 3 },
      stock_fisico: CANTIDAD,
      bom_vigente: { bsonType: "bool" },
      bom: {
        bsonType: "array",
        minItems: 1,
        items: {
          bsonType: "object",
          required: ["material_id", "cantidad_requerida"],
          properties: {
            material_id: { bsonType: "string", pattern: "^MP-[0-9]{2,4}$" },
            cantidad_requerida: CANTIDAD_POSITIVA
          }
        }
      }
    }
  },

  // Orden de Compra
  ordenes_compra: {
    required: ["_id", "proveedor_id", "fecha_creacion", "items", "estado"],
    properties: {
      _id: { bsonType: "string", pattern: "^OC-[0-9]{3}$" },
      proveedor_id: { bsonType: "string", pattern: "^PROV-[0-9]{3}$" },
      fecha_creacion: { bsonType: "date" },
      estado: { enum: ["Pendiente", "Parcialmente Recibida", "Recibida", "Pagada", "Cancelada"] },
      items: {
        bsonType: "array",
        minItems: 1,
        items: {
          bsonType: "object",
          required: ["material_id", "cantidad", "precio_unitario"],
          properties: {
            material_id: { bsonType: "string", pattern: "^MP-[0-9]{2,4}$" },
            cantidad: CANTIDAD_POSITIVA,
            cantidad_recibida: CANTIDAD,
            precio_unitario: CANTIDAD
          }
        }
      }
    }
  },

  // Orden de Produccion
  ordenes_produccion: {
    required: ["_id", "producto_id", "cantidad_a_fabricar", "items_consumidos", "estado"],
    properties: {
      _id: { bsonType: "string", pattern: "^OP-[0-9]{3}$" },
      producto_id: { bsonType: "string", pattern: "^PT-[0-9]{2,4}$" },
      cantidad_a_fabricar: CANTIDAD_POSITIVA,
      estado: { enum: ["Planeada", "En Proceso", "Completada", "Cancelada"] },
      items_consumidos: {
        bsonType: "array",
        items: {
          bsonType: "object",
          required: ["material_id", "cantidad_requerida"],
          properties: {
            material_id: { bsonType: "string", pattern: "^MP-[0-9]{2,4}$" },
            cantidad_requerida: CANTIDAD_POSITIVA,
            cantidad_consumida: CANTIDAD
          }
        }
      }
    }
  },

  // Pronostico de ventas y pedidos reales (el pedido consume el forecast del periodo)
  forecast: {
    required: ["_id", "producto_id", "periodo", "cantidad"],
    properties: {
      _id: { bsonType: "string" },
      producto_id: { bsonType: "string", pattern: "^PT-[0-9]{2,4}$" },
      periodo: { bsonType: "string", pattern: "^[0-9]{4}-(0[1-9]|1[0-2])$" },
      cantidad: CANTIDAD
    }
  },

  pedidos_venta: {
    required: ["_id", "producto_id", "periodo", "cantidad"],
    properties: {
      _id: { bsonType: "string", pattern: "^PV-[0-9]{3}$" },
      producto_id: { bsonType: "string", pattern: "^PT-[0-9]{2,4}$" },
      periodo: { bsonType: "string", pattern: "^[0-9]{4}-(0[1-9]|1[0-2])$" },
      cantidad: CANTIDAD_POSITIVA
    }
  }
};

for (const [nombre, esquema] of Object.entries(TABLAS)) {
  const opciones = {
    validator: { $jsonSchema: { bsonType: "object", ...esquema } },
    validationLevel: "strict",
    validationAction: "error"
  };

  if (db.getCollectionNames().includes(nombre)) {
    db.runCommand({ collMod: nombre, ...opciones });
    print(`actualizada -> ${nombre}`);
  } else {
    db.createCollection(nombre, opciones);
    print(`creada      -> ${nombre}`);
  }
}

// Claves naturales unicas y apoyo a las consultas del MRP
db.proveedores.createIndex({ nombre: 1 }, { unique: true });
db.materiales.createIndex({ descripcion: 1 }, { unique: true });
db.materiales.createIndex({ punto_reorden: 1 });
db.productos_terminados.createIndex({ descripcion: 1 }, { unique: true });
db.ordenes_compra.createIndex({ proveedor_id: 1, estado: 1 });
db.ordenes_produccion.createIndex({ producto_id: 1, estado: 1 });
db.forecast.createIndex({ producto_id: 1, periodo: 1 }, { unique: true });

print(`\n${Object.keys(TABLAS).length} tablas del modulo OC/OP listas.`);
