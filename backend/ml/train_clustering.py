"""Trains player-archetype clusters (unsupervised). Run: python backend/ml/train_clustering.py

Cluster count is picked by silhouette score over a small candidate range rather than
hardcoded -- the "right" number of playstyle archetypes isn't known upfront. Each
cluster gets an auto-generated label from its two most distinguishing (highest
z-scored) per-90 stats plus its most common position, so the output is directly
usable in the frontend without a manual labeling pass.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
from features import ARCHETYPE_PER90_COLUMNS, build_archetype_dataset
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

DATA_CSV = Path(__file__).parent.parent.parent / "data" / "raw" / "fifa_world_cup_2026_player_performance.csv"
ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
CANDIDATE_K = range(4, 9)

FEATURE_LABELS = {
    "goals_per90": "Goals", "assists_per90": "Assists", "shots_per90": "Shots",
    "key_passes_per90": "Key passes", "successful_passes_per90": "Passing",
    "dribbles_attempted_per90": "Dribbling", "tackles_per90": "Tackles",
    "interceptions_per90": "Interceptions", "clearances_per90": "Clearances",
    "aerial_duels_won_per90": "Aerial duels", "saves_per90": "Saves",
    "fouls_committed_per90": "Physicality",
}


def pick_k(scaled) -> int:
    best_k, best_score = CANDIDATE_K[0], -1.0
    for k in CANDIDATE_K:
        labels = KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(scaled)
        score = silhouette_score(scaled, labels)
        print(f"  k={k}: silhouette={score:.3f}")
        if score > best_score:
            best_k, best_score = k, score
    return best_k


def label_clusters(model: KMeans, feature_columns: list[str], df: pd.DataFrame, labels) -> dict[int, str]:
    df = df.copy()
    df["cluster"] = labels
    result = {}
    for cluster_id, center in enumerate(model.cluster_centers_):
        top_idx = center.argsort()[::-1][:2]
        top_features = [FEATURE_LABELS.get(feature_columns[i], feature_columns[i]) for i in top_idx]
        dominant_position = df.loc[df["cluster"] == cluster_id, "position"].mode().iloc[0]
        result[cluster_id] = f"{dominant_position}: {' + '.join(top_features)}"
    return result


def main() -> None:
    print(f"Building archetype dataset from {DATA_CSV} ...")
    players = build_archetype_dataset(str(DATA_CSV))
    feature_columns = [f"{c}_per90" for c in ARCHETYPE_PER90_COLUMNS]
    x = players[feature_columns].fillna(0.0)

    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(x)

    print("Selecting k via silhouette score ...")
    k = pick_k(x_scaled)
    print(f"Chosen k={k}")

    model = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = model.fit_predict(x_scaled)

    cluster_labels = label_clusters(model, feature_columns, players, labels)
    players["cluster"] = labels
    players["archetype"] = players["cluster"].map(cluster_labels)

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    joblib.dump(model, ARTIFACTS_DIR / "cluster_model.joblib")
    joblib.dump(scaler, ARTIFACTS_DIR / "cluster_scaler.joblib")
    (ARTIFACTS_DIR / "cluster_labels.json").write_text(
        json.dumps({str(k): v for k, v in cluster_labels.items()}, indent=2)
    )
    players[["player_id", "player_name", "team", "position", "cluster", "archetype"]].to_csv(
        ARTIFACTS_DIR / "player_archetypes.csv", index=False
    )
    print(f"Saved artifacts to {ARTIFACTS_DIR}")
    print(players["archetype"].value_counts())


if __name__ == "__main__":
    main()
