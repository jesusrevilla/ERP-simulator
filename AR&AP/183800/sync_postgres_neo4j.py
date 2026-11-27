#!/usr/bin/env python3
"""
sync_postgres_neo4j.py                                      Matrícula 183800

Sincroniza los documentos A/R-A/P de PostgreSQL con un Knowledge Graph en
Neo4j y conecta cada documento con sus eventos ISA-95.

Características
  * Idempotente: solo usa MERGE para crear nodos y relaciones. Ejecutarlo
    dos veces seguidas deja el grafo igual (la segunda corrida crea 0).
  * Nunca borra la base: no usa CREATE de nodos ni DETACH DELETE. Lo único que
    elimina son relaciones :SIGUIENTE de eventos que ya no corresponden al
    orden cronológico vigente.
  * PostgreSQL es la fuente oficial: solo se leen datos de ahí.
  * Dos modos: "completo" (todo) e "incremental" (solo documentos con
    fecha_creacion >= última sincronización; ver extraccion_incremental.sql).
  * Lee los eventos ISA-95 de Eventos_ISA95.json (3 formatos distintos) y los
    pasos del proceso de compras de eventos_ap.json.

Variables de entorno (las mismas de .env.example y de los workflows del repo)
  POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
  NEO4J_URI (opcional) o NEO4J_HOST + NEO4J_PORT, NEO4J_USER, NEO4J_PASSWORD

Uso
  python sync_postgres_neo4j.py                       # sincronización completa
  python sync_postgres_neo4j.py --modo incremental    # solo lo nuevo
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RUTA_SQL = CARPETA / "extraccion_incremental.sql"
RUTA_SCHEMA = CARPETA / "schema_neo4j_arap.cypher"
RUTA_EVENTOS = CARPETA.parent / "Eventos_ISA95.json"
RUTA_PASOS = CARPETA.parent / "eventos_ap.json"
RUTA_ESTADO = CARPETA / ".estado_sync_183800.json"

ZONA_POR_DEFECTO = "-06:00"  # los JSON declaran UTC-06:00
TAMANO_LOTE = 500
DESDE_SIEMPRE = "1900-01-01T00:00:00"

NIVELES_ISA95 = {
    0: "Proceso de producción (sensores y actuadores)",
    1: "PLC - sensado y manipulación",
    2: "SCADA - monitoreo y control supervisorio",
    3: "MES/WMS - operaciones de manufactura",
    4: "ERP - planeación de negocio y logística",
}

# --------------------------------------------------------------------------
# Modelo del grafo (nombres de etiquetas y relaciones = estándar del equipo)
# --------------------------------------------------------------------------
MAESTROS = {  # consulta -> (etiqueta, propiedad clave)
    "clientes": ("Cliente", "rfc"),
    "proveedores": ("Proveedor", "rfc"),
    "cuentas_contables": ("CuentaContable", "codigo"),
}
OPCIONALES = {"cuentas_contables"}  # si la tabla no existe se omite con aviso

DOCUMENTOS = {  # consulta -> (etiqueta, proceso)
    "pedidos_venta": ("PedidoVenta", "AR"),
    "facturas_cliente": ("FacturaCliente", "AR"),
    "cobros": ("Cobro", "AR"),
    "ordenes_compra": ("OrdenCompra", "AP"),
    "recepciones": ("Recepcion", "AP"),
    "facturas_proveedor": ("FacturaProveedor", "AP"),
    "pagos": ("Pago", "AP"),
}
# Columnas que solo sirven para armar relaciones; no se guardan como propiedad.
COLUMNAS_DE_ENLACE = {
    "cliente_rfc", "proveedor_rfc", "pedido_folio", "oc_folio", "recepcion_folio",
}

RELACIONES = [  # (consulta, origen, relación, destino, propiedades de la relación)
    # origen/destino = (etiqueta, propiedad clave, columna de la fila)
    ("pedidos_venta", ("Cliente", "rfc", "cliente_rfc"), "GENERA_PEDIDO",
     ("PedidoVenta", "folio", "folio"), ()),
    ("facturas_cliente", ("PedidoVenta", "folio", "pedido_folio"), "FACTURADO_EN",
     ("FacturaCliente", "folio", "folio"), ()),
    ("facturas_cliente", ("Cliente", "rfc", "cliente_rfc"), "TIENE_FACTURA",
     ("FacturaCliente", "folio", "folio"), ()),
    ("cobro_aplicaciones", ("Cobro", "folio", "cobro_folio"), "PAGA",
     ("FacturaCliente", "folio", "factura_folio"), ("monto_aplicado",)),
    ("ordenes_compra", ("Proveedor", "rfc", "proveedor_rfc"), "RECIBE_OC",
     ("OrdenCompra", "folio", "folio"), ()),
    ("recepciones", ("OrdenCompra", "folio", "oc_folio"), "SURTIDA_EN",
     ("Recepcion", "folio", "folio"), ()),
    ("facturas_proveedor", ("Recepcion", "folio", "recepcion_folio"), "CONCILIADA_EN",
     ("FacturaProveedor", "folio", "folio"), ()),
    ("facturas_proveedor", ("Proveedor", "rfc", "proveedor_rfc"), "TIENE_FACTURA",
     ("FacturaProveedor", "folio", "folio"), ()),
    ("pago_aplicaciones", ("Pago", "folio", "pago_folio"), "LIQUIDA",
     ("FacturaProveedor", "folio", "factura_folio"), ("monto_aplicado",)),
]

LINEAS = {  # consulta -> etiqueta del documento que INCLUYE el artículo
    "pedido_lineas": "PedidoVenta",
    "oc_lineas": "OrdenCompra",
}

# --------------------------------------------------------------------------
# Sentencias Cypher (todas con MERGE; las etiquetas salen de las constantes
# de arriba, nunca de datos externos)
# --------------------------------------------------------------------------
CYPHER_NIVELES = (
    "UNWIND $rows AS n "
    "MERGE (x:NivelISA95 {nivel: n.nivel}) "
    "SET x.nombre = n.nombre"
)

CYPHER_PASOS = (
    "UNWIND $rows AS p "
    "MERGE (x:PasoProceso {id: p.id}) "
    "SET x.tipo = p.tipo, x.nombre = p.nombre, x.descripcion = p.descripcion, x.carril = p.carril"
)

CYPHER_PASOS_ARISTAS = (
    "UNWIND $rows AS a "
    "MATCH (x:PasoProceso {id: a.de}) "
    "MATCH (y:PasoProceso {id: a.a}) "
    "MERGE (x)-[r:SIGUIENTE]->(y) "
    "SET r.condicion = a.condicion"
)

CYPHER_EVENTOS = (
    "UNWIND $rows AS ev "
    "MERGE (e:EventoISA95 {eventId: ev.eventId}) "
    "SET e.idOriginal = ev.idOriginal, e.fuente = ev.fuente, e.tipo = ev.tipo, "
    "e.timestamp = ev.timestamp, e.nivel = ev.nivel, e.nivel_inferido = ev.nivel_inferido, "
    "e.proceso = ev.proceso, e.actor = ev.actor, e.folio = ev.folio, "
    "e.folio_base = ev.folio_base, e.datos = ev.datos "
    "MERGE (n:NivelISA95 {nivel: ev.nivel}) "
    "MERGE (e)-[:DE_NIVEL]->(n) "
    "MERGE (a:AreaTrabajo {clave: ev.area_clave}) "
    "SET a.nombre = ev.area_nombre "
    "MERGE (e)-[:OCURRIO_EN]->(a)"
)

# Un evento es huérfano si declara un folio que no existe como documento.
CYPHER_EVENTOS_HUERFANOS = (
    "UNWIND $rows AS ev "
    "MATCH (e:EventoISA95 {eventId: ev.eventId}) "
    "OPTIONAL MATCH (d:Documento {folio: ev.folio}) "
    "WITH e, ev, count(d) AS coincidencias "
    "SET e.huerfano = (ev.folio IS NOT NULL AND coincidencias = 0)"
)

CYPHER_EVENTOS_DOCUMENTO = (
    "UNWIND $rows AS ev "
    "MATCH (e:EventoISA95 {eventId: ev.eventId}) "
    "MATCH (d:Documento {folio: ev.folio}) "
    "MERGE (e)-[:REGISTRADO_EN]->(d)"
)

CYPHER_EVENTOS_SIGUIENTE = (
    "UNWIND $rows AS p "
    "MATCH (a:EventoISA95 {eventId: p.de}) "
    "MATCH (b:EventoISA95 {eventId: p.a}) "
    "MERGE (a)-[:SIGUIENTE]->(b)"
)

# Única sentencia que elimina algo: relaciones SIGUIENTE ya no vigentes.
CYPHER_EVENTOS_SIGUIENTE_OBSOLETAS = (
    "MATCH (a:EventoISA95 {fuente: $fuente})-[r:SIGUIENTE]->(b:EventoISA95) "
    "WHERE NOT (a.eventId + '>' + b.eventId) IN $vigentes "
    "DELETE r"
)

CYPHER_CONTEO_NODOS = (
    "MATCH (n) UNWIND labels(n) AS etiqueta "
    "RETURN etiqueta, count(*) AS total ORDER BY etiqueta"
)
CYPHER_CONTEO_RELACIONES = (
    "MATCH ()-[r]->() RETURN type(r) AS tipo, count(*) AS total ORDER BY tipo"
)
CYPHER_CONTEO_HUERFANOS = (
    "MATCH (e:EventoISA95) "
    "RETURN e.proceso AS proceso, count(*) AS total, "
    "sum(CASE WHEN e.huerfano = true THEN 1 ELSE 0 END) AS huerfanos "
    "ORDER BY proceso"
)


def cypher_maestro(etiqueta: str, clave: str) -> str:
    return (
        f"UNWIND $rows AS row "
        f"MERGE (n:{etiqueta} {{{clave}: row.{clave}}}) "
        f"SET n += row.props"
    )


def cypher_documento(etiqueta: str) -> str:
    return (
        f"UNWIND $rows AS row "
        f"MERGE (n:{etiqueta} {{folio: row.folio}}) "
        f"SET n:Documento, n += row.props"
    )


def cypher_relacion(origen: tuple, rel: str, destino: tuple, props: tuple) -> str:
    la, ka, ca = origen
    lb, kb, cb = destino
    asignar = (" SET " + ", ".join(f"r.{p} = row.{p}" for p in props)) if props else ""
    return (
        f"UNWIND $rows AS row "
        f"MATCH (a:{la} {{{ka}: row.{ca}}}) "
        f"MATCH (b:{lb} {{{kb}: row.{cb}}}) "
        f"MERGE (a)-[r:{rel}]->(b){asignar}"
    )


def cypher_lineas(etiqueta: str) -> str:
    return (
        f"UNWIND $rows AS row "
        f"MATCH (d:{etiqueta} {{folio: row.documento_folio}}) "
        f"MERGE (a:Articulo {{nombre: row.articulo}}) "
        f"MERGE (d)-[r:INCLUYE]->(a) "
        f"SET r.cantidad = row.cantidad, r.precio_unitario = row.precio_unitario"
    )


def todas_las_sentencias_de_escritura() -> list[str]:
    """Todas las sentencias de datos que ejecuta el sincronizador (para auditarlas)."""
    s = [CYPHER_NIVELES, CYPHER_PASOS, CYPHER_PASOS_ARISTAS, CYPHER_EVENTOS,
         CYPHER_EVENTOS_HUERFANOS, CYPHER_EVENTOS_DOCUMENTO, CYPHER_EVENTOS_SIGUIENTE,
         CYPHER_EVENTOS_SIGUIENTE_OBSOLETAS]
    s += [cypher_maestro(e, k) for e, k in MAESTROS.values()]
    s += [cypher_documento(e) for e, _ in DOCUMENTOS.values()]
    s += [cypher_relacion(o, r, d, p) for _, o, r, d, p in RELACIONES]
    s += [cypher_lineas(e) for e in LINEAS.values()]
    return s


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------
def _limpiar(valor):
    """Convierte tipos de PostgreSQL a tipos que Neo4j acepta."""
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    return valor


def _en_lotes(filas: list, tamano: int = TAMANO_LOTE):
    for i in range(0, len(filas), tamano):
        yield filas[i:i + tamano]


def _como_lista(valor) -> list:
    if valor is None:
        return []
    return list(valor) if isinstance(valor, (list, tuple)) else [valor]


def leer_sentencias_cypher(ruta: Path = RUTA_SCHEMA) -> list[str]:
    """Separa un archivo .cypher en sentencias (quita comentarios // y separa por ;)."""
    lineas = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if linea.strip().startswith("//"):
            continue
        lineas.append(linea)
    return [s.strip() for s in "\n".join(lineas).split(";") if s.strip()]


def cargar_consultas(ruta: Path = RUTA_SQL) -> dict[str, str]:
    """Lee extraccion_incremental.sql: un bloque '-- name: x' por consulta."""
    texto = ruta.read_text(encoding="utf-8")
    partes = re.split(r"^--\s*name:\s*(\w+)\s*$", texto, flags=re.MULTILINE)
    consultas = {}
    for nombre, cuerpo in zip(partes[1::2], partes[2::2]):
        sql = "\n".join(
            l for l in cuerpo.splitlines() if not l.strip().startswith("--")
        ).strip().rstrip(";").strip()
        consultas[nombre] = sql.replace(":'desde'", "%(desde)s")
    return consultas


# --------------------------------------------------------------------------
# Eventos ISA-95 (Eventos_ISA95.json mezcla 3 formatos) y pasos del proceso
# --------------------------------------------------------------------------
def _iso(ts) -> str:
    """Devuelve ISO-8601 con zona horaria; si no trae zona usa UTC-06:00."""
    ts = str(ts).strip().replace(" ", "T", 1)
    if re.search(r"(Z|[+-]\d{2}:\d{2})$", ts):
        return ts
    return ts + ZONA_POR_DEFECTO


def _ruta_area(*partes) -> tuple[str, str]:
    """(clave, nombre) del área de trabajo a partir de la jerarquía ISA-95."""
    usadas = [str(p) for p in partes if p]
    return "/".join(usadas), (usadas[-1] if usadas else "SIN_AREA")


CLAVES_FOLIO_MENSAJE = (  # formato "messages": el primer id presente es el documento
    "apInvoiceId", "arInvoiceId", "goodsReceiptId", "purchaseOrderId", "productionOrderId",
)


def _evento_formato_events(fuente: str, e: dict) -> dict:
    h = e.get("isa95", {})
    doc = e.get("document") or {}
    clave, nombre = _ruta_area(h.get("enterprise"), h.get("site"), h.get("area"), h.get("workCenter"))
    return {
        "eventId": f"{fuente}-{e['eventId']}", "idOriginal": str(e["eventId"]), "fuente": fuente,
        "tipo": e.get("eventType"), "timestamp": _iso(e["timestamp"]),
        "nivel": int(h.get("level", 4)), "nivel_inferido": "level" not in h,
        "proceso": h.get("area"), "actor": e.get("actor"),
        "folio": doc.get("folio"), "folio_base": doc.get("base"),
        "area_clave": clave, "area_nombre": nombre,
        "datos": json.dumps(e.get("data", {}), ensure_ascii=False),
    }


def _evento_formato_messages(fuente: str, m: dict) -> dict:
    h = m.get("hierarchy", {})
    payload = m.get("payload", {})
    clave, nombre = _ruta_area(
        h.get("enterprise"), h.get("site"), h.get("area"),
        h.get("line"), h.get("cell"), h.get("machine"),
    )
    folio = next((payload[k] for k in CLAVES_FOLIO_MENSAJE if payload.get(k)), None)
    return {
        "eventId": f"{fuente}-{m['messageId']}", "idOriginal": str(m["messageId"]), "fuente": fuente,
        "tipo": m.get("eventType"), "timestamp": _iso(m["timestamp"]),
        "nivel": int(m.get("isa95Level", 4)), "nivel_inferido": "isa95Level" not in m,
        "proceso": m.get("process"), "actor": None,
        "folio": folio, "folio_base": None,
        "area_clave": clave, "area_nombre": nombre,
        "datos": json.dumps(payload, ensure_ascii=False),
    }


def _evento_formato_eventos(fuente: str, empresa: str, e: dict) -> dict:
    clave, nombre = _ruta_area(empresa, e.get("area"))
    datos = {k: e[k] for k in ("control", "riesgo") if k in e}
    return {
        "eventId": f"{fuente}-{e['id']}", "idOriginal": str(e["id"]), "fuente": fuente,
        "tipo": e.get("evento"), "timestamp": _iso(e["timestamp"]),
        "nivel": 4, "nivel_inferido": True,  # este formato no trae nivel: es un proceso de ERP
        "proceso": e.get("proceso"), "actor": None,
        "folio": None, "folio_base": None,   # tampoco trae folio de documento
        "area_clave": clave, "area_nombre": nombre,
        "datos": json.dumps(datos, ensure_ascii=False),
    }


def _eventos_de_contenido(fuente: str, c: dict) -> list[dict]:
    if "events" in c:
        return [_evento_formato_events(fuente, e) for e in c["events"]]
    if "messages" in c:
        return [_evento_formato_messages(fuente, m) for m in c["messages"]]
    if "eventos" in c:
        empresa = c.get("empresa") or ""
        return [_evento_formato_eventos(fuente, empresa, e) for e in c["eventos"]]
    print(f"AVISO: la fuente {fuente} no tiene un formato de eventos conocido; se omite.")
    return []


def normalizar_eventos(ruta: Path = RUTA_EVENTOS) -> list[dict]:
    """Lee Eventos_ISA95.json y devuelve todos los eventos con el mismo formato."""
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    eventos = []
    if "fuentes" in datos:
        for f in datos["fuentes"]:
            eventos += _eventos_de_contenido(str(f.get("matricula")), f.get("contenido", {}))
    else:
        eventos += _eventos_de_contenido(Path(ruta).stem, datos)
    return eventos


def pares_siguiente(eventos: list[dict]) -> dict[str, list[tuple[str, str]]]:
    """
    Cadena cronológica :SIGUIENTE. Se arma por (fuente, proceso): los eventos
    de una misma fuente y proceso se ordenan por fecha y cada uno apunta al
    siguiente. Devuelve {fuente: [(eventId, eventId_siguiente), ...]}.
    """
    grupos = defaultdict(list)
    for e in eventos:
        grupos[(e["fuente"], e["proceso"])].append(e)
    por_fuente = defaultdict(list)
    for (fuente, _), lista in grupos.items():
        lista.sort(key=lambda e: (datetime.fromisoformat(e["timestamp"]), e["eventId"]))
        for a, b in zip(lista, lista[1:]):
            por_fuente[fuente].append((a["eventId"], b["eventId"]))
    return dict(por_fuente)


def normalizar_pasos(ruta: Path = RUTA_PASOS) -> tuple[list[dict], list[dict]]:
    """Pasos del proceso de compras (eventos_ap.json) y sus transiciones."""
    crudos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    pasos, aristas, vistas = [], [], set()
    for p in crudos:
        pasos.append({k: p.get(k) for k in ("id", "tipo", "nombre", "descripcion", "carril")})
        transiciones = [(s, None) for s in _como_lista(p.get("siguiente"))]
        transiciones += [(r.get("siguiente"), r.get("condicion")) for r in p.get("ramas", [])]
        for destino, condicion in transiciones:
            if destino and (p["id"], destino) not in vistas:
                vistas.add((p["id"], destino))
                aristas.append({"de": p["id"], "a": destino, "condicion": condicion})
    return pasos, aristas


# --------------------------------------------------------------------------
# PostgreSQL
# --------------------------------------------------------------------------
def conectar_postgres():
    import psycopg2
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "erpdb"),
        user=os.getenv("POSTGRES_USER", "erp"),
        password=os.getenv("POSTGRES_PASSWORD", "erp"),
        sslmode=os.getenv("POSTGRES_SSLMODE", "prefer"),
    )


