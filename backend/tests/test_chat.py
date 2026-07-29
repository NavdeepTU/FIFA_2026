"""Unit tests for /chat -- mocks the embedding call (via monkeypatch) so these don't
load the real fastembed model, matching how /predict tests mock model artifacts
(see test_predict.py). DB layer is the existing FakeConnection from conftest.
"""
from app.routers import chat as chat_router


def test_status():
    from app.main import app
    from fastapi.testclient import TestClient

    resp = TestClient(app).get("/chat/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["retrieval_available"] is True
    assert body["generation_available"] is False


def test_retrieve_embeds_query_and_returns_nearest_players(make_client, monkeypatch):
    monkeypatch.setattr(chat_router, "embed_texts", lambda texts: [[0.1] * 384])
    rows = [
        {
            "player_id": "P00001",
            "player_name": "Test Keeper",
            "team": "France",
            "position": "Goalkeeper",
            "summary_text": "Test Keeper is a Goalkeeper for France.",
            "distance": 0.42,
        }
    ]
    client = make_client([rows])
    resp = client.post("/chat/retrieve", json={"query": "best goalkeeper", "top_k": 5})
    assert resp.status_code == 200
    assert resp.json() == rows


def test_retrieve_rejects_empty_query(client):
    resp = client.post("/chat/retrieve", json={"query": ""})
    assert resp.status_code == 422


def test_retrieve_rejects_top_k_out_of_range(client):
    resp = client.post("/chat/retrieve", json={"query": "goalkeepers", "top_k": 100})
    assert resp.status_code == 422


def test_retrieve_returns_503_when_embedding_fails(make_client, monkeypatch):
    def _raise(_texts):
        raise RuntimeError("model download failed")

    monkeypatch.setattr(chat_router, "embed_texts", _raise)
    client = make_client([])
    resp = client.post("/chat/retrieve", json={"query": "best goalkeeper"})
    assert resp.status_code == 503


def test_ask_retrieves_then_generates_grounded_answer(make_client, monkeypatch):
    monkeypatch.setattr(chat_router, "embed_texts", lambda texts: [[0.1] * 384])
    captured = {}

    def fake_generate_answer(question, context):
        captured["question"] = question
        captured["context"] = context
        return "Test Keeper made the most saves."

    monkeypatch.setattr(chat_router, "generate_answer", fake_generate_answer)
    rows = [
        {
            "player_id": "P00001",
            "player_name": "Test Keeper",
            "team": "France",
            "position": "Goalkeeper",
            "summary_text": "Test Keeper is a Goalkeeper for France.",
            "distance": 0.42,
        }
    ]
    client = make_client([rows])
    resp = client.post("/chat/ask", json={"query": "who made the most saves?", "top_k": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "Test Keeper made the most saves."
    assert body["sources"] == rows
    assert captured["question"] == "who made the most saves?"
    assert captured["context"] == ["Test Keeper is a Goalkeeper for France."]


def test_ask_returns_503_when_generation_fails(make_client, monkeypatch):
    monkeypatch.setattr(chat_router, "embed_texts", lambda texts: [[0.1] * 384])

    def _raise(_question, _context):
        raise RuntimeError("GROQ_API_KEY is not set")

    monkeypatch.setattr(chat_router, "generate_answer", _raise)
    rows = [
        {
            "player_id": "P00001",
            "player_name": "Test Keeper",
            "team": "France",
            "position": "Goalkeeper",
            "summary_text": "Test Keeper is a Goalkeeper for France.",
            "distance": 0.42,
        }
    ]
    client = make_client([rows])
    resp = client.post("/chat/ask", json={"query": "who made the most saves?"})
    assert resp.status_code == 503
