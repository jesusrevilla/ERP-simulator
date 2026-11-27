// =====================================================================
//  Grafo de programación de órdenes de producción (Neo4j / Cypher)
//  Autor: Diego Luna Saucedo - 184814  ·  Issue #300
//
//  Modelo (nivel ORDEN, no nivel maestro de rutas):
//    (:Orden)-[:TIENE_ETAPA]->(:EtapaOrden)
//    (:EtapaOrden)-[:SIGUIENTE {dias_espera}]->(:EtapaOrden)
//    (:EtapaOrden)-[:EN_CENTRO]->(:CentroTrabajo)
//    (:EtapaOrden)-[:PROGRAMADA_EL {horas}]->(:Dia)
//
//  Todos los nodos llevan fuente = 'rutas_184814' para no mezclarse ni
//  borrar datos de otros compañeros si comparten la misma base Neo4j.
//
//  cargar_grafo.py lee este archivo: cada bloque empieza con una línea
//  "// @nombre". Los bloques de carga reciben $filas desde PostgreSQL.
//  Para probar una consulta en Neo4j Browser, define antes el parámetro,
//  por ejemplo:  :param etapa_id => 1
// =====================================================================

// @indice_orden
CREATE INDEX idx_orden_folio_184814 IF NOT EXISTS FOR (o:Orden) ON (o.folio);

// @indice_etapa
CREATE INDEX idx_etapa_orden_id_184814 IF NOT EXISTS FOR (e:EtapaOrden) ON (e.id);

// @indice_centro
CREATE INDEX idx_centro_codigo_184814 IF NOT EXISTS FOR (c:CentroTrabajo) ON (c.codigo);

// @indice_dia
CREATE INDEX idx_dia_fecha_184814 IF NOT EXISTS FOR (d:Dia) ON (d.fecha);

// @limpiar
MATCH (n {fuente: 'rutas_184814'}) DETACH DELETE n;

// ---------------------------------------------------------------------
// Carga (parámetro $filas: lista de mapas leídos de PostgreSQL)
// ---------------------------------------------------------------------

// @cargar_centros
UNWIND $filas AS f
MERGE (c:CentroTrabajo {codigo: f.codigo, fuente: 'rutas_184814'})
SET c.nombre = f.nombre,
    c.capacidad_horas_dia = f.capacidad_horas_dia;

// @cargar_ordenes
UNWIND $filas AS f
MERGE (o:Orden {folio: f.folio, fuente: 'rutas_184814'})
SET o.cantidad          = f.cantidad,
    o.estatus           = f.estatus,
    o.fecha_inicio      = date(f.fecha_inicio),
    o.fecha_fin         = date(f.fecha_fin),
    o.fecha_compromiso  = CASE WHEN f.fecha_compromiso IS NULL THEN NULL
                               ELSE date(f.fecha_compromiso) END,
    o.costo_planificado = f.costo_planificado;

// @cargar_etapas
UNWIND $filas AS f
MATCH (o:Orden {folio: f.folio, fuente: 'rutas_184814'})
MATCH (c:CentroTrabajo {codigo: f.centro, fuente: 'rutas_184814'})
MERGE (e:EtapaOrden {id: f.id, fuente: 'rutas_184814'})
SET e.folio        = f.folio,
    e.secuencia    = f.secuencia,
    e.etapa        = f.etapa,
    e.estatus      = f.estatus,
    e.dias_espera  = f.dias_espera,
    e.fecha_inicio = date(f.fecha_inicio),
    e.fecha_fin    = date(f.fecha_fin)
MERGE (o)-[:TIENE_ETAPA]->(e)
MERGE (e)-[:EN_CENTRO]->(c);

// @cargar_secuencia
// Une cada etapa con la siguiente de la misma orden; dias_espera es la
// espera de la etapa destino antes de iniciar.
MATCH (o:Orden {fuente: 'rutas_184814'})-[:TIENE_ETAPA]->(e:EtapaOrden)
WITH o, e ORDER BY e.secuencia
WITH o, collect(e) AS etapas
UNWIND range(0, size(etapas) - 2) AS i
WITH etapas[i] AS actual, etapas[i + 1] AS siguiente
MERGE (actual)-[r:SIGUIENTE]->(siguiente)
SET r.dias_espera = siguiente.dias_espera;