def extraer(conn, desde) -> dict[str, list[dict]]:
    """Ejecuta todas las consultas de extraccion_incremental.sql."""
    import psycopg2
    import psycopg2.extras

    resultado = {}
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        for nombre, sql in cargar_consultas().items():
            try:
                cur.execute(sql, {"desde": desde})
            except psycopg2.errors.UndefinedTable:
                conn.rollback()
                if nombre not in OPCIONALES:
                    raise
                print(f"AVISO: no existe la tabla de '{nombre}'; se omite.")
                resultado[nombre] = []
                continue
            resultado[nombre] = [
                {k: _limpiar(v) for k, v in fila.items()} for fila in cur.fetchall()
            ]
    conn.rollback()  # solo lecturas: cerramos la transacción sin cambios
    return resultado


# --------------------------------------------------------------------------
# Neo4j
# --------------------------------------------------------------------------
def conectar_neo4j():
    from neo4j import GraphDatabase
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    uri = os.getenv("NEO4J_URI", "")
    if not re.match(r"^(bolt|neo4j)(\+s|\+ssc)?://", uri):
        uri = f"bolt://{os.getenv('NEO4J_HOST', 'localhost')}:{os.getenv('NEO4J_PORT', '7687')}"
    usuario = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME") or "neo4j"
    clave = os.getenv("NEO4J_PASSWORD", "password")
    return GraphDatabase.driver(uri, auth=(usuario, clave))


