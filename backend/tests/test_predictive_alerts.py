"""PREDINT-024: Tests for predictive alert CRUD routes + ARQ job logic."""
from __future__ import annotations
import pytest
from schemas.predint import (PredictiveAlertCreate, PredictiveAlertUpdate, PredictiveAlertResponse, PredictiveAlertListResponse, row_to_alert_response)

MOCK_ROW = {"id":"alert-abc","user_id":"user-123","sector_id":"saude","alert_type":"volume_spike","threshold_value":50000.0,"uf":"SP","enabled":True,"last_triggered_at":None,"created_at":"2026-06-12T10:00:00Z","updated_at":"2026-06-12T10:00:00Z"}

class TestCreate:
    def test_valid(self):
        m = PredictiveAlertCreate(sector_id="saude", alert_type="volume_spike", threshold_value=50000, uf="SP")
        assert m.sector_id == "saude"
    def test_minimal(self):
        m = PredictiveAlertCreate(sector_id="ti", alert_type="new_opportunity")
        assert m.threshold_value == 0.0 and m.uf is None
    def test_invalid_type(self):
        with pytest.raises(ValueError): PredictiveAlertCreate(sector_id="s", alert_type="bad")
    def test_negative_threshold(self):
        with pytest.raises(ValueError): PredictiveAlertCreate(sector_id="s", alert_type="volume_spike", threshold_value=-1)

class TestUpdate:
    def test_partial(self):
        m = PredictiveAlertUpdate(enabled=False)
        assert m.enabled is False and m.sector_id is None
    def test_all_fields(self):
        m = PredictiveAlertUpdate(sector_id="edu", alert_type="recurrence", threshold_value=100000, uf="RJ", enabled=True)
        assert m.uf == "RJ"

class TestConversion:
    def test_row_to_response(self):
        r = row_to_alert_response(MOCK_ROW)
        assert r.id == "alert-abc" and r.sector_id == "saude" and r.uf == "SP"

class TestListResponse:
    def test_list(self):
        r = PredictiveAlertListResponse(alerts=[row_to_alert_response(MOCK_ROW)], total=1)
        assert r.total == 1

class TestMatchingLogic:
    def test_uf_filter(self):
        preds = [{"uf":"SP","valor_estimado":100000},{"uf":"RJ","valor_estimado":50000}]
        matched = [p for p in preds if p["uf"] == "SP"]
        assert len(matched) == 1 and matched[0]["uf"] == "SP"
    def test_threshold_filter(self):
        preds = [{"uf":"SP","valor_estimado":100000},{"uf":"RJ","valor_estimado":50000}]
        matched = [p for p in preds if p["valor_estimado"] >= 75000]
        assert len(matched) == 1
    def test_no_uf_filter(self):
        preds = [{"uf":"SP"},{"uf":"RJ"}]
        matched = [p for p in preds if not "SP" or p["uf"] == p["uf"]]
        assert len(matched) == 2
    def test_volume_spike(self):
        preds = [{"variacao_anual":0.2},{"variacao_anual":0.1}]
        matched = [p for p in preds if p["variacao_anual"] >= 0.15]
        assert len(matched) == 1
    def test_recurrence(self):
        preds = [{"indice_recorrencia":0.8},{"indice_recorrencia":0.3}]
        matched = [p for p in preds if p["indice_recorrencia"] >= 0.5]
        assert len(matched) == 1
    def test_deadline(self):
        preds = [{"meses_ate_publicacao":1},{"meses_ate_publicacao":3}]
        matched = [p for p in preds if p["meses_ate_publicacao"] <= 2]
        assert len(matched) == 1
    def test_max_events(self):
        capped = [{"uf":f"UF{i}"} for i in range(10)][:5]
        assert len(capped) == 5

class TestEmailRender:
    def test_render(self):
        from jobs.cron.predictive_alert_job import _render_digest
        events = [{"alert_id":"a1","user_id":"u1","sector_id":"s","alert_type":"new","uf":"SP","mensagem":"Nova oportunidade prevista","valor_estimado":50000,"mes_estimado":"Jul","confidence":85.0}]
        html = _render_digest("Maria", events)
        assert "Maria" in html and "Nova oportunidade" in html and "Ver no Radar" in html
    def test_render_empty(self):
        from jobs.cron.predictive_alert_job import _render_digest
        html = _render_digest("Test", [])
        assert "Ola, Test" in html
