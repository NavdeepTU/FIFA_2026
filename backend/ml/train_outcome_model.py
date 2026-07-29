"""Trains the match-outcome (W/D/L) classifier. Run: python backend/ml/train_outcome_model.py"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
from features import build_team_match_dataset
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

DATA_CSV = Path(__file__).parent.parent.parent / "data" / "raw" / "fifa_world_cup_2026_player_performance.csv"
ARTIFACTS_DIR = Path(__file__).parent / "artifacts"


def main() -> None:
    print(f"Loading team-match dataset from {DATA_CSV} ...")
    x, y = build_team_match_dataset(str(DATA_CSV))
    print(f"  {len(x)} team-match rows, {x.shape[1]} features, classes: {sorted(y.unique())}")

    encoder = LabelEncoder()
    y_encoded = encoder.fit_transform(y)

    x_train, x_test, y_train, y_test = train_test_split(
        x, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
    )

    model = XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric="mlogloss",
    )
    model.fit(x_train, y_train)

    preds = model.predict(x_test)
    report = classification_report(y_test, preds, target_names=encoder.classes_, output_dict=True)
    metrics = {
        "accuracy": float(accuracy_score(y_test, preds)),
        "classification_report": report,
        "n_train": len(x_train),
        "n_test": len(x_test),
        "classes": list(encoder.classes_),
    }
    print("Test accuracy:", metrics["accuracy"])

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    joblib.dump(model, ARTIFACTS_DIR / "outcome_model.joblib")
    joblib.dump(encoder, ARTIFACTS_DIR / "outcome_label_encoder.joblib")
    (ARTIFACTS_DIR / "outcome_features.json").write_text(json.dumps(list(x.columns)))
    (ARTIFACTS_DIR / "outcome_metrics.json").write_text(json.dumps(metrics, indent=2))
    print(f"Saved artifacts to {ARTIFACTS_DIR}")


if __name__ == "__main__":
    main()
