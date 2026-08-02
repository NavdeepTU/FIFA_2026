"""Unit tests for the pure summary-text builders -- no model loading, no DB, so these
stay fast. Embedding generation itself (fastembed call, DB upsert) is exercised by
actually running `backend/genai/generate_embeddings.py` /
`generate_team_embeddings.py` against a real Postgres, not here -- see
docs/project_status.md.
"""
from genai.embeddings import build_match_summary_text, build_summary_text, build_team_summary_text

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

PERFORMERS = [
    {
        "player_name": "Kylian Mbappe",
        "team": "France",
        "goals": 2,
        "assists": 0,
        "player_rating": 8.9,
        "yellow_cards": 0,
        "red_cards": 0,
    },
    {
        "player_name": "Vinicius Junior",
        "team": "Brazil",
        "goals": 1,
        "assists": 0,
        "player_rating": 7.4,
        "yellow_cards": 1,
        "red_cards": 0,
    },
    {
        "player_name": "N'Golo Kante",
        "team": "France",
        "goals": 0,
        "assists": 1,
        "player_rating": 7.1,
        "yellow_cards": 0,
        "red_cards": 0,
    },
]


def test_build_match_summary_text_includes_scoreline_and_venue():
    summary = build_match_summary_text(MATCH_ROW, PERFORMERS)
    assert "Group Stage match at MetLife Stadium, East Rutherford on 2026-06-11" in summary
    assert "France 2-1 Brazil" in summary


def test_build_match_summary_text_lists_scorers():
    summary = build_match_summary_text(MATCH_ROW, PERFORMERS)
    assert "Kylian Mbappe (France, 2 goal(s))" in summary
    assert "Vinicius Junior (Brazil, 1 goal(s))" in summary
    assert "N'Golo Kante" not in summary.split("Goal scorers:")[1].split(".")[0]


def test_build_match_summary_text_names_top_rated_performer():
    summary = build_match_summary_text(MATCH_ROW, PERFORMERS)
    assert "Top-rated performer: Kylian Mbappe (France), rating 8.90." in summary


def test_build_match_summary_text_lists_cards():
    summary = build_match_summary_text(MATCH_ROW, PERFORMERS)
    assert "Vinicius Junior (1Y/0R)" in summary


def test_build_match_summary_text_omits_cards_section_when_none():
    no_cards = [{**p, "yellow_cards": 0, "red_cards": 0} for p in PERFORMERS]
    summary = build_match_summary_text(MATCH_ROW, no_cards)
    assert "Cards:" not in summary


def test_build_match_summary_text_handles_no_performers():
    summary = build_match_summary_text(MATCH_ROW, [])
    assert "France 2-1 Brazil" in summary
    assert "Top-rated performer" not in summary
    assert "Goal scorers" not in summary