class Contadores:
    """Suma lo que Neo4j reporta como creado en toda la corrida."""

    def __init__(self):
        self.nodos_creados = 0
        self.relaciones_creadas = 0
        self.propiedades_escritas = 0
        self.relaciones_borradas = 0

    def sumar(self, c) -> None:
        self.nodos_creados += c.nodes_created
        self.relaciones_creadas += c.relationships_created
        self.propiedades_escritas += c.properties_set
        self.relaciones_borradas += c.relationships_deleted

    def como_dict(self) -> dict:
        return dict(vars(self))


def _escribir(session, contadores: Contadores, cypher: str, **params) -> None:
    def trabajo(tx):
        return tx.run(cypher, **params).consume().counters

    contadores.sumar(session.execute_write(trabajo))


def _escribir_en_lotes(session, contadores, cypher, filas, clave="rows") -> None:
    for lote in _en_lotes(filas):
        _escribir(session, contadores, cypher, **{clave: lote})


def aplicar_schema(session, ruta: Path = RUTA_SCHEMA) -> int:
    sentencias = leer_sentencias_cypher(ruta)
    for s in sentencias:
        session.run(s).consume()
    return len(sentencias)


def cargar_grafo(session, datos: dict[str, list[dict]], contadores: Contadores) -> None:
    """Maestros -> documentos -> relaciones -> líneas (artículos)."""
    for consulta, (etiqueta, clave) in MAESTROS.items():
        filas = [{clave: f[clave], "props": f} for f in datos.get(consulta, [])]
        _escribir_en_lotes(session, contadores, cypher_maestro(etiqueta, clave), filas)

    for consulta, (etiqueta, proceso) in DOCUMENTOS.items():
        filas = []
        for f in datos.get(consulta, []):
            props = {k: v for k, v in f.items() if k not in COLUMNAS_DE_ENLACE}
            props.update(proceso=proceso, tipo_documento=etiqueta)
            filas.append({"folio": f["folio"], "props": props})
        _escribir_en_lotes(session, contadores, cypher_documento(etiqueta), filas)

    for consulta, origen, rel, destino, props in RELACIONES:
        filas = [
            f for f in datos.get(consulta, [])
            if f.get(origen[2]) is not None and f.get(destino[2]) is not None
        ]
        _escribir_en_lotes(session, contadores, cypher_relacion(origen, rel, destino, props), filas)

    for consulta, etiqueta in LINEAS.items():
        _escribir_en_lotes(session, contadores, cypher_lineas(etiqueta), datos.get(consulta, []))


