"""Unit tests for /reports -- mocks the Groq call (via monkeypatch) so these don't
need a real GROQ_API_KEY, matching how /chat tests mock generate_answer. DB layer is
the existing FakeConnection from conftest.
"""
from app.rate_limit import MAX_REQUESTS_PER_WINDOW
from app.routers import reports as reports_router

PROFILE_ROW = {
    "player_id": "P00001",
    "player_name": "Test Keeper",
    "team": "France",
    "position": "Goalkeeper",
    "matches_played": 7,
    "minutes_played": 630,
    "goals": 0,
    "assists": 0,
    "shots": 0,
    "shots_on_target": 0,
    "expected_goals_xg": 0.0,
    "expected_assists_xa": 0.0,
    "avg_pass_accuracy": 80.0,
    "tackles": 1,
    "interceptions": 2,
    "saves": 22,
    "clean_sheets": 3,
    "yellow_cards": 1,
    "red_cards": 0,
    "avg_player_rating": 7.1,
}

MATCH_ROWS = [
    {
        "match_date": "2026-06-11",
        "tournament_stage": "Group Stage",
        "opponent_team": "Belgium",
        "match_result": "W",
        "minutes_played": 90,
        "goals": 0,
        "assists": 0,
        "player_rating": 7.8,
    }
]

CACHED_REPORT_ROW = {
    "player_id": "P00001",
    "player_name": "Test Keeper",
    "report_text": "Test Keeper is a reliable shot-stopper ...",
    "generated_at": "2026-07-30T12:00:00+00:00",
}


def test_get_cached_report_404_when_none_exists(make_client):
    client = make_client([[]])
    resp = client.get("/reports/players/P00001")
    assert resp.status_code == 404


def test_get_cached_report_returns_existing(make_client):
    client = make_client([[CACHED_REPORT_ROW]])
    resp = client.get("/reports/players/P00001")
    assert resp.status_code == 200
    assert resp.json()["report_text"] == CACHED_REPORT_ROW["report_text"]


def test_generate_report_404_when_player_not_found(make_client):
    client = make_client([[]])
    resp = client.post("/reports/players/P99999")
    assert resp.status_code == 404


def test_generate_report_success(make_client, monkeypatch):
    captured = {}

    def fake_generate_player_report(summary, recent_matches):
        captured["summary"] = summary
        captured["recent_matches"] = recent_matches
        return "Test Keeper is a reliable shot-stopper with strong distribution."

    monkeypatch.setattr(reports_router, "generate_player_report", fake_generate_player_report)

    inserted_row = {
        "player_id": "P00001",
        "report_text": "Test Keeper is a reliable shot-stopper with strong distribution.",
        "generated_at": "2026-07-30T12:00:00+00:00",
    }
    client = make_client([[PROFILE_ROW], MATCH_ROWS, [inserted_row]])
    resp = client.post("/reports/players/P00001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["player_id"] == "P00001"
    assert body["player_name"] == "Test Keeper"
    assert "shot-stopper" in body["report_text"]
    assert "Test Keeper is a Goalkeeper for France." in captured["summary"]
    assert captured["recent_matches"] == MATCH_ROWS


def test_generate_report_returns_503_when_generation_fails(make_client, monkeypatch):
    def _raise(_summary, _recent_matches):
        raise RuntimeError("GROQ_API_KEY is not set")

    monkeypatch.setattr(reports_router, "generate_player_report", _raise)
    client = make_client([[PROFILE_ROW], MATCH_ROWS])
    resp = client.post("/reports/players/P00001")
    assert resp.status_code == 503


def test_generate_report_rate_limits_after_max_requests(make_client, monkeypatch):
    monkeypatch.setattr(reports_router, "generate_player_report", lambda s, m: "report")
    inserted_row = {
        "player_id": "P00001",
        "report_text": "report",
        "generated_at": "2026-07-30T12:00:00+00:00",
    }
    responses = [[PROFILE_ROW], MATCH_ROWS, [inserted_row]] * MAX_REQUESTS_PER_WINDOW
    client = make_client(responses)

    for _ in range(MAX_REQUESTS_PER_WINDOW):
        resp = client.post("/reports/players/P00001")
        assert resp.status_code == 200

    resp = client.post("/reports/players/P00001")
    assert resp.status_code == 429
