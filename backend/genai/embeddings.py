"""Player summary text + embedding generation for the Phase 3 RAG layer.

Embedding model is local/offline (fastembed, ONNX-based) rather than a hosted API --
Groq (the project's LLM provider) doesn't offer an embeddings endpoint, and a local
384-dim model avoids adding a second API dependency/cost just for retrieval. 384 is
also what `player_embeddings.embedding` is declared as in `etl/schema.sql`.
"""
from __future__ import annotations

from collections.abc import Iterable

EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384

_model = None


def get_embedding_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        _model = TextEmbedding(model_name=EMBEDDING_MODEL_NAME)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    return [vec.tolist() for vec in get_embedding_model().embed(texts)]


def build_summary_text(row: dict) -> str:
    """Turns one `mv_player_tournament_stats` row into a natural-language summary
    for embedding. Plain sentences (not a stat dump) since retrieval quality depends
    on the text reading like something a person would ask about.
    """
    matches = row["matches_played"] or 0
    minutes = row["minutes_played"] or 0
    goals = row["goals"] or 0
    assists = row["assists"] or 0
    shots = row["shots"] or 0
    shots_on_target = row["shots_on_target"] or 0
    xg = float(row["expected_goals_xg"] or 0)
    xa = float(row["expected_assists_xa"] or 0)
    pass_accuracy = float(row["avg_pass_accuracy"] or 0)
    tackles = row["tackles"] or 0
    interceptions = row["interceptions"] or 0
    saves = row["saves"] or 0
    clean_sheets = row["clean_sheets"] or 0
    yellow_cards = row["yellow_cards"] or 0
    red_cards = row["red_cards"] or 0
    avg_rating = float(row["avg_player_rating"] or 0)

    sentences = [
        f"{row['player_name']} is a {row['position']} for {row['team']}.",
        f"Across {matches} matches ({minutes} minutes played), they scored {goals} goals and "
        f"{assists} assists from {shots} shots ({shots_on_target} on target, xG {xg:.1f}, xA {xa:.1f}).",
        f"Passing accuracy averaged {pass_accuracy:.0f}%. "
        f"Defensively they made {tackles} tackles and {interceptions} interceptions.",
    ]
    if row["position"] == "Goalkeeper" or saves:
        sentences.append(f"They recorded {saves} saves and {clean_sheets} clean sheets.")
    sentences.append(
        f"Discipline: {yellow_cards} yellow card(s) and {red_cards} red card(s). "
        f"Average match rating {avg_rating:.2f}."
    )
    return " ".join(sentences)


def to_pgvector_literal(vector: Iterable[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vector) + "]"