def cargar_eventos(session, eventos: list[dict], contadores: Contadores) -> None:
    _escribir_en_lotes(
        session, contadores, CYPHER_NIVELES,
        [{"nivel": n, "nombre": t} for n, t in NIVELES_ISA95.items()],
    )
    for lote in _en_lotes(eventos):
        _escribir(session, contadores, CYPHER_EVENTOS, rows=lote)
        _escribir(session, contadores, CYPHER_EVENTOS_HUERFANOS, rows=lote)
        _escribir(session, contadores, CYPHER_EVENTOS_DOCUMENTO, rows=lote)
    for fuente, pares in pares_siguiente(eventos).items():
        _escribir_en_lotes(
            session, contadores, CYPHER_EVENTOS_SIGUIENTE,
            [{"de": a, "a": b} for a, b in pares],
        )
        _escribir(
            session, contadores, CYPHER_EVENTOS_SIGUIENTE_OBSOLETAS,
            fuente=fuente, vigentes=[f"{a}>{b}" for a, b in pares],
        )


def cargar_pasos(session, pasos: list[dict], aristas: list[dict], contadores: Contadores) -> None:
    _escribir_en_lotes(session, contadores, CYPHER_PASOS, pasos)
    _escribir_en_lotes(session, contadores, CYPHER_PASOS_ARISTAS, aristas)


