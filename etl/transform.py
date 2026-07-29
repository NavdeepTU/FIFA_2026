"""Pure pandas transforms: raw FIFA CSV -> normalized tables.

No DB or network access here on purpose, so this can be unit-tested and iterated on
without needing Postgres available.
"""
from __future__ import annotations

import pandas as pd

BIO_COLUMNS = [
    "player_id", "player_name", "age", "nationality", "team", "jersey_number",
    "position", "height_cm", "weight_kg", "preferred_foot", "club_name", "market_value_eur",
]

STAT_COLUMNS = [
    "minutes_played", "goals", "assists", "shots", "shots_on_target",
    "expected_goals_xg", "expected_assists_xa", "key_passes", "successful_passes",
    "total_passes", "pass_accuracy", "dribbles_attempted", "successful_dribbles",
    "crosses", "successful_crosses", "tackles", "interceptions", "clearances", "blocks",
    "aerial_duels_won", "aerial_duels_lost", "recoveries", "defensive_actions",
    "fouls_committed", "fouls_suffered", "yellow_cards", "red_cards", "offsides",
    "saves", "save_percentage", "punches", "clean_sheet", "goals_conceded",
    "penalty_saves", "distance_covered_km", "sprint_distance_km", "top_speed_kmh",
    "accelerations", "decelerations", "stamina_score", "player_rating",
    "performance_score", "offensive_contribution", "defensive_contribution",
    "possession_impact", "pressure_resistance", "creativity_score",
    "consistency_score", "clutch_performance_score",
]


def load_raw(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, parse_dates=["match_date"])
    df["clean_sheet"] = df["clean_sheet"].astype(bool)
    return df


def build_teams(df: pd.DataFrame) -> pd.DataFrame:
    names = pd.unique(pd.concat([df["team"], df["opponent_team"]]))
    return pd.DataFrame({"team_name": sorted(names)})


def build_players(df: pd.DataFrame) -> pd.DataFrame:
    # bio fields are constant per player_id in this dataset; .first() collapses duplicates safely
    return (
        df[BIO_COLUMNS]
        .groupby("player_id", as_index=False)
        .first()
    )


def build_matches(df: pd.DataFrame) -> pd.DataFrame:
    sides = df[
        ["match_id", "match_date", "stadium", "city", "tournament_stage",
         "team", "opponent_team", "goals_team", "goals_opponent"]
    ].drop_duplicates(subset=["match_id", "team"])

    rows = []
    for match_id, g in sides.groupby("match_id"):
        g = g.reset_index(drop=True)
        base = g.iloc[0]
        if len(g) >= 2:
            other = g.iloc[1]
            team_a, goals_a = base["team"], base["goals_team"]
            team_b, goals_b = other["team"], other["goals_team"]
        else:
            # only one side present in the dataset for this match_id
            team_a, goals_a = base["team"], base["goals_team"]
            team_b, goals_b = base["opponent_team"], base["goals_opponent"]

        if team_b < team_a:
            team_a, team_b = team_b, team_a
            goals_a, goals_b = goals_b, goals_a

        rows.append({
            "match_id": match_id,
            "match_date": base["match_date"],
            "stadium": base["stadium"],
            "city": base["city"],
            "tournament_stage": base["tournament_stage"],
            "team_a": team_a,
            "team_b": team_b,
            "goals_a": goals_a,
            "goals_b": goals_b,
        })
    return pd.DataFrame(rows)


def build_player_match_stats(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["player_id", "match_id", "team", "opponent_team", "match_result"] + STAT_COLUMNS
    return df[cols].drop_duplicates(subset=["player_id", "match_id"])


def transform(csv_path: str) -> dict[str, pd.DataFrame]:
    df = load_raw(csv_path)
    return {
        "teams": build_teams(df),
        "players": build_players(df),
        "matches": build_matches(df),
        "player_match_stats": build_player_match_stats(df),
    }
