"""Módulo MongoDB para Compras, Recibos, Entregas e Inventario (ERP Simulator).

Incluye:
- Validadores formales $jsonSchema e índices únicos por colección.
- Reglas de negocio para Recibos (proveedor activo, no recibir de más salvo autorización gerencial,
  registro de piezas exactas/faltantes/dañadas y suma automática al aprobar).
- Reglas de negocio para Entregas (pedido aprobado y pagado o crédito autorizado, validación de
  stock físico suficiente, generación de nota de salida y resta automática).
- Integridad de datos (Entradas - Salidas = Stock actual, e inmutabilidad de registros cerrados).
"""

from __future__ import annotations

import copy
import os
import re
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple


class ERPValidationError(ValueError):
    """Error de validación de esquema o formato de datos."""


class BusinessRuleError(Exception):
    """Violación de una regla de negocio de Recibos o Entregas."""


class DataIntegrityError(Exception):
    """Violación de inmutabilidad o cuadre de inventario."""


# ---------------------------------------------------------------------------
# Validadores $jsonSchema oficiales de MongoDB por colección (Normalizados)
# ---------------------------------------------------------------------------

COLLECTION_VALIDATORS: Dict[str, Dict[str, Any]] = {
    "proveedores": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["codigo_proveedor", "nombre", "estatus", "activo", "creado_en"],
            "properties": {
                "codigo_proveedor": {"bsonType": "string", "minLength": 2},
                "nombre": {"bsonType": "string", "minLength": 2},
                "rfc": {"bsonType": ["string", "null"]},
                "email": {"bsonType": ["string", "null"]},
                "telefono": {"bsonType": ["string", "null"]},
                "estatus": {"enum": ["ACTIVO", "SUSPENDIDO", "BAJA"]},
                "activo": {"bsonType": "bool"},
                "creado_en": {"bsonType": "string"},
            },
        }
    },
    "clientes": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["codigo_cliente", "nombre", "estatus", "credito_autorizado", "activo"],
            "properties": {
                "codigo_cliente": {"bsonType": "string", "minLength": 2},
                "nombre": {"bsonType": "string", "minLength": 2},
                "estatus": {"enum": ["ACTIVO", "SUSPENDIDO", "BAJA"]},
                "credito_autorizado": {"bsonType": "bool"},
                "limite_credito": {"bsonType": ["int", "double"], "minimum": 0},
                "activo": {"bsonType": "bool"},
            },
        }
    },
    "almacenes": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["codigo_almacen", "nombre", "activo"],
            "properties": {
                "codigo_almacen": {"bsonType": "string", "minLength": 2},
                "nombre": {"bsonType": "string", "minLength": 2},
                "activo": {"bsonType": "bool"},
            },
        }
    },
    "productos": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["codigo_sku", "nombre", "unidad_medida", "peso_unitario_kg", "activo"],
            "properties": {
                "codigo_sku": {"bsonType": "string", "minLength": 2},
                "nombre": {"bsonType": "string", "minLength": 2},
                "unidad_medida": {"bsonType": "string", "minLength": 1},
                "peso_unitario_kg": {"bsonType": ["int", "double"], "minimum": 0},
                "stock_minimo": {"bsonType": ["int", "double"], "minimum": 0},
                "activo": {"bsonType": "bool"},
            },
        }
    },
    "inventario_stock": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["codigo_sku", "codigo_almacen", "stock_actual", "stock_danado"],
            "properties": {
                "codigo_sku": {"bsonType": "string", "minLength": 2},
                "codigo_almacen": {"bsonType": "string", "minLength": 2},
                "stock_actual": {"bsonType": ["int", "double"], "minimum": 0},
                "stock_danado": {"bsonType": ["int", "double"], "minimum": 0},
                "actualizado_en": {"bsonType": "string"},
            },
        }
    },
    "autorizaciones_gerenciales": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["codigo_autorizacion", "tipo_autorizacion", "gerente_nombre", "cantidad_extra_autorizada", "vigente"],
            "properties": {
                "codigo_autorizacion": {"bsonType": "string", "minLength": 3},
                "tipo_autorizacion": {"enum": ["EXCESO_RECIBO", "CREDITO_EXCEPCION"]},
                "gerente_nombre": {"bsonType": "string", "minLength": 2},
                "motivo": {"bsonType": "string"},
                "cantidad_extra_autorizada": {"bsonType": ["int", "double"], "minimum": 0},
                "vigente": {"bsonType": "bool"},
            },
        }
    },
    "ordenes_compra": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["codigo_oc", "codigo_proveedor", "codigo_almacen", "estado", "lineas"],
            "properties": {
                "codigo_oc": {"bsonType": "string", "minLength": 3},
                "codigo_proveedor": {"bsonType": "string"},
                "codigo_almacen": {"bsonType": "string"},
                "estado": {"enum": ["BORRADOR", "APROBADA", "PARCIAL", "RECIBIDA", "CANCELADA"]},
                "lineas": {
                    "bsonType": "array",
                    "minItems": 1,
                    "items": {
                        "bsonType": "object",
                        "required": ["codigo_sku", "cantidad_solicitada", "cantidad_recibida"],
                        "properties": {
                            "codigo_sku": {"bsonType": "string"},
                            "cantidad_solicitada": {"bsonType": ["int", "double"], "exclusiveMinimum": 0},
                            "cantidad_recibida": {"bsonType": ["int", "double"], "minimum": 0},
                            "costo_unitario": {"bsonType": ["int", "double"], "minimum": 0},
                        },
                    },
                },
            },
        }
    },
    "recibos_mercancia": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["codigo_recibo", "codigo_oc", "codigo_proveedor", "codigo_almacen", "estado", "lineas"],
            "properties": {
                "codigo_recibo": {"bsonType": "string", "minLength": 3},
                "codigo_oc": {"bsonType": "string"},
                "codigo_proveedor": {"bsonType": "string"},
                "codigo_almacen": {"bsonType": "string"},
                "autorizacion_gerencial": {"bsonType": ["string", "null"]},
                "estado": {"enum": ["BORRADOR", "EN_INSPECCION", "APROBADO", "RECHAZADO", "CERRADO"]},
                "lineas": {
                    "bsonType": "array",
                    "minItems": 1,
                    "items": {
                        "bsonType": "object",
                        "required": [
                            "codigo_sku",
                            "cantidad_esperada",
                            "cantidad_recibida",
                            "cantidad_aceptada",
                            "cantidad_faltante",
                            "cantidad_danada",
                            "estado_calidad",
                        ],
                        "properties": {
                            "codigo_sku": {"bsonType": "string"},
                            "cantidad_esperada": {"bsonType": ["int", "double"], "exclusiveMinimum": 0},
                            "cantidad_recibida": {"bsonType": ["int", "double"], "minimum": 0},
                            "cantidad_aceptada": {"bsonType": ["int", "double"], "minimum": 0},
                            "cantidad_faltante": {"bsonType": ["int", "double"], "minimum": 0},
                            "cantidad_danada": {"bsonType": ["int", "double"], "minimum": 0},
                            "estado_calidad": {
                                "enum": ["EXACTO", "FALTANTE", "DANADO", "PARCIAL_DANADO", "EXCESO_AUTORIZADO"]
                            },
                        },
                    },
                },
            },
        }
    },
    "ordenes_venta": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["codigo_ov", "codigo_cliente", "codigo_almacen", "estado_pedido", "estado_pago", "lineas"],
            "properties": {
                "codigo_ov": {"bsonType": "string", "minLength": 3},
                "codigo_cliente": {"bsonType": "string"},
                "codigo_almacen": {"bsonType": "string"},
                "estado_pedido": {"enum": ["BORRADOR", "APROBADO", "EN_DESPACHO", "DESPACHADO", "CANCELADO"]},
                "estado_pago": {"enum": ["PENDIENTE", "PAGADO", "CREDITO_AUTORIZADO", "RECHAZADO"]},
                "lineas": {
                    "bsonType": "array",
                    "minItems": 1,
                    "items": {
                        "bsonType": "object",
                        "required": ["codigo_sku", "cantidad_pedida", "cantidad_despachada"],
                        "properties": {
                            "codigo_sku": {"bsonType": "string"},
                            "cantidad_pedida": {"bsonType": ["int", "double"], "exclusiveMinimum": 0},
                            "cantidad_despachada": {"bsonType": ["int", "double"], "minimum": 0},
                        },
                    },
                },
            },
        }
    },
    "entregas_mercancia": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "codigo_entrega",
                "numero_nota_salida",
                "codigo_ov",
                "codigo_almacen",
                "estado",
                "peso_total_kg",
                "lineas",
            ],
            "properties": {
                "codigo_entrega": {"bsonType": "string", "minLength": 3},
                "numero_nota_salida": {"bsonType": "string", "minLength": 3},
                "codigo_ov": {"bsonType": "string"},
                "codigo_almacen": {"bsonType": "string"},
                "estado": {"enum": ["BORRADOR", "EMPACADO", "CONFIRMADA", "CERRADA", "CANCELADA"]},
                "peso_total_kg": {"bsonType": ["int", "double"], "minimum": 0},
                "lineas": {
                    "bsonType": "array",
                    "minItems": 1,
                    "items": {
                        "bsonType": "object",
                        "required": ["codigo_sku", "cantidad_entregada", "peso_subtotal_kg"],
                        "properties": {
                            "codigo_sku": {"bsonType": "string"},
                            "cantidad_entregada": {"bsonType": ["int", "double"], "exclusiveMinimum": 0},
                            "peso_subtotal_kg": {"bsonType": ["int", "double"], "minimum": 0},
                        },
                    },
                },
            },
        }
    },
    "movimientos_inventario": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "codigo_movimiento",
                "codigo_sku",
                "codigo_almacen",
                "tipo_movimiento",
                "documento_tipo",
                "documento_codigo",
                "cantidad",
                "signo",
                "stock_anterior",
                "stock_posterior",
                "fecha_movimiento",
            ],
            "properties": {
                "codigo_movimiento": {"bsonType": "string"},
                "codigo_sku": {"bsonType": "string"},
                "codigo_almacen": {"bsonType": "string"},
                "tipo_movimiento": {"enum": ["ENTRADA_RECIBO", "SALIDA_ENTREGA"]},
                "documento_tipo": {"enum": ["RECIBO", "ENTREGA"]},
                "documento_codigo": {"bsonType": "string"},
                "cantidad": {"bsonType": ["int", "double"], "exclusiveMinimum": 0},
                "signo": {"enum": [1, -1]},
                "stock_anterior": {"bsonType": ["int", "double"], "minimum": 0},
                "stock_posterior": {"bsonType": ["int", "double"], "minimum": 0},
                "fecha_movimiento": {"bsonType": "string"},
            },
        }
    },
}

