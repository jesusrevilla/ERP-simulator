// Where-Used (implosión) multinivel de un componente: padres directos e indirectos
MATCH p = (padre:Articulo)-[rels:REQUIRES*1..6]->(comp:Articulo {sku: $component_sku})
WHERE ($incluir_inactivos = true OR ALL(r IN rels WHERE r.estado = 'ACTIVO'))
RETURN padre.sku AS sku_afectado,
       padre.tipo_item AS tipo_item,
       length(p) AS profundidad,
       reduce(qty = 1.0, r IN rels | qty * r.cantidad) AS consumo_unitario_total,
       [n IN nodes(p) | n.sku] AS ruta_ensamble
ORDER BY profundidad ASC, sku_afectado ASC;

// Registro de la alerta de desabasto y su plan de mitigación
MERGE (c:Articulo {sku: $component_sku})
MERGE (al:AlertaDesabasto {alerta_id: $alerta_id})
SET al.nivel_riesgo = $nivel_riesgo,
    al.productos_terminados_afectados = $pt_afectados,
    al.plan_llm = $plan_llm
MERGE (al)-[:ORIGINA_EN]->(c)
RETURN al.alerta_id AS alerta_id;