def contar_grafo(session) -> dict:
    nodos = {r["etiqueta"]: r["total"] for r in session.run(CYPHER_CONTEO_NODOS)}
    rels = {r["tipo"]: r["total"] for r in session.run(CYPHER_CONTEO_RELACIONES)}
    huerfanos = {
        r["proceso"]: {"total": r["total"], "huerfanos": r["huerfanos"]}
        for r in session.run(CYPHER_CONTEO_HUERFANOS)
    }
    return {"nodos": nodos, "relaciones": rels, "eventos_por_proceso": huerfanos}


# --------------------------------------------------------------------------
# Estado de la sincronización incremental
# --------------------------------------------------------------------------
def leer_estado(ruta: Path = RUTA_ESTADO) -> dict:
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def guardar_estado(ruta: Path, marca: str) -> None:
    Path(ruta).write_text(json.dumps({"ultima_sincronizacion": marca}, indent=2), encoding="utf-8")


def marca_de_agua(datos: dict[str, list[dict]], anterior: str | None) -> str | None:
    """Mayor fecha_creacion vista; si no hubo filas se conserva la anterior."""
    vistas = [f["fecha_creacion"] for consulta in DOCUMENTOS for f in datos.get(consulta, [])
              if f.get("fecha_creacion")]
    return max(vistas) if vistas else anterior