UNIQUE_INDEXES: Dict[str, List[Tuple[List[Tuple[str, int]], str]]] = {
    "proveedores": [([("codigo_proveedor", 1)], "uq_proveedor_codigo")],
    "clientes": [([("codigo_cliente", 1)], "uq_cliente_codigo")],
    "almacenes": [([("codigo_almacen", 1)], "uq_almacen_codigo")],
    "productos": [([("codigo_sku", 1)], "uq_producto_sku")],
    "inventario_stock": [([("codigo_sku", 1), ("codigo_almacen", 1)], "uq_stock_sku_almacen")],
    "autorizaciones_gerenciales": [([("codigo_autorizacion", 1)], "uq_auth_codigo")],
    "ordenes_compra": [([("codigo_oc", 1)], "uq_oc_codigo")],
    "recibos_mercancia": [([("codigo_recibo", 1)], "uq_recibo_codigo")],
    "ordenes_venta": [([("codigo_ov", 1)], "uq_ov_codigo")],
    "entregas_mercancia": [
        ([("codigo_entrega", 1)], "uq_entrega_codigo"),
        ([("numero_nota_salida", 1)], "uq_nota_salida"),
    ],
    "movimientos_inventario": [([("codigo_movimiento", 1)], "uq_movimiento_codigo")],
}


