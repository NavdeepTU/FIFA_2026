"""Feature sets for the three Phase 2 models, built from the ETL'd tables.

Deliberately excludes a cluster of columns that turned out to be leaky: correlation
against `player_rating` showed `tournament_rating` (0.997), `performance_score` (0.997),
`distance_covered_km` (0.837), and `sprint_distance_km` are all effectively the same
synthetic formula wearing different names, not independent signal. Training on them
would give a trivially "accurate" model that predicts nothing real. The feature sets
below use only genuine box-score actions (goals, passes, tackles, etc.) and minutes --
the inputs a rating model could plausibly generalize from.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "etl"))
from transform import load_raw  # noqa: E402

RATING_FEATURE_COLUMNS = [
    "minutes_played", "goals", "assists", "shots", "shots_on_target",
    "expected_goals_xg", "expected_assists_xa", "key_passes", "successful_passes",
    "total_passes", "pass_accuracy", "dribbles_attempted", "successful_dribbles",
    "crosses", "successful_crosses", "tackles", "interceptions", "clearances",
    "blocks", "aerial_duels_won", "aerial_duels_lost", "recoveries",
    "defensive_actions", "fouls_committed", "fouls_suffered", "yellow_cards",
    "red_cards", "offsides", "saves", "save_percentage", "clean_sheet",
    "goals_conceded", "penalty_saves",
]
RATING_CATEGORICAL_COLUMNS = ["position"]
RATING_TARGET = "player_rating"

TEAM_MATCH_STAT_COLUMNS = [
    "goals", "shots", "shots_on_target", "expected_goals_xg", "expected_assists_xa",
    "successful_passes", "total_passes", "dribbles_attempted", "successful_dribbles",
    "crosses", "successful_crosses", "tackles", "interceptions", "clearances",
    "aerial_duels_won", "fouls_committed", "yellow_cards", "red_cards",
]
OUTCOME_TARGET = "result"

ARCHETYPE_PER90_COLUMNS = [
    "goals", "assists", "shots", "key_passes", "successful_passes",
    "dribbles_attempted", "tackles", "interceptions", "clearances",
    "aerial_duels_won", "saves", "fouls_committed",
]


def _raw(csv_path: str) -> pd.DataFrame:
    return load_raw(csv_path)


def build_rating_dataset(csv_path: str) -> tuple[pd.DataFrame, pd.Series]:
    """One row per player-match. Only rows with minutes_played > 0 (an unused
    substitute has no meaningful stat line to learn from)."""
    df = _raw(csv_path)
    df = df[df["minutes_played"] > 0].copy()
    x = df[RATING_FEATURE_COLUMNS + RATING_CATEGORICAL_COLUMNS].copy()
    x = pd.get_dummies(x, columns=RATING_CATEGORICAL_COLUMNS, prefix="pos")
    y = df[RATING_TARGET]
    return x, y


def build_team_match_dataset(csv_path: str) -> tuple[pd.DataFrame, pd.Series]:
    """Aggregates player rows up to (match_id, team) and predicts that team's
    result (W/D/L) in the match from their aggregated box-score stats."""
    df = _raw(csv_path)
    agg = (
        df.groupby(["match_id", "team"], as_index=False)[TEAM_MATCH_STAT_COLUMNS]
        .sum()
    )
    result = df.groupby(["match_id", "team"], as_index=False)["match_result"].first()
    merged = agg.merge(result, on=["match_id", "team"])
    x = merged[TEAM_MATCH_STAT_COLUMNS]
    y = merged["match_result"].rename(OUTCOME_TARGET)
    return x, y


def build_archetype_dataset(csv_path: str) -> pd.DataFrame:
    """Per-player per-90-minutes aggregates, standardized inputs for clustering.
    Returns player_id/player_name/team/position alongside the per-90 feature columns
    (not yet standardized -- train_clustering.py owns the scaler)."""
    df = _raw(csv_path)
    played = df[df["minutes_played"] > 0].copy()
    minutes = played.groupby("player_id")["minutes_played"].sum()

    totals = played.groupby("player_id")[ARCHETYPE_PER90_COLUMNS].sum()
    per90 = totals.div(minutes / 90.0, axis=0)
    per90.columns = [f"{c}_per90" for c in per90.columns]

    meta = played.groupby("player_id").agg(
        player_name=("player_name", "first"),
        team=("team", "first"),
        position=("position", "first"),
    )
    return meta.join(per90).reset_index()
