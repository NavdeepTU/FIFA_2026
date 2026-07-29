import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.ml_models import (
    get_outcome_features,
    get_outcome_label_encoder,
    get_outcome_model,
    get_player_archetypes,
    get_rating_features,
    get_rating_model,
    models_available,
)

router = APIRouter(prefix="/predict", tags=["predict"])

# Mirrors backend/ml/features.py's RATING_FEATURE_COLUMNS / TEAM_MATCH_STAT_COLUMNS.
# Deliberately duplicated rather than imported: this is the public API contract, and
# it shouldn't silently drift just because an internal training script's feature list
# changes -- a real feature-set change should touch both deliberately.


class RatingPredictionInput(BaseModel):
    minutes_played: float = 90
    goals: float = 0
    assists: float = 0
    shots: float = 0
    shots_on_target: float = 0
    expected_goals_xg: float = 0
    expected_assists_xa: float = 0
    key_passes: float = 0
    successful_passes: float = 0
    total_passes: float = 0
    pass_accuracy: float = 0.8
    dribbles_attempted: float = 0
    successful_dribbles: float = 0
    crosses: float = 0
    successful_crosses: float = 0
    tackles: float = 0
    interceptions: float = 0
    clearances: float = 0
    blocks: float = 0
    aerial_duels_won: float = 0
    aerial_duels_lost: float = 0
    recoveries: float = 0
    defensive_actions: float = 0
    fouls_committed: float = 0
    fouls_suffered: float = 0
    yellow_cards: float = 0
    red_cards: float = 0
    offsides: float = 0
    saves: float = 0
    save_percentage: float = 0
    clean_sheet: bool = False
    goals_conceded: float = 0
    penalty_saves: float = 0
    position: str = Field(default="Midfielder", description="Forward, Midfielder, Defender, or Goalkeeper")


class RatingPredictionOutput(BaseModel):
    predicted_rating: float


class TeamMatchStatsInput(BaseModel):
    goals: float = 0
    shots: float = 0
    shots_on_target: float = 0
    expected_goals_xg: float = 0
    expected_assists_xa: float = 0
    successful_passes: float = 0
    total_passes: float = 0
    dribbles_attempted: float = 0
    successful_dribbles: float = 0
    crosses: float = 0
    successful_crosses: float = 0
    tackles: float = 0
    interceptions: float = 0
    clearances: float = 0
    aerial_duels_won: float = 0
    fouls_committed: float = 0
    yellow_cards: float = 0
    red_cards: float = 0


class OutcomePredictionOutput(BaseModel):
    predicted_result: str
    probabilities: dict[str, float]


@router.get("/status")
def status():
    return {"available": models_available()}


@router.post("/rating", response_model=RatingPredictionOutput)
def predict_rating(payload: RatingPredictionInput):
    try:
        feature_columns = get_rating_features()
        model = get_rating_model()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    raw = payload.model_dump(exclude={"position"})
    raw["clean_sheet"] = int(raw["clean_sheet"])
    row = {col: raw.get(col, 0) for col in feature_columns if not col.startswith("pos_")}
    for col in feature_columns:
        if col.startswith("pos_"):
            row[col] = 1 if col == f"pos_{payload.position}" else 0

    x = pd.DataFrame([row])[list(feature_columns)]
    prediction = model.predict(x)[0]
    return RatingPredictionOutput(predicted_rating=round(float(prediction), 2))


@router.post("/outcome", response_model=OutcomePredictionOutput)
def predict_outcome(payload: TeamMatchStatsInput):
    try:
        feature_columns = get_outcome_features()
        model = get_outcome_model()
        encoder = get_outcome_label_encoder()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    row = payload.model_dump()
    x = pd.DataFrame([row])[list(feature_columns)]
    probabilities = model.predict_proba(x)[0]
    predicted_idx = probabilities.argmax()

    class_probabilities = zip(encoder.classes_, probabilities, strict=True)
    return OutcomePredictionOutput(
        predicted_result=str(encoder.classes_[predicted_idx]),
        probabilities={cls: round(float(p), 3) for cls, p in class_probabilities},
    )


@router.get("/archetypes/{player_id}")
def player_archetype(player_id: str):
    try:
        archetypes = get_player_archetypes()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    match = archetypes[archetypes["player_id"] == player_id]
    if match.empty:
        raise HTTPException(status_code=404, detail="player not found in archetype data")
    return match.iloc[0].to_dict()


@router.get("/archetypes")
def archetype_distribution():
    try:
        archetypes = get_player_archetypes()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    counts = archetypes["archetype"].value_counts()
    return [{"archetype": name, "count": int(count)} for name, count in counts.items()]