# ---------------------------------------------------------------------------
# Funciones puras aisladas (Componentes para Pruebas Unitarias)
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sumar_inventario(stock_actual: float, cantidad_aceptada: float) -> float:
    """Suma mercancía aceptada al stock actual validando no-negatividad."""
    if isinstance(stock_actual, bool) or isinstance(cantidad_aceptada, bool):
        raise ERPValidationError("Las cantidades deben ser numéricas, no booleanas.")
    if stock_actual < 0 or cantidad_aceptada < 0:
        raise ERPValidationError("El stock y la cantidad aceptada deben ser >= 0.")
    resultado = Decimal(str(stock_actual)) + Decimal(str(cantidad_aceptada))
    return float(resultado.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def restar_inventario(stock_actual: float, cantidad_entregada: float) -> float:
    """Resta mercancía entregada validando stock físico suficiente (>= 0)."""
    if isinstance(stock_actual, bool) or isinstance(cantidad_entregada, bool):
        raise ERPValidationError("Las cantidades deben ser numéricas, no booleanas.")
    if stock_actual < 0 or cantidad_entregada <= 0:
        raise ERPValidationError("El stock debe ser >= 0 y la cantidad entregada > 0.")
    if Decimal(str(stock_actual)) < Decimal(str(cantidad_entregada)):
        raise BusinessRuleError(
            f"Stock insuficiente: disponible={stock_actual}, solicitado={cantidad_entregada}."
        )
    resultado = Decimal(str(stock_actual)) - Decimal(str(cantidad_entregada))
    return float(resultado.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def calcular_peso_paquete(items: List[Dict[str, float]]) -> float:
    """Calcula el peso total (kg) de un paquete de envío a 2 decimales."""
    total = Decimal("0.00")
    for item in items:
        peso = Decimal(str(item["peso_unitario_kg"]))
        qty = Decimal(str(item["cantidad"]))
        if peso < 0 or qty <= 0:
            raise ERPValidationError("Peso unitario >= 0 y cantidad > 0 requeridos.")
        total += peso * qty
    return float(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def clasificar_recepcion_linea(
    cantidad_esperada: float,
    cantidad_aceptada: float,
    cantidad_danada: float = 0.0,
) -> Dict[str, Any]:
    """Calcula recibida, faltante y estado de calidad de una línea de recibo."""
    if cantidad_esperada <= 0 or cantidad_aceptada < 0 or cantidad_danada < 0:
        raise ERPValidationError("Cantidades inválidas en la línea de recibo.")
    cantidad_recibida = cantidad_aceptada + cantidad_danada
    faltante = max(0.0, round(cantidad_esperada - cantidad_recibida, 4))

    if cantidad_recibida > cantidad_esperada:
        estado_calidad = "EXCESO_AUTORIZADO"
    elif cantidad_danada > 0 and cantidad_aceptada == 0:
        estado_calidad = "DANADO"
    elif cantidad_danada > 0:
        estado_calidad = "PARCIAL_DANADO"
    elif faltante > 0:
        estado_calidad = "FALTANTE"
    else:
        estado_calidad = "EXACTO"

    return {
        "cantidad_esperada": float(cantidad_esperada),
        "cantidad_recibida": float(cantidad_recibida),
        "cantidad_aceptada": float(cantidad_aceptada),
        "cantidad_faltante": float(faltante),
        "cantidad_danada": float(cantidad_danada),
        "estado_calidad": estado_calidad,
    }


# ---------------------------------------------------------------------------
# Adaptador en memoria compatible con PyMongo + validación $jsonSchema
# ---------------------------------------------------------------------------

def _matches_bson_type(value: Any, expected: Any) -> bool:
    types = expected if isinstance(expected, list) else [expected]
    for t in types:
        if t == "string" and isinstance(value, str):
            return True
        if t == "bool" and isinstance(value, bool):
            return True
        if t == "int" and isinstance(value, int) and not isinstance(value, bool):
            return True
        if t == "double" and isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
        if t == "array" and isinstance(value, list):
            return True
        if t == "object" and isinstance(value, dict):
            return True
        if t == "null" and value is None:
            return True
    return False


def validate_against_json_schema(doc: Dict[str, Any], schema: Dict[str, Any], path: str = "$") -> None:
    """Valida un documento contra un subconjunto estricto de MongoDB $jsonSchema."""
    root = schema.get("$jsonSchema", schema)
    if "bsonType" in root and not _matches_bson_type(doc, root["bsonType"]):
        raise ERPValidationError(f"{path}: tipo inválido, esperado {root['bsonType']}.")

    if isinstance(doc, dict):
        for req in root.get("required", []):
            if req not in doc:
                raise ERPValidationError(f"{path}.{req}: campo obligatorio faltante.")
        for field, rule in root.get("properties", {}).items():
            if field not in doc:
                continue
            val = doc[field]
            if "enum" in rule and val not in rule["enum"]:
                raise ERPValidationError(f"{path}.{field}: valor '{val}' fuera de enum {rule['enum']}.")
            if "bsonType" in rule and not _matches_bson_type(val, rule["bsonType"]):
                raise ERPValidationError(f"{path}.{field}: bsonType inválido.")
            if isinstance(val, str) and "minLength" in rule and len(val) < rule["minLength"]:
                raise ERPValidationError(f"{path}.{field}: longitud menor a {rule['minLength']}.")
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                if "minimum" in rule and val < rule["minimum"]:
                    raise ERPValidationError(f"{path}.{field}: valor {val} < minimum {rule['minimum']}.")
                if "exclusiveMinimum" in rule and val <= rule["exclusiveMinimum"]:
                    raise ERPValidationError(f"{path}.{field}: valor {val} <= {rule['exclusiveMinimum']}.")
            if isinstance(val, list):
                if "minItems" in rule and len(val) < rule["minItems"]:
                    raise ERPValidationError(f"{path}.{field}: requiere al menos {rule['minItems']} elemento(s).")
                if "items" in rule:
                    for idx, item in enumerate(val):
                        validate_against_json_schema(item, rule["items"], f"{path}.{field}[{idx}]")


class InMemoryCollection:
    """Colección en memoria compatible con la API básica de PyMongo."""

    def __init__(self, name: str, validator: Optional[Dict[str, Any]] = None) -> None:
        self.name = name
        self.validator = validator
        self.docs: List[Dict[str, Any]] = []
        self.indexes: List[Tuple[List[Tuple[str, int]], bool]] = []

    def create_index(self, keys: List[Tuple[str, int]], unique: bool = False, name: str = "") -> str:
        self.indexes.append((keys, unique))
        return name or "_".join(k for k, _ in keys)

    def _check_unique(self, doc: Dict[str, Any], ignore_idx: Optional[int] = None) -> None:
        for keys, unique in self.indexes:
            if not unique:
                continue
            candidate = tuple(doc.get(k) for k, _ in keys)
            for idx, existing in enumerate(self.docs):
                if ignore_idx is not None and idx == ignore_idx:
                    continue
                if tuple(existing.get(k) for k, _ in keys) == candidate:
                    raise ERPValidationError(f"Índice único duplicado en {self.name}: {candidate}")

    @staticmethod
    def _matches(doc: Dict[str, Any], filt: Dict[str, Any]) -> bool:
        for k, v in filt.items():
            if doc.get(k) != v:
                return False
        return True

    def insert_one(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        payload = copy.deepcopy(doc)
        if self.validator:
            validate_against_json_schema(payload, self.validator, self.name)
        self._check_unique(payload)
        self.docs.append(payload)
        return payload

    def find_one(self, filt: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for d in self.docs:
            if self._matches(d, filt):
                return copy.deepcopy(d)
        return None

    def find(self, filt: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        filt = filt or {}
        return [copy.deepcopy(d) for d in self.docs if self._matches(d, filt)]

    def update_one(self, filt: Dict[str, Any], update: Dict[str, Any], upsert: bool = False) -> None:
        for idx, d in enumerate(self.docs):
            if self._matches(d, filt):
                updated = copy.deepcopy(d)
                for k, v in update.get("$set", {}).items():
                    updated[k] = copy.deepcopy(v)
                for k, v in update.get("$inc", {}).items():
                    updated[k] = updated.get(k, 0) + v
                if self.validator:
                    validate_against_json_schema(updated, self.validator, self.name)
                self._check_unique(updated, ignore_idx=idx)
                self.docs[idx] = updated
                return
        if upsert:
            base = dict(filt)
            base.update(copy.deepcopy(update.get("$set", {})))
            for k, v in update.get("$inc", {}).items():
                base[k] = base.get(k, 0) + v
            self.insert_one(base)


class InMemoryDatabase:
    """Base de datos en memoria compatible con pymongo.database.Database."""

    def __init__(self) -> None:
        self._collections: Dict[str, InMemoryCollection] = {}

    def list_collection_names(self) -> List[str]:
        return list(self._collections.keys())

    def create_collection(self, name: str, validator: Optional[Dict[str, Any]] = None, **_: Any) -> InMemoryCollection:
        col = InMemoryCollection(name, validator=validator)
        self._collections[name] = col
        return col

    def command(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        if "collMod" in cmd:
            col_name = cmd["collMod"]
            if col_name in self._collections:
                self._collections[col_name].validator = cmd.get("validator")
        return {"ok": 1}

    def __getitem__(self, name: str) -> InMemoryCollection:
        if name not in self._collections:
            self._collections[name] = InMemoryCollection(name)
        return self._collections[name]


# ---------------------------------------------------------------------------
# Servicio ERP en MongoDB (Recibos, Entregas, Inventario e Integridad)
# ---------------------------------------------------------------------------

ESTADOS_CERRADOS = {"APROBADO", "CONFIRMADA", "CERRADO", "CERRADA"}


class RecibosEntregasMongoDB:
    """Orquestador de reglas de negocio sobre MongoDB para Recibos y Entregas."""

    def __init__(self, db: Any) -> None:
        self.db = db
        self.inicializar_esquema()

    @classmethod
    def from_env(cls) -> "RecibosEntregasMongoDB":
        from pymongo import MongoClient

        uri = os.getenv("MONGO_URI")
        if not uri:
            host = os.getenv("MONGO_HOST", "localhost")
            port = os.getenv("MONGO_PORT", "27017")
            uri = f"mongodb://{host}:{port}"
        db_name = os.getenv("MONGO_DB", "erpdb")
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        return cls(client[db_name])

    def inicializar_esquema(self) -> None:
        existing = set(self.db.list_collection_names())
        for name, validator in COLLECTION_VALIDATORS.items():
            if name not in existing:
                self.db.create_collection(
                    name,
                    validator=validator,
                    validationLevel="strict",
                    validationAction="error",
                )
            else:
                self.db.command(
                    {
                        "collMod": name,
                        "validator": validator,
                        "validationLevel": "strict",
                        "validationAction": "error",
                    }
                )
        for col_name, idx_list in UNIQUE_INDEXES.items():
            for keys, idx_name in idx_list:
                self.db[col_name].create_index(keys, unique=True, name=idx_name)

    # --- Maestros ---

    def registrar_proveedor(
        self,
        codigo_proveedor: str,
        nombre: str,
        estatus: str = "ACTIVO",
        rfc: Optional[str] = None,
        email: Optional[str] = None,
        telefono: Optional[str] = None,
    ) -> Dict[str, Any]:
        doc = {
            "codigo_proveedor": codigo_proveedor,
            "nombre": nombre,
            "rfc": rfc,
            "email": email,
            "telefono": telefono,
            "estatus": estatus,
            "activo": estatus == "ACTIVO",
            "creado_en": _utc_now_iso(),
        }
        return self.db["proveedores"].insert_one(doc)

    def registrar_cliente(
        self,
        codigo_cliente: str,
        nombre: str,
        estatus: str = "ACTIVO",
        credito_autorizado: bool = False,
        limite_credito: float = 0.0,
    ) -> Dict[str, Any]:
        doc = {
            "codigo_cliente": codigo_cliente,
            "nombre": nombre,
            "estatus": estatus,
            "credito_autorizado": credito_autorizado,
            "limite_credito": float(limite_credito),
            "activo": estatus == "ACTIVO",
        }
        return self.db["clientes"].insert_one(doc)

    def registrar_almacen(self, codigo_almacen: str, nombre: str) -> Dict[str, Any]:
        return self.db["almacenes"].insert_one(
            {"codigo_almacen": codigo_almacen, "nombre": nombre, "activo": True}
        )

    def registrar_producto(
        self,
        codigo_sku: str,
        nombre: str,
        unidad_medida: str = "PZA",
        peso_unitario_kg: float = 1.0,
        stock_minimo: float = 0.0,
    ) -> Dict[str, Any]:
        sku_norm = codigo_sku.strip().upper()
        if not sku_norm:
            raise ERPValidationError("El código SKU es obligatorio.")
        return self.db["productos"].insert_one(
            {
                "codigo_sku": sku_norm,
                "nombre": nombre,
                "unidad_medida": unidad_medida,
                "peso_unitario_kg": float(peso_unitario_kg),
                "stock_minimo": float(stock_minimo),
                "activo": True,
            }
        )

    def registrar_autorizacion_gerencial(
        self,
        codigo_autorizacion: str,
        tipo_autorizacion: str,
        gerente_nombre: str,
        motivo: str,
        cantidad_extra_autorizada: float,
        vigente: bool = True,
    ) -> Dict[str, Any]:
        return self.db["autorizaciones_gerenciales"].insert_one(
            {
                "codigo_autorizacion": codigo_autorizacion,
                "tipo_autorizacion": tipo_autorizacion,
                "gerente_nombre": gerente_nombre,
                "motivo": motivo,
                "cantidad_extra_autorizada": float(cantidad_extra_autorizada),
                "vigente": vigente,
            }
        )

    # --- Órdenes de Compra ---

    def crear_orden_compra(
        self,
        codigo_oc: str,
        codigo_proveedor: str,
        codigo_almacen: str,
        lineas: List[Dict[str, Any]],
        estado: str = "APROBADA",
    ) -> Dict[str, Any]:
        if not self.db["proveedores"].find_one({"codigo_proveedor": codigo_proveedor}):
            raise ERPValidationError(f"Proveedor '{codigo_proveedor}' no existe.")
        if not self.db["almacenes"].find_one({"codigo_almacen": codigo_almacen}):
            raise ERPValidationError(f"Almacén '{codigo_almacen}' no existe.")
        norm_lines = []
        for l in lineas:
            sku = l["codigo_sku"].strip().upper()
            if not self.db["productos"].find_one({"codigo_sku": sku}):
                raise ERPValidationError(f"Producto '{sku}' no existe.")
            norm_lines.append(
                {
                    "codigo_sku": sku,
                    "cantidad_solicitada": float(l["cantidad_solicitada"]),
                    "cantidad_recibida": 0.0,
                    "costo_unitario": float(l.get("costo_unitario", 0.0)),
                }
            )
        return self.db["ordenes_compra"].insert_one(
            {
                "codigo_oc": codigo_oc,
                "codigo_proveedor": codigo_proveedor,
                "codigo_almacen": codigo_almacen,
                "estado": estado,
                "lineas": norm_lines,
                "creado_en": _utc_now_iso(),
            }
        )

    # --- Módulo de Recibos (Inbound) ---

    def registrar_recibo(
        self,
        codigo_recibo: str,
        codigo_oc: str,
        lineas_recibo: List[Dict[str, Any]],
        usuario_registro: str,
        autorizacion_gerencial: Optional[str] = None,
    ) -> Dict[str, Any]:
        oc = self.db["ordenes_compra"].find_one({"codigo_oc": codigo_oc})
        if not oc:
            raise BusinessRuleError(f"La orden de compra '{codigo_oc}' no existe.")
        if oc["estado"] not in ("APROBADA", "PARCIAL"):
            raise BusinessRuleError(
                f"La OC '{codigo_oc}' debe estar APROBADA o PARCIAL (actual: {oc['estado']})."
            )

        proveedor = self.db["proveedores"].find_one({"codigo_proveedor": oc["codigo_proveedor"]})
        if not proveedor or proveedor["estatus"] != "ACTIVO" or not proveedor["activo"]:
            estatus = proveedor["estatus"] if proveedor else "INEXISTENTE"
            raise BusinessRuleError(
                f"Regla de negocio (Proveedor activo): No se puede registrar recibo para proveedor en estado {estatus}."
            )

        oc_lines = {l["codigo_sku"]: l for l in oc["lineas"]}
        extra_autorizado = 0.0
        if autorizacion_gerencial:
            auth = self.db["autorizaciones_gerenciales"].find_one(
                {"codigo_autorizacion": autorizacion_gerencial}
            )
            if not auth or not auth["vigente"] or auth["tipo_autorizacion"] != "EXCESO_RECIBO":
                raise BusinessRuleError(
                    f"Autorización gerencial '{autorizacion_gerencial}' inválida o no vigente."
                )
            extra_autorizado = float(auth["cantidad_extra_autorizada"])

        detalle_normalizado: List[Dict[str, Any]] = []
        for item in lineas_recibo:
            sku = item["codigo_sku"].strip().upper()
            if sku not in oc_lines:
                raise BusinessRuleError(f"El SKU '{sku}' no pertenece a la OC '{codigo_oc}'.")
            oc_line = oc_lines[sku]
            pendiente = oc_line["cantidad_solicitada"] - oc_line["cantidad_recibida"]
            aceptada = float(item["cantidad_aceptada"])
            danada = float(item.get("cantidad_danada", 0.0))
            recibida_total = aceptada + danada

            if recibida_total > pendiente:
                if not autorizacion_gerencial:
                    raise BusinessRuleError(
                        f"Regla de negocio (No recibir de más): SKU '{sku}' intenta recibir {recibida_total} "
                        f"contra pendiente {pendiente} sin autorización gerencial."
                    )
                if recibida_total > (pendiente + extra_autorizado):
                    raise BusinessRuleError(
                        f"SKU '{sku}' excede incluso el límite con autorización gerencial "
                        f"({pendiente + extra_autorizado})."
                    )

            clasificada = clasificar_recepcion_linea(
                cantidad_esperada=pendiente,
                cantidad_aceptada=aceptada,
                cantidad_danada=danada,
            )
            clasificada["codigo_sku"] = sku
            if "lote" in item:
                clasificada["lote"] = item["lote"]
            detalle_normalizado.append(clasificada)

        recibo_doc = {
            "codigo_recibo": codigo_recibo,
            "codigo_oc": codigo_oc,
            "codigo_proveedor": oc["codigo_proveedor"],
            "codigo_almacen": oc["codigo_almacen"],
            "autorizacion_gerencial": autorizacion_gerencial,
            "estado": "BORRADOR",
            "usuario_registro": usuario_registro,
            "fecha_recepcion": _utc_now_iso(),
            "lineas": detalle_normalizado,
        }
        return self.db["recibos_mercancia"].insert_one(recibo_doc)

    def aprobar_recibo(self, codigo_recibo: str, usuario_aprueba: str) -> Dict[str, Any]:
        recibo = self.db["recibos_mercancia"].find_one({"codigo_recibo": codigo_recibo})
        if not recibo:
            raise BusinessRuleError(f"Recibo '{codigo_recibo}' no existe.")
        if recibo["estado"] in ESTADOS_CERRADOS:
            raise DataIntegrityError(
                f"Integridad de datos: El recibo '{codigo_recibo}' ya fue {recibo['estado']} y es inmutable."
            )
        if recibo["estado"] == "RECHAZADO":
            raise BusinessRuleError(f"No se puede aprobar un recibo RECHAZADO ('{codigo_recibo}').")

        almacen = recibo["codigo_almacen"]
        oc = self.db["ordenes_compra"].find_one({"codigo_oc": recibo["codigo_oc"]})
        oc_lines = {l["codigo_sku"]: l for l in oc["lineas"]}

        for linea in recibo["lineas"]:
            sku = linea["codigo_sku"]
            stock_doc = self.db["inventario_stock"].find_one(
                {"codigo_sku": sku, "codigo_almacen": almacen}
            )
            stock_prev = float(stock_doc["stock_actual"]) if stock_doc else 0.0
            danado_prev = float(stock_doc["stock_danado"]) if stock_doc else 0.0
            aceptada = float(linea["cantidad_aceptada"])
            danada = float(linea["cantidad_danada"])
            stock_post = sumar_inventario(stock_prev, aceptada)

            self.db["inventario_stock"].update_one(
                {"codigo_sku": sku, "codigo_almacen": almacen},
                {
                    "$set": {
                        "stock_actual": stock_post,
                        "stock_danado": round(danado_prev + danada, 4),
                        "actualizado_en": _utc_now_iso(),
                    }
                },
                upsert=True,
            )

            if aceptada > 0:
                self.db["movimientos_inventario"].insert_one(
                    {
                        "codigo_movimiento": f"MOV-{codigo_recibo}-{sku}",
                        "codigo_sku": sku,
                        "codigo_almacen": almacen,
                        "tipo_movimiento": "ENTRADA_RECIBO",
                        "documento_tipo": "RECIBO",
                        "documento_codigo": codigo_recibo,
                        "cantidad": aceptada,
                        "signo": 1,
                        "stock_anterior": stock_prev,
                        "stock_posterior": stock_post,
                        "usuario_registro": usuario_aprueba,
                        "fecha_movimiento": _utc_now_iso(),
                    }
                )

            oc_lines[sku]["cantidad_recibida"] = round(
                oc_lines[sku]["cantidad_recibida"] + aceptada, 4
            )

        nuevas_lineas_oc = list(oc_lines.values())
        completo = all(l["cantidad_recibida"] >= l["cantidad_solicitada"] for l in nuevas_lineas_oc)
        self.db["ordenes_compra"].update_one(
            {"codigo_oc": oc["codigo_oc"]},
            {"$set": {"lineas": nuevas_lineas_oc, "estado": "RECIBIDA" if completo else "PARCIAL"}},
        )

        self.db["recibos_mercancia"].update_one(
            {"codigo_recibo": codigo_recibo},
            {"$set": {"estado": "APROBADO", "fecha_aprobacion": _utc_now_iso()}},
        )
        return self.db["recibos_mercancia"].find_one({"codigo_recibo": codigo_recibo})

    # --- Órdenes de Venta y Módulo de Entregas (Outbound) ---

    def crear_orden_venta(
        self,
        codigo_ov: str,
        codigo_cliente: str,
        codigo_almacen: str,
        lineas: List[Dict[str, Any]],
        estado_pedido: str = "APROBADO",
        estado_pago: str = "PAGADO",
    ) -> Dict[str, Any]:
        if not self.db["clientes"].find_one({"codigo_cliente": codigo_cliente}):
            raise ERPValidationError(f"Cliente '{codigo_cliente}' no existe.")
        if not self.db["almacenes"].find_one({"codigo_almacen": codigo_almacen}):
            raise ERPValidationError(f"Almacén '{codigo_almacen}' no existe.")
        norm_lines = []
        for l in lineas:
            sku = l["codigo_sku"].strip().upper()
            if not self.db["productos"].find_one({"codigo_sku": sku}):
                raise ERPValidationError(f"Producto '{sku}' no existe.")
            norm_lines.append(
                {
                    "codigo_sku": sku,
                    "cantidad_pedida": float(l["cantidad_pedida"]),
                    "cantidad_despachada": 0.0,
                }
            )
        return self.db["ordenes_venta"].insert_one(
            {
                "codigo_ov": codigo_ov,
                "codigo_cliente": codigo_cliente,
                "codigo_almacen": codigo_almacen,
                "estado_pedido": estado_pedido,
                "estado_pago": estado_pago,
                "lineas": norm_lines,
                "creado_en": _utc_now_iso(),
            }
        )

    def registrar_entrega(
        self,
        codigo_entrega: str,
        codigo_ov: str,
        lineas_entrega: List[Dict[str, Any]],
        usuario_despacho: str,
        numero_nota_salida: Optional[str] = None,
    ) -> Dict[str, Any]:
        ov = self.db["ordenes_venta"].find_one({"codigo_ov": codigo_ov})
        if not ov:
            raise BusinessRuleError(f"La orden de venta '{codigo_ov}' no existe.")
        if ov["estado_pedido"] not in ("APROBADO", "EN_DESPACHO"):
            raise BusinessRuleError(
                f"Regla de negocio (Estado del pedido): OV '{codigo_ov}' debe estar APROBADO (actual: {ov['estado_pedido']})."
            )
        if ov["estado_pago"] not in ("PAGADO", "CREDITO_AUTORIZADO"):
            raise BusinessRuleError(
                f"Regla de negocio (Pago/Crédito): OV '{codigo_ov}' requiere PAGADO o CREDITO_AUTORIZADO (actual: {ov['estado_pago']})."
            )

        ov_lines = {l["codigo_sku"]: l for l in ov["lineas"]}
        almacen = ov["codigo_almacen"]
        peso_items: List[Dict[str, float]] = []
        lineas_paquete: List[Dict[str, Any]] = []

        for item in lineas_entrega:
            sku = item["codigo_sku"].strip().upper()
            qty = float(item["cantidad_entregada"])
            if sku not in ov_lines:
                raise BusinessRuleError(f"El SKU '{sku}' no pertenece a la OV '{codigo_ov}'.")
            pendiente_ov = ov_lines[sku]["cantidad_pedida"] - ov_lines[sku]["cantidad_despachada"]
            if qty > pendiente_ov:
                raise BusinessRuleError(
                    f"No se puede entregar {qty} de '{sku}'; pendiente en OV es {pendiente_ov}."
                )

            stock_doc = self.db["inventario_stock"].find_one(
                {"codigo_sku": sku, "codigo_almacen": almacen}
            )
            stock_actual = float(stock_doc["stock_actual"]) if stock_doc else 0.0
            restar_inventario(stock_actual, qty)  # Valida stock físico suficiente

            prod = self.db["productos"].find_one({"codigo_sku": sku})
            peso_unit = float(prod["peso_unitario_kg"])
            peso_sub = calcular_peso_paquete([{"peso_unitario_kg": peso_unit, "cantidad": qty}])
            peso_items.append({"peso_unitario_kg": peso_unit, "cantidad": qty})
            lineas_paquete.append(
                {"codigo_sku": sku, "cantidad_entregada": qty, "peso_subtotal_kg": peso_sub}
            )

        nota_salida = numero_nota_salida or f"NS-{re.sub(r'[^A-Z0-9-]', '', codigo_entrega.upper())}"
        entrega_doc = {
            "codigo_entrega": codigo_entrega,
            "numero_nota_salida": nota_salida,
            "codigo_ov": codigo_ov,
            "codigo_almacen": almacen,
            "estado": "EMPACADO",
            "peso_total_kg": calcular_peso_paquete(peso_items),
            "usuario_despacho": usuario_despacho,
            "fecha_entrega": _utc_now_iso(),
            "lineas": lineas_paquete,
        }
        return self.db["entregas_mercancia"].insert_one(entrega_doc)

    def confirmar_entrega(self, codigo_entrega: str, usuario_confirma: str) -> Dict[str, Any]:
        entrega = self.db["entregas_mercancia"].find_one({"codigo_entrega": codigo_entrega})
        if not entrega:
            raise BusinessRuleError(f"Entrega '{codigo_entrega}' no existe.")
        if entrega["estado"] in ESTADOS_CERRADOS:
            raise DataIntegrityError(
                f"Integridad de datos: La entrega '{codigo_entrega}' ya está {entrega['estado']} y es inmutable."
            )

        ov = self.db["ordenes_venta"].find_one({"codigo_ov": entrega["codigo_ov"]})
        if ov["estado_pedido"] not in ("APROBADO", "EN_DESPACHO") or ov["estado_pago"] not in (
            "PAGADO",
            "CREDITO_AUTORIZADO",
        ):
            raise BusinessRuleError("La orden de venta ya no cumple condiciones de despacho.")

        almacen = entrega["codigo_almacen"]
        ov_lines = {l["codigo_sku"]: l for l in ov["lineas"]}

        # Pre-validación de todo el paquete antes de mutar inventario (atomicidad lógica)
        stocks_prev: Dict[str, float] = {}
        for linea in entrega["lineas"]:
            sku = linea["codigo_sku"]
            stock_doc = self.db["inventario_stock"].find_one(
                {"codigo_sku": sku, "codigo_almacen": almacen}
            )
            stock_prev = float(stock_doc["stock_actual"]) if stock_doc else 0.0
            restar_inventario(stock_prev, float(linea["cantidad_entregada"]))
            stocks_prev[sku] = stock_prev

        for linea in entrega["lineas"]:
            sku = linea["codigo_sku"]
            qty = float(linea["cantidad_entregada"])
            stock_prev = stocks_prev[sku]
            stock_post = restar_inventario(stock_prev, qty)

            self.db["inventario_stock"].update_one(
                {"codigo_sku": sku, "codigo_almacen": almacen},
                {"$set": {"stock_actual": stock_post, "actualizado_en": _utc_now_iso()}},
            )
            self.db["movimientos_inventario"].insert_one(
                {
                    "codigo_movimiento": f"MOV-{codigo_entrega}-{sku}",
                    "codigo_sku": sku,
                    "codigo_almacen": almacen,
                    "tipo_movimiento": "SALIDA_ENTREGA",
                    "documento_tipo": "ENTREGA",
                    "documento_codigo": codigo_entrega,
                    "cantidad": qty,
                    "signo": -1,
                    "stock_anterior": stock_prev,
                    "stock_posterior": stock_post,
                    "usuario_registro": usuario_confirma,
                    "fecha_movimiento": _utc_now_iso(),
                }
            )
            ov_lines[sku]["cantidad_despachada"] = round(ov_lines[sku]["cantidad_despachada"] + qty, 4)

        nuevas_lineas_ov = list(ov_lines.values())
        completo = all(l["cantidad_despachada"] >= l["cantidad_pedida"] for l in nuevas_lineas_ov)
        self.db["ordenes_venta"].update_one(
            {"codigo_ov": ov["codigo_ov"]},
            {"$set": {"lineas": nuevas_lineas_ov, "estado_pedido": "DESPACHADO" if completo else "EN_DESPACHO"}},
        )
        self.db["entregas_mercancia"].update_one(
            {"codigo_entrega": codigo_entrega},
            {
                "$set": {
                    "estado": "CONFIRMADA",
                    "fecha_confirmacion": _utc_now_iso(),
                    "comprobante_salida": {
                        "numero_nota_salida": entrega["numero_nota_salida"],
                        "codigo_ov": entrega["codigo_ov"],
                        "peso_total_kg": entrega["peso_total_kg"],
                        "emitido_por": usuario_confirma,
                    },
                }
            },
        )
        return self.db["entregas_mercancia"].find_one({"codigo_entrega": codigo_entrega})

    # --- Integridad de datos e inmutabilidad ---

    def modificar_recibo(self, codigo_recibo: str, cambios: Dict[str, Any]) -> Dict[str, Any]:
        recibo = self.db["recibos_mercancia"].find_one({"codigo_recibo": codigo_recibo})
        if not recibo:
            raise ERPValidationError(f"Recibo '{codigo_recibo}' no existe.")
        if recibo["estado"] in ESTADOS_CERRADOS:
            raise DataIntegrityError(
                f"Integridad de datos: El recibo '{codigo_recibo}' está cerrado/aprobado y no puede alterarse."
            )
        self.db["recibos_mercancia"].update_one({"codigo_recibo": codigo_recibo}, {"$set": cambios})
        return self.db["recibos_mercancia"].find_one({"codigo_recibo": codigo_recibo})

    def eliminar_documento(self, coleccion: str, campo_codigo: str, codigo: str) -> None:
        if coleccion == "movimientos_inventario":
            raise DataIntegrityError("Integridad de datos: El kardex de movimientos es inmutable.")
        doc = self.db[coleccion].find_one({campo_codigo: codigo})
        if not doc:
            raise ERPValidationError(f"Documento '{codigo}' no encontrado en {coleccion}.")
        if doc.get("estado") in ESTADOS_CERRADOS:
            raise DataIntegrityError(
                f"Integridad de datos: No se puede eliminar un registro cerrado ({codigo})."
            )
        raise DataIntegrityError("Se requiere borrado lógico/cancelación de estado, no eliminación física.")

    def consultar_stock(self, codigo_sku: str, codigo_almacen: str) -> Dict[str, float]:
        doc = self.db["inventario_stock"].find_one(
            {"codigo_sku": codigo_sku.strip().upper(), "codigo_almacen": codigo_almacen}
        )
        if not doc:
            return {"stock_actual": 0.0, "stock_danado": 0.0}
        return {"stock_actual": float(doc["stock_actual"]), "stock_danado": float(doc["stock_danado"])}

    def verificar_cuadre_inventario(self, codigo_sku: str, codigo_almacen: str) -> Dict[str, Any]:
        """Comprueba la ecuación fundamental: Entradas - Salidas = Stock actual."""
        sku = codigo_sku.strip().upper()
        movimientos = self.db["movimientos_inventario"].find(
            {"codigo_sku": sku, "codigo_almacen": codigo_almacen}
        )
        entradas = sum(float(m["cantidad"]) for m in movimientos if m["signo"] == 1)
        salidas = sum(float(m["cantidad"]) for m in movimientos if m["signo"] == -1)
        stock_kardex = round(entradas - salidas, 4)
        stock_actual = self.consultar_stock(sku, codigo_almacen)["stock_actual"]
        diferencia = round(stock_actual - stock_kardex, 4)
        return {
            "codigo_sku": sku,
            "codigo_almacen": codigo_almacen,
            "entradas": round(entradas, 4),
            "salidas": round(salidas, 4),
            "stock_calculado": stock_kardex,
            "stock_actual": stock_actual,
            "diferencia": diferencia,
            "cuadra": diferencia == 0.0,
        }