# --------------------------------------------------------------------------
# Orquestador
# --------------------------------------------------------------------------
def sincronizar(conn_pg, driver, modo: str = "completo", ruta_eventos: Path | None = RUTA_EVENTOS,
                ruta_pasos: Path | None = RUTA_PASOS, ruta_estado: Path | None = RUTA_ESTADO,
                base_datos: str | None = None, log=print) -> dict:
    if modo not in ("completo", "incremental"):
        raise ValueError("modo debe ser 'completo' o 'incremental'")

    estado = leer_estado(ruta_estado) if ruta_estado else {}
    anterior = estado.get("ultima_sincronizacion")
    if modo == "incremental" and anterior:
        desde = anterior
    else:
        if modo == "incremental":
            log("AVISO: no hay sincronización previa; se hace una completa.")
        desde = DESDE_SIEMPRE

    log(f"== Sincronización PostgreSQL -> Neo4j (modo {modo}, desde {desde}) ==")
    datos = extraer(conn_pg, desde)
    log("Extraídos de PostgreSQL: " + ", ".join(f"{k}={len(v)}" for k, v in datos.items()))

    contadores = Contadores()
    kw = {"database": base_datos} if base_datos else {}
    with driver.session(**kw) as session:
        log(f"Constraints e índices aplicados: {aplicar_schema(session)}")
        cargar_grafo(session, datos, contadores)

        if ruta_pasos and Path(ruta_pasos).exists():
            pasos, aristas = normalizar_pasos(ruta_pasos)
            cargar_pasos(session, pasos, aristas, contadores)
            log(f"Pasos del proceso: {len(pasos)} nodos, {len(aristas)} transiciones")
        if ruta_eventos and Path(ruta_eventos).exists():
            eventos = normalizar_eventos(ruta_eventos)
            cargar_eventos(session, eventos, contadores)
            log(f"Eventos ISA-95: {len(eventos)}")

        grafo = contar_grafo(session)

    nueva = marca_de_agua(datos, anterior)
    if ruta_estado and nueva:
        guardar_estado(ruta_estado, nueva)

    c = contadores.como_dict()
    log(f"Creados en esta corrida: {c['nodos_creados']} nodos, {c['relaciones_creadas']} relaciones "
        f"({c['propiedades_escritas']} propiedades escritas)")
    log(f"Grafo actual: {sum(grafo['relaciones'].values())} relaciones; nodos por etiqueta: {grafo['nodos']}")
    log(f"Relaciones por tipo: {grafo['relaciones']}")
    log(f"Eventos por proceso (total / huérfanos): {grafo['eventos_por_proceso']}")
    return {"extraidos": {k: len(v) for k, v in datos.items()}, "creados": c,
            "grafo": grafo, "marca_de_agua": nueva}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Sincroniza PostgreSQL con el Knowledge Graph A/R-A/P en Neo4j")
    ap.add_argument("--modo", choices=("completo", "incremental"), default="completo")
    ap.add_argument("--eventos", type=Path, default=RUTA_EVENTOS, help="JSON de eventos ISA-95")
    ap.add_argument("--pasos", type=Path, default=RUTA_PASOS, help="JSON de pasos del proceso de compras")
    ap.add_argument("--estado", type=Path, default=RUTA_ESTADO, help="archivo con la marca de agua")
    ap.add_argument("--base-datos", default=None, help="base de datos de Neo4j (por defecto la predeterminada)")
    args = ap.parse_args(argv)

    conn = conectar_postgres()
    driver = conectar_neo4j()
    try:
        driver.verify_connectivity()
        sincronizar(conn, driver, args.modo, args.eventos, args.pasos, args.estado, args.base_datos)
    finally:
        conn.close()
        driver.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
