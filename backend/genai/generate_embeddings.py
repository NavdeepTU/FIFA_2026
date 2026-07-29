"""Populates `player_embeddings` from `mv_player_tournament_stats`. Idempotent: safe
to re-run (upserts on player_id) -- run after every ETL load so embeddings stay in
sync with the underlying stats.

Usage:
    DATABASE_URL=postgresql://user:pass@host:5432/dbname python backend/genai/generate_embeddings.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).parent))
from embeddings import build_summary_text, embed_texts, to_pgvector_literal  # noqa: E402

UPSERT_SQL = text(
    """
    insert into player_embeddings (player_id, summary_text, embedding, updated_at)
    values (:player_id, :summary_text, cast(:embedding as vector), now())
    on conflict (player_id) do update
        set summary_text = excluded.summary_text,
            embedding = excluded.embedding,
            updated_at = excluded.updated_at
    """
)


def get_engine():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL env var is required, e.g. postgresql://user:pass@host:5432/db")
    return create_engine(db_url)


def fetch_player_stats(engine) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text("select * from mv_player_tournament_stats order by player_id")).mappings()
        return [dict(row) for row in rows]


def main() -> None:
    engine = get_engine()

    print("Fetching player aggregates from mv_player_tournament_stats ...")
    players = fetch_player_stats(engine)
    print(f"  {len(players)} players")

    print("Building summary texts ...")
    summaries = [build_summary_text(row) for row in players]

    print("Embedding summaries (fastembed, local) ...")
    vectors = embed_texts(summaries)

    print("Upserting into player_embeddings ...")
    params = [
        {
            "player_id": row["player_id"],
            "summary_text": summary,
            "embedding": to_pgvector_literal(vector),
        }
        for row, summary, vector in zip(players, summaries, vectors, strict=True)
    ]
    with engine.begin() as conn:
        conn.execute(UPSERT_SQL, params)

    print(f"Done. {len(params)} player embeddings upserted.")


if __name__ == "__main__":
    main()
