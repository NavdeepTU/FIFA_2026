"""Trains the player-rating regressor. Run: python backend/ml/train_rating_model.py

Rerun any time the ETL/dataset changes -- artifacts are versioned by overwrite, not by
filename, since this is a single-environment portfolio project rather than a model
registry with multiple concurrent versions in flight.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
from features import build_rating_dataset
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor

DATA_CSV = Path(__file__).parent.parent.parent / "data" / "raw" / "fifa_world_cup_2026_player_performance.csv"
ARTIFACTS_DIR = Path(__file__).parent / "artifacts"


def main() -> None:
    print(f"Loading rating dataset from {DATA_CSV} ...")
    x, y = build_rating_dataset(str(DATA_CSV))
    print(f"  {len(x)} rows, {x.shape[1]} features")

    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.2, random_state=42)

    model = XGBRegressor(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
    )
    model.fit(x_train, y_train)

    preds = model.predict(x_test)
    metrics = {
        "mae": float(mean_absolute_error(y_test, preds)),
        "rmse": float(mean_squared_error(y_test, preds) ** 0.5),
        "r2": float(r2_score(y_test, preds)),
        "n_train": len(x_train),
        "n_test": len(x_test),
    }
    print("Test metrics:", json.dumps(metrics, indent=2))

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    joblib.dump(model, ARTIFACTS_DIR / "rating_model.joblib")
    (ARTIFACTS_DIR / "rating_features.json").write_text(json.dumps(list(x.columns)))
    (ARTIFACTS_DIR / "rating_metrics.json").write_text(json.dumps(metrics, indent=2))
    print(f"Saved artifacts to {ARTIFACTS_DIR}")


if __name__ == "__main__":
    main()
