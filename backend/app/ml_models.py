"""Lazy-loaded model artifacts for the /predict endpoints.

`lru_cache` gives us load-once-per-process singletons without a startup hook that
would fail app boot if artifacts haven't been trained yet -- the first request after
a fresh clone pays the load cost and a clear FileNotFoundError instead of the whole
API refusing to start. Retrain via `backend/ml/train_*.py`; this module only reads.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd

ARTIFACTS_DIR = Path(__file__).parent.parent / "ml" / "artifacts"


def _load_json(name: str):
    path = ARTIFACTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found -- run the corresponding backend/ml/train_*.py script first"
        )
    return json.loads(path.read_text())


def _load_joblib(name: str):
    path = ARTIFACTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found -- run the corresponding backend/ml/train_*.py script first"
        )
    return joblib.load(path)


@lru_cache
def get_rating_model():
    return _load_joblib("rating_model.joblib")


@lru_cache
def get_rating_features() -> tuple[str, ...]:
    return tuple(_load_json("rating_features.json"))


@lru_cache
def get_outcome_model():
    return _load_joblib("outcome_model.joblib")


@lru_cache
def get_outcome_label_encoder():
    return _load_joblib("outcome_label_encoder.joblib")


@lru_cache
def get_outcome_features() -> tuple[str, ...]:
    return tuple(_load_json("outcome_features.json"))


@lru_cache
def get_player_archetypes() -> pd.DataFrame:
    path = ARTIFACTS_DIR / "player_archetypes.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found -- run train_clustering.py first")
    return pd.read_csv(path, dtype={"player_id": str})


def models_available() -> dict[str, bool]:
    return {
        "rating_model": (ARTIFACTS_DIR / "rating_model.joblib").exists(),
        "outcome_model": (ARTIFACTS_DIR / "outcome_model.joblib").exists(),
        "archetypes": (ARTIFACTS_DIR / "player_archetypes.csv").exists(),
    }
