"""Pruebas del proceso de componentes descontinuados en BOM (matrícula 181914, issue #239)."""

import pytest

from BOM.Descontinuados_181914.gestor_descontinuados import (
    ACTIVO,
    DESCONTINUADO,
    DEMANDA_PEDIDO,
    PROXIMO_A_DESCONTINUAR,
    ROL_RESPONSABLE_BOM,
    ROL_RESPONSABLE_TECNICO,
    ErrorDeProceso,
    Recomendacion,
    ejecutar_escenario,
    escenario_tarjeta_madre,
    utc,
)

MB = "MB-B550-PLUS"
T0 = utc("2026-11-20T09:00:00")


@pytest.fixture
def erp():
    return escenario_tarjeta_madre()


@pytest.fixture
def erp_descontinuado(erp):
    erp.cambiar_estado(MB, DESCONTINUADO, T0, usuario="comprador01")
    return erp


# --- Ciclo de vida -----------------------------------------------------------

def test_transicion_invalida_desde_descontinuado(erp_descontinuado):
    with pytest.raises(ErrorDeProceso):
        erp_descontinuado.cambiar_estado(MB, ACTIVO, T0, usuario="x")


def test_estado_desconocido_rechazado(erp):
    with pytest.raises(ErrorDeProceso):
        erp.cambiar_estado(MB, "OBSOLETO", T0, usuario="x")


def test_cambio_de_estado_queda_en_historial(erp_descontinuado):
    registro = erp_descontinuado.historial[0]
    assert registro["tipo"] == "CAMBIO_CICLO_VIDA"
    assert (registro["anterior"], registro["nuevo"]) == (ACTIVO, DESCONTINUADO)


# --- Detección multinivel -----------------------------------------------------

def test_where_used_multinivel(erp):
    afectadas = {b["bom_id"]: b["nivel"] for b in erp.boms_afectadas(MB)}
    assert afectadas == {
        "ENS-BASE-AM4-v1": 1,
        "PC-WS-300-v1": 1,
        "PC-OFI-100-v1": 2,
        "PC-GAM-200-v1": 2,
    }
    assert "PC-MINI-400-v1" not in afectadas


def test_alerta_critica_con_ordenes_y_cobertura_insuficiente(erp_descontinuado):
    alerta = erp_descontinuado.alertas[-1]
    assert alerta.prioridad == "CRITICA"
    assert alerta.demanda_abierta == 45  # 30 + 10 + 5 (incluye la orden en proceso)
    assert set(alerta.ordenes_afectadas) == {"OF-1001", "OF-1002", "OF-0990"}
    assert alerta.cobertura == pytest.approx(12 / 45, abs=1e-4)


def test_componente_sin_uso_genera_alerta_baja(erp):
    alerta = erp.cambiar_estado("MB-A520M-LITE", PROXIMO_A_DESCONTINUAR, T0, usuario="x")
    assert alerta.prioridad == "BAJA"
    assert alerta.boms_afectadas == []


# --- Agente de recomendación --------------------------------------------------

def test_recomendacion_ordenada_y_filtrada(erp_descontinuado):
    recs, descartados = erp_descontinuado.recomendar_sustitutos(MB)
    assert [r.sku_sustituto for r in recs] == ["MB-B550-PRO", "MB-B550-LEGACY", "MB-X570-ELITE"]
    assert "MB-B650-AURA" in descartados  # socket y memoria distintos
    assert "MB-A520M-LITE" in descartados  # factor de forma y PCIe insuficientes
    assert recs[0].puntuacion > recs[1].puntuacion > recs[2].puntuacion


def test_proximo_a_descontinuar_penalizado(erp_descontinuado):
    recs, _ = erp_descontinuado.recomendar_sustitutos(MB)
    legacy = next(r for r in recs if r.sku_sustituto == "MB-B550-LEGACY")
    assert legacy.detalle["ciclo_vida"] < 1.0


# --- Autorización y aplicación ------------------------------------------------

def test_solo_responsable_tecnico_autoriza(erp_descontinuado):
    recs, _ = erp_descontinuado.recomendar_sustitutos(MB)
    with pytest.raises(ErrorDeProceso):
        erp_descontinuado.autorizar(recs[0], "resp.bom", ROL_RESPONSABLE_BOM, T0)


