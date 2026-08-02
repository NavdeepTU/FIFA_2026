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


def build_team_summary_text(row: dict) -> str:
    """Turns one team row (mv_team_standings joined with mv_team_tournament_stats) into
    a natural-language summary for embedding -- the team-level counterpart to
    build_summary_text(), covering both results (wins/draws/losses/points) and
    box-score aggregates (tackles, saves, clean sheets) so questions about a team's
    defense or discipline have something concrete to retrieve, not just goals for/against.
    """
    matches = row["matches_played"] or 0
    wins = row["wins"] or 0
    draws = row["draws"] or 0
    losses = row["losses"] or 0
    goals_for = row["goals_for"] or 0
    goals_against = row["goals_against"] or 0
    points = row["points"] or 0
    tackles = row["tackles"] or 0
    interceptions = row["interceptions"] or 0
    clearances = row["clearances"] or 0
    saves = row["saves"] or 0
    clean_sheets = row["clean_sheets"] or 0
    yellow_cards = row["yellow_cards"] or 0
    red_cards = row["red_cards"] or 0
    pass_accuracy = float(row["avg_pass_accuracy"] or 0)
    avg_rating = float(row["avg_player_rating"] or 0)

    sentences = [
        f"{row['team']} played {matches} matches, with a record of {wins} wins, {draws} draws, "
        f"and {losses} losses ({points} points).",
        f"They scored {goals_for} goals and conceded {goals_against}.",
        f"Defensively the squad made {tackles} tackles, {interceptions} interceptions, and "
        f"{clearances} clearances, with {saves} goalkeeper saves and {clean_sheets} clean sheets.",
        f"Passing accuracy averaged {pass_accuracy:.0f}% across the squad, with an average player "
        f"rating of {avg_rating:.2f}.",
        f"Discipline: {yellow_cards} yellow card(s) and {red_cards} red card(s).",
    ]
    return " ".join(sentences)


def build_match_summary_text(match: dict, performers: list[dict]) -> str:
    """Turns one match row plus its full player_match_stats box score into a natural-
    language summary for the match-recap prompt (reports.py). Unlike
    build_summary_text()/build_team_summary_text(), this has no matching embeddings
    table -- matches aren't retrieved via /chat, only players and teams are -- so this
    summary exists purely as Groq context, not as anything embedded.
    """
    scoreline = f"{match['team_a']} {match['goals_a']}-{match['goals_b']} {match['team_b']}"
    sentences = [
        f"{match['tournament_stage']} match at {match['stadium']}, {match['city']} on "
        f"{match['match_date']}: {scoreline}."
    ]

    scorers = [p for p in performers if (p["goals"] or 0) > 0]
    if scorers:
        scorer_lines = ", ".join(
            f"{p['player_name']} ({p['team']}, {p['goals']} goal(s))" for p in scorers
        )
        sentences.append(f"Goal scorers: {scorer_lines}.")

    if performers:
        top = performers[0]  # caller sorts by player_rating desc
        sentences.append(
            f"Top-rated performer: {top['player_name']} ({top['team']}), "
            f"rating {float(top['player_rating'] or 0):.2f}."
        )

    carded = [p for p in performers if (p["yellow_cards"] or 0) or (p["red_cards"] or 0)]
    if carded:
        card_lines = ", ".join(
            f"{p['player_name']} ({p['yellow_cards'] or 0}Y/{p['red_cards'] or 0}R)" for p in carded
        )
        sentences.append(f"Cards: {card_lines}.")

    return " ".join(sentences)


def to_pgvector_literal(vector: Iterable[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vector) + "]"
