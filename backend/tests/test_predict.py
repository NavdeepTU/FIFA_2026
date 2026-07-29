"""Unit tests for /predict -- mocks the model artifacts (via monkeypatch) rather than
loading the real ones, so these stay fast and don't churn every time a model is
retrained. Real model *quality* (accuracy/R2) is tracked in backend/ml/artifacts/*_metrics.json,
not asserted here.
"""
import numpy as np
import pandas as pd
from app.routers import predict as predict_router


class FakeRegressor:
    def predict(self, x):
        return np.array([7.5] * len(x))


class FakeClassifier:
    def predict_proba(self, x):
        return np.array([[0.2, 0.3, 0.5]] * len(x))


class FakeEncoder:
    classes_ = np.array(["D", "L", "W"])


def test_predict_rating(client, monkeypatch):
    monkeypatch.setattr(predict_router, "get_rating_model", lambda: FakeRegressor())
    monkeypatch.setattr(
        predict_router, "get_rating_features", lambda: ("goals", "pos_Forward", "pos_Midfielder")
    )
    resp = client.post("/predict/rating", json={"goals": 2, "position": "Forward"})
    assert resp.status_code == 200
    assert resp.json() == {"predicted_rating": 7.5}


def test_predict_outcome(client, monkeypatch):
    monkeypatch.setattr(predict_router, "get_outcome_model", lambda: FakeClassifier())
    monkeypatch.setattr(predict_router, "get_outcome_label_encoder", lambda: FakeEncoder())
    monkeypatch.setattr(predict_router, "get_outcome_features", lambda: ("goals", "shots"))
    resp = client.post("/predict/outcome", json={"goals": 3, "shots": 10})
    assert resp.status_code == 200
    body = resp.json()
    assert body["predicted_result"] == "W"
    assert body["probabilities"]["W"] == 0.5


def test_predict_rating_missing_artifacts_returns_503(client, monkeypatch):
    def _raise():
        raise FileNotFoundError("no artifact")

    monkeypatch.setattr(predict_router, "get_rating_features", _raise)
    resp = client.post("/predict/rating", json={"goals": 1})
    assert resp.status_code == 503


def test_archetype_lookup(client, monkeypatch):
    df = pd.DataFrame([{"player_id": "P1", "player_name": "Test", "archetype": "Forward: Shots + Goals"}])
    monkeypatch.setattr(predict_router, "get_player_archetypes", lambda: df)
    resp = client.get("/predict/archetypes/P1")
    assert resp.status_code == 200
    assert resp.json()["archetype"] == "Forward: Shots + Goals"


def test_archetype_lookup_not_found(client, monkeypatch):
    df = pd.DataFrame([{"player_id": "P1", "archetype": "x"}])
    monkeypatch.setattr(predict_router, "get_player_archetypes", lambda: df)
    resp = client.get("/predict/archetypes/PDOESNOTEXIST")
    assert resp.status_code == 404