def test_no_se_autoriza_sustituto_incompatible(erp_descontinuado):
    rec = Recomendacion(MB, "MB-B650-AURA", 0.0, {}, "forzada")
    with pytest.raises(ErrorDeProceso):
        erp_descontinuado.autorizar(rec, "ing", ROL_RESPONSABLE_TECNICO, T0)


def test_no_se_aplica_sin_autorizacion_aprobada(erp_descontinuado):
    recs, _ = erp_descontinuado.recomendar_sustitutos(MB)
    rechazo = erp_descontinuado.autorizar(recs[0], "ing", ROL_RESPONSABLE_TECNICO, T0, aprobar=False)
    with pytest.raises(ErrorDeProceso):
        erp_descontinuado.aplicar_sustitucion(rechazo, "resp.bom", T0)


def test_sustitucion_crea_revision_y_conserva_historial(erp_descontinuado):
    erp = erp_descontinuado
    recs, _ = erp.recomendar_sustitutos(MB)
    aut = erp.autorizar(recs[0], "ing", ROL_RESPONSABLE_TECNICO, T0)
    res = erp.aplicar_sustitucion(aut, "resp.bom", T0)
    assert res["boms_nuevas"] == ["ENS-BASE-AM4-v2", "PC-WS-300-v2"]
    assert erp.boms["ENS-BASE-AM4-v1"].estado == "OBSOLETO"
    # La versión anterior no se editó.
    assert any(l.component_sku == MB for l in erp.boms["ENS-BASE-AM4-v1"].lineas)
    assert any(l.component_sku == "MB-B550-PRO" for l in erp.boms["ENS-BASE-AM4-v2"].lineas)
    assert res["ordenes_conservadas"] == ["OF-0990"]
    assert set(res["ordenes_reasignadas"]) == {"OF-1001", "OF-1002"}
    assert [h for h in erp.historial if h["tipo"] == "SUSTITUCION"]
    assert erp.boms_afectadas(MB) == []


# --- MRP -----------------------------------------------------------------------

def test_mrp_as_is_recomienda_comprar_descontinuado(erp):
    resultado = erp.mrp(DEMANDA_PEDIDO, aplicar_reglas=False)
    assert {"sku": MB, "cantidad": 28, "estado_componente": ACTIVO} in resultado["compras"]


def test_mrp_no_compra_descontinuado_y_usa_stock(erp_descontinuado):
    resultado = erp_descontinuado.mrp(DEMANDA_PEDIDO)
    assert MB not in {c["sku"] for c in resultado["compras"]}
    assert resultado["consumo_stock_descontinuado"] == {MB: 12}
    assert resultado["faltantes_bloqueados"] == {MB: 28}


def test_mrp_sin_uso_de_stock_autorizado(erp):
    erp.cambiar_estado(MB, DESCONTINUADO, T0, usuario="x", autorizar_uso_stock=False)
    resultado = erp.mrp(DEMANDA_PEDIDO)
    assert resultado["consumo_stock_descontinuado"] == {MB: 0}
    assert resultado["faltantes_bloqueados"] == {MB: 40}


# --- Escenario completo y KPIs -------------------------------------------------

def test_escenario_completo_kpis():
    r = ejecutar_escenario()
    assert r["kpis_as_is"]["recomendaciones_invalidas_pct"] == 25.0
    assert r["kpis_as_is"]["boms_afectadas_pct"] == 80.0
    assert r["kpis_to_be"] == {
        "tiempo_deteccion_h": 0.25,
        "tiempo_sustitucion_h": 24.0,
        "boms_afectadas_pct": 0.0,
        "recomendaciones_invalidas_pct": 0.0,
        "ordenes_afectadas_pct": 0.0,
        "tasa_sustitucion_exitosa_pct": 100.0,
    }
    # Tras la sustitución se agota primero el stock del descontinuado.
    assert r["mrp_to_be"]["consumo_stock_descontinuado"] == {MB: 12}
    assert "MB-B550-PRO" not in {c["sku"] for c in r["mrp_to_be"]["compras"]}
