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

TEAM_PROFILE_ROW = {
    "team": "France",
    "matches_played": 34,
    "wins": 12,
    "draws": 11,
    "losses": 11,
    "goals_for": 53,
    "goals_against": 50,
    "points": 47,
    "tackles": 733,
    "interceptions": 543,
    "clearances": 748,
    "saves": 108,
    "clean_sheets": 5,
    "yellow_cards": 88,
    "red_cards": 4,
    "avg_pass_accuracy": 1.0,
    "avg_player_rating": 3.58,
}

TEAM_MATCH_ROWS = [
    {
        "match_date": "2026-06-11",
        "tournament_stage": "Group Stage",
        "opponent": "Belgium",
        "goals_for": 2,
        "goals_against": 1,
    }
]

CACHED_TEAM_REPORT_ROW = {
    "team_name": "France",
    "report_text": "France field a defensively organized side ...",
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


def test_get_cached_team_report_404_when_none_exists(make_client):
    client = make_client([[]])
    resp = client.get("/reports/teams/France")
    assert resp.status_code == 404


def test_get_cached_team_report_returns_existing(make_client):
    client = make_client([[CACHED_TEAM_REPORT_ROW]])
    resp = client.get("/reports/teams/France")
    assert resp.status_code == 200
    assert resp.json()["report_text"] == CACHED_TEAM_REPORT_ROW["report_text"]


def test_generate_team_report_404_when_team_not_found(make_client):
    client = make_client([[]])
    resp = client.post("/reports/teams/Nowhereland")
    assert resp.status_code == 404


def test_generate_team_report_success(make_client, monkeypatch):
    captured = {}

    def fake_generate_team_report(summary, recent_matches):
        captured["summary"] = summary
        captured["recent_matches"] = recent_matches
        return "France field a defensively organized side with strong distribution."

    monkeypatch.setattr(reports_router, "generate_team_report", fake_generate_team_report)

    inserted_row = {
        "team_name": "France",
        "report_text": "France field a defensively organized side with strong distribution.",
        "generated_at": "2026-07-30T12:00:00+00:00",
    }
    client = make_client([[TEAM_PROFILE_ROW], TEAM_MATCH_ROWS, [inserted_row]])
    resp = client.post("/reports/teams/France")
    assert resp.status_code == 200
    body = resp.json()
    assert body["team_name"] == "France"
    assert "defensively organized" in body["report_text"]
    assert "France played 34 matches" in captured["summary"]
    assert captured["recent_matches"] == TEAM_MATCH_ROWS


def test_generate_team_report_returns_503_when_generation_fails(make_client, monkeypatch):
    def _raise(_summary, _recent_matches):
        raise RuntimeError("GROQ_API_KEY is not set")

    monkeypatch.setattr(reports_router, "generate_team_report", _raise)
    client = make_client([[TEAM_PROFILE_ROW], TEAM_MATCH_ROWS])
    resp = client.post("/reports/teams/France")
    assert resp.status_code == 503


MATCH_ROW = {
    "match_id": "M00001",
    "match_date": "2026-06-11",
    "stadium": "MetLife Stadium",
    "city": "East Rutherford",
    "tournament_stage": "Group Stage",
    "team_a": "France",
    "team_b": "Brazil",
    "goals_a": 2,
    "goals_b": 1,
}

MATCH_PERFORMERS = [
    {
        "player_name": "Kylian Mbappe",
        "team": "France",
        "goals": 2,
        "assists": 0,
        "player_rating": 8.9,
        "yellow_cards": 0,
        "red_cards": 0,
    }
]

CACHED_MATCH_REPORT_ROW = {
    "match_id": "M00001",
    "team_a": "France",
    "team_b": "Brazil",
    "report_text": "France edged past Brazil in a tense group-stage clash ...",
    "generated_at": "2026-07-30T12:00:00+00:00",
}


def test_get_cached_match_report_404_when_none_exists(make_client):
    client = make_client([[]])
    resp = client.get("/reports/matches/M00001")
    assert resp.status_code == 404


def test_get_cached_match_report_returns_existing(make_client):
    client = make_client([[CACHED_MATCH_REPORT_ROW]])
    resp = client.get("/reports/matches/M00001")
    assert resp.status_code == 200
    assert resp.json()["report_text"] == CACHED_MATCH_REPORT_ROW["report_text"]


def test_generate_match_report_404_when_match_not_found(make_client):
    client = make_client([[]])
    resp = client.post("/reports/matches/M99999")
    assert resp.status_code == 404


def test_generate_match_report_success(make_client, monkeypatch):
    captured = {}

    def fake_generate_match_report(summary):
        captured["summary"] = summary
        return "France edged past Brazil in a tense group-stage clash."

    monkeypatch.setattr(reports_router, "generate_match_report", fake_generate_match_report)

    inserted_row = {
        "match_id": "M00001",
        "report_text": "France edged past Brazil in a tense group-stage clash.",
        "generated_at": "2026-07-30T12:00:00+00:00",
    }
    client = make_client([[MATCH_ROW], MATCH_PERFORMERS, [inserted_row]])
    resp = client.post("/reports/matches/M00001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["match_id"] == "M00001"
    assert body["team_a"] == "France"
    assert body["team_b"] == "Brazil"
    assert "tense group-stage clash" in body["report_text"]
    assert "France 2-1 Brazil" in captured["summary"]


def test_generate_match_report_returns_503_when_generation_fails(make_client, monkeypatch):
    def _raise(_summary):
        raise RuntimeError("GROQ_API_KEY is not set")

    monkeypatch.setattr(reports_router, "generate_match_report", _raise)
    client = make_client([[MATCH_ROW], MATCH_PERFORMERS])
    resp = client.post("/reports/matches/M00001")
    assert resp.status_code == 503


def test_generate_match_report_rate_limits_after_max_requests(make_client, monkeypatch):
    monkeypatch.setattr(reports_router, "generate_match_report", lambda s: "report")
    inserted_row = {
        "match_id": "M00001",
        "report_text": "report",
        "generated_at": "2026-07-30T12:00:00+00:00",
    }
    responses = [[MATCH_ROW], MATCH_PERFORMERS, [inserted_row]] * MAX_REQUESTS_PER_WINDOW
    client = make_client(responses)

    for _ in range(MAX_REQUESTS_PER_WINDOW):
        resp = client.post("/reports/matches/M00001")
        assert resp.status_code == 200

    resp = client.post("/reports/matches/M00001")
    assert resp.status_code == 429
