"""Populates `team_embeddings` from `mv_team_standings` + `mv_team_tournament_stats`.
Idempotent: safe to re-run (upserts on team_name) -- run after every ETL load so
embeddings stay in sync with the underlying stats, same as generate_embeddings.py.

Usage:
    DATABASE_URL=postgresql://user:pass@host:5432/dbname python backend/genai/generate_team_embeddings.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).parent))
from embeddings import build_team_summary_text, embed_texts, to_pgvector_literal  # noqa: E402

UPSERT_SQL = text(
    """
    insert into team_embeddings (team_name, summary_text, embedding, updated_at)
    values (:team_name, :summary_text, cast(:embedding as vector), now())
    on conflict (team_name) do update
        set summary_text = excluded.summary_text,
            embedding = excluded.embedding,
            updated_at = excluded.updated_at
    """
)

TEAM_STATS_SQL = text(
    """
    select s.team, s.matches_played, s.wins, s.draws, s.losses, s.goals_for, s.goals_against,
           s.points, t.tackles, t.interceptions, t.clearances, t.saves, t.clean_sheets,
           t.yellow_cards, t.red_cards, t.avg_pass_accuracy, t.avg_player_rating
    from mv_team_standings s
    join mv_team_tournament_stats t on t.team = s.team
    order by s.team
    """
)


def get_engine():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL env var is required, e.g. postgresql://user:pass@host:5432/db")
    return create_engine(db_url)


def fetch_team_stats(engine) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(TEAM_STATS_SQL).mappings()
        return [dict(row) for row in rows]


def main() -> None:
    engine = get_engine()

    print("Fetching team aggregates from mv_team_standings + mv_team_tournament_stats ...")
    teams = fetch_team_stats(engine)
    print(f"  {len(teams)} teams")

    print("Building summary texts ...")
    summaries = [build_team_summary_text(row) for row in teams]

    print("Embedding summaries (fastembed, local) ...")
    vectors = embed_texts(summaries)

    print("Upserting into team_embeddings ...")
    params = [
        {
            "team_name": row["team"],
            "summary_text": summary,
            "embedding": to_pgvector_literal(vector),
        }
        for row, summary, vector in zip(teams, summaries, vectors, strict=True)
    ]
    with engine.begin() as conn:
        conn.execute(UPSERT_SQL, params)

    print(f"Done. {len(params)} team embeddings upserted.")


if __name__ == "__main__":
    main()
