import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from transform import BIO_COLUMNS, STAT_COLUMNS, build_players, build_teams, transform  # noqa: E402

MATCH_COLUMNS = [
    "match_id", "match_date", "stadium", "city", "tournament_stage",
    "opponent_team", "goals_team", "goals_opponent", "match_result",
]
ALL_COLUMNS = list(dict.fromkeys(BIO_COLUMNS + STAT_COLUMNS + MATCH_COLUMNS))


def _row(**overrides) -> dict:
    row = {col: 0 for col in ALL_COLUMNS}
    row.update({
        "player_name": "Test Player",
        "nationality": "Testland",
        "position": "Midfielder",
        "preferred_foot": "Right",
        "club_name": "Test FC",
        "stadium": "Test Stadium",
        "city": "Test City",
        "tournament_stage": "Group Stage",
        "match_date": "2026-07-01",
        "match_result": "W",
        "clean_sheet": 0,
    })
    row.update(overrides)
    return row


@pytest.fixture
def raw_csv(tmp_path) -> str:
    rows = [
        # Match M1: Spain 1-0 Peru
        _row(player_id="P1", team="Spain", opponent_team="Peru", match_id="M1",
             goals_team=1, goals_opponent=0, goals=1, match_result="W"),
        _row(player_id="P2", team="Peru", opponent_team="Spain", match_id="M1",
             goals_team=0, goals_opponent=1, match_result="L"),
        # Match M2: Zambia 2-2 Australia (tests alphabetical canonical ordering)
        _row(player_id="P3", team="Zambia", opponent_team="Australia", match_id="M2",
             goals_team=2, goals_opponent=2, goals=2, match_result="D"),
        _row(player_id="P4", team="Australia", opponent_team="Zambia", match_id="M2",
             goals_team=2, goals_opponent=2, match_result="D"),
    ]
    df = pd.DataFrame(rows)
    path = tmp_path / "raw.csv"
    df.to_csv(path, index=False)
    return str(path)


def test_transform_shapes(raw_csv):
    tables = transform(raw_csv)
    assert len(tables["teams"]) == 4
    assert len(tables["players"]) == 4
    assert len(tables["matches"]) == 2
    assert len(tables["player_match_stats"]) == 4


def test_matches_canonical_ordering_and_scores(raw_csv):
    tables = transform(raw_csv)
    matches = tables["matches"].set_index("match_id")

    m1 = matches.loc["M1"]
    assert m1["team_a"] == "Peru"  # alphabetically before Spain
    assert m1["team_b"] == "Spain"
    assert m1["goals_a"] == 0
    assert m1["goals_b"] == 1

    m2 = matches.loc["M2"]
    assert m2["team_a"] == "Australia"
    assert m2["team_b"] == "Zambia"
    assert m2["goals_a"] == 2
    assert m2["goals_b"] == 2


def test_player_match_stats_goals_preserved(raw_csv):
    tables = transform(raw_csv)
    stats = tables["player_match_stats"].set_index("player_id")
    assert stats.loc["P1", "goals"] == 1
    assert stats.loc["P3", "goals"] == 2


def test_players_deduplicated_by_id():
    df = pd.DataFrame([_row(player_id="P1", team="Spain", match_id="M1"),
                        _row(player_id="P1", team="Spain", match_id="M2")])
    players = build_players(df)
    assert len(players) == 1


def test_teams_union_of_team_and_opponent():
    df = pd.DataFrame([_row(player_id="P1", team="Spain", opponent_team="Peru", match_id="M1")])
    teams = build_teams(df)
    assert set(teams["team_name"]) == {"Spain", "Peru"}
