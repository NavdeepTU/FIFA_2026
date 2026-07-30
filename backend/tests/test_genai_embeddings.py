"""Unit tests for the pure summary-text builders -- no model loading, no DB, so these
stay fast. Embedding generation itself (fastembed call, DB upsert) is exercised by
actually running `backend/genai/generate_embeddings.py` /
`generate_team_embeddings.py` against a real Postgres, not here -- see
docs/project_status.md.
"""
from genai.embeddings import build_summary_text, build_team_summary_text

OUTFIELD_ROW = {
    "player_name": "Kylian Mbappe",
    "team": "France",
    "position": "Forward",
    "matches_played": 7,
    "minutes_played": 630,
    "goals": 8,
    "assists": 3,
    "shots": 25,
    "shots_on_target": 12,
    "expected_goals_xg": 6.4,
    "expected_assists_xa": 2.1,
    "avg_pass_accuracy": 82.5,
    "tackles": 2,
    "interceptions": 1,
    "saves": 0,
    "clean_sheets": 0,
    "yellow_cards": 1,
    "red_cards": 0,
    "avg_player_rating": 7.8,
}

GOALKEEPER_ROW = {
    **OUTFIELD_ROW,
    "player_name": "Mike Maignan",
    "position": "Goalkeeper",
    "goals": 0,
    "assists": 0,
    "saves": 22,
    "clean_sheets": 3,
}


def test_build_summary_text_includes_key_stats():
    summary = build_summary_text(OUTFIELD_ROW)
    assert "Kylian Mbappe" in summary
    assert "Forward for France" in summary
    assert "8 goals" in summary
    assert "3 assists" in summary
    assert "xG 6.4" in summary
    assert "rating 7.80" in summary


def test_build_summary_text_omits_saves_for_outfield_player_with_none():
    summary = build_summary_text(OUTFIELD_ROW)
    assert "saves" not in summary


def test_build_summary_text_includes_saves_for_goalkeeper():
    summary = build_summary_text(GOALKEEPER_ROW)
    assert "22 saves" in summary
    assert "3 clean sheets" in summary


def test_build_summary_text_handles_missing_values_as_zero():
    sparse_row = {**OUTFIELD_ROW, "goals": None, "expected_goals_xg": None, "avg_player_rating": None}
    summary = build_summary_text(sparse_row)
    assert "0 goals" in summary
    assert "xG 0.0" in summary
    assert "rating 0.00" in summary


TEAM_ROW = {
    "team": "Brazil",
    "matches_played": 45,
    "wins": 22,
    "draws": 11,
    "losses": 12,
    "goals_for": 77,
    "goals_against": 55,
    "points": 77,
    "tackles": 310,
    "interceptions": 210,
    "clearances": 180,
    "saves": 90,
    "clean_sheets": 12,
    "yellow_cards": 40,
    "red_cards": 3,
    "avg_pass_accuracy": 81.2,
    "avg_player_rating": 6.9,
}


def test_build_team_summary_text_includes_record_and_defensive_stats():
    summary = build_team_summary_text(TEAM_ROW)
    assert "Brazil" in summary
    assert "22 wins" in summary
    assert "11 draws" in summary
    assert "12 losses" in summary
    assert "77 points" in summary
    assert "77 goals" in summary
    assert "conceded 55" in summary
    assert "310 tackles" in summary
    assert "12 clean sheets" in summary


def test_build_team_summary_text_handles_missing_values_as_zero():
    sparse_row = {**TEAM_ROW, "wins": None, "avg_pass_accuracy": None, "avg_player_rating": None}
    summary = build_team_summary_text(sparse_row)
    assert "0 wins" in summary
    assert "0%" in summary
    assert "rating of 0.00" in summary