// @cargar_carga
UNWIND $filas AS f
MATCH (e:EtapaOrden {id: f.etapa_id, fuente: 'rutas_184814'})
MERGE (d:Dia {fecha: date(f.fecha), fuente: 'rutas_184814'})
MERGE (e)-[p:PROGRAMADA_EL]->(d)
SET p.horas = f.horas;

// ---------------------------------------------------------------------
// Consultas para los agentes
// ---------------------------------------------------------------------

// @propagacion_retraso
// Si la etapa $etapa_id se retrasa, ¿qué etapas posteriores de su orden se recorren?
// Decisión: el agente recalcula esas fechas (fn_registrar_retraso) y avisa.
MATCH (e:EtapaOrden {id: $etapa_id, fuente: 'rutas_184814'})-[:SIGUIENTE*1..]->(siguiente:EtapaOrden)
      <-[:TIENE_ETAPA]-(o:Orden)
WITH o, siguiente ORDER BY siguiente.secuencia
RETURN o.folio AS folio, collect(siguiente.secuencia) AS etapas_afectadas;

// @impacto_en_otras_ordenes
// Etapas de OTRAS órdenes que comparten centro y día con las etapas que se
// recorrerían por el retraso de $etapa_id. Son las que podrían chocar.
MATCH (e:EtapaOrden {id: $etapa_id, fuente: 'rutas_184814'})-[:SIGUIENTE*0..]->(afectada:EtapaOrden)
MATCH (afectada)-[:EN_CENTRO]->(c:CentroTrabajo)<-[:EN_CENTRO]-(otra:EtapaOrden)
WHERE otra.folio <> afectada.folio
  AND otra.fecha_inicio >= afectada.fecha_inicio
RETURN DISTINCT c.codigo AS centro_trabajo, otra.folio AS orden_en_riesgo,
       otra.secuencia AS etapa, otra.fecha_inicio AS inicio
ORDER BY inicio;

// @conflictos_centro_dia
// Órdenes que compiten por el mismo centro de trabajo el mismo día.
MATCH (c:CentroTrabajo {fuente: 'rutas_184814'})<-[:EN_CENTRO]-(e:EtapaOrden)-[p:PROGRAMADA_EL]->(d:Dia)
WITH c, d, sum(p.horas) AS horas, collect(DISTINCT e.folio) AS ordenes
WHERE size(ordenes) > 1
RETURN c.codigo AS centro_trabajo, d.fecha AS fecha, horas,
       c.capacidad_horas_dia AS capacidad, horas > c.capacidad_horas_dia AS sobrecargado,
       ordenes
ORDER BY fecha, centro_trabajo;

// @duracion_acumulada
// Recorre la cadena de etapas de cada orden: días laborables ocupados,
// días de espera y duración total en días naturales.
MATCH (o:Orden {fuente: 'rutas_184814'})-[:TIENE_ETAPA]->(primera:EtapaOrden)
WHERE NOT ()-[:SIGUIENTE]->(primera)
MATCH camino = (primera)-[:SIGUIENTE*0..]->(ultima:EtapaOrden)
WHERE NOT (ultima)-[:SIGUIENTE]->()
UNWIND nodes(camino) AS etapa
OPTIONAL MATCH (etapa)-[:PROGRAMADA_EL]->(d:Dia)
WITH o, primera, ultima, etapa, count(d) AS dias_etapa
RETURN o.folio AS folio,
       sum(dias_etapa) AS dias_laborables,
       sum(etapa.dias_espera) AS dias_espera,
       duration.inDays(primera.fecha_inicio, ultima.fecha_fin).days + 1 AS dias_naturales,
       ultima.fecha_fin AS fecha_fin,
       o.fecha_compromiso AS fecha_compromiso
ORDER BY folio;
