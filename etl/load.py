"""Load the transformed FIFA tables into Postgres. Idempotent: safe to re-run.

Usage:
    DATABASE_URL=postgresql://user:pass@host:5432/dbname python etl/load.py [csv_path]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).parent))
from transform import transform  # noqa: E402

DEFAULT_CSV = Path(__file__).parent.parent / "data" / "raw" / "fifa_world_cup_2026_player_performance.csv"
SCHEMA_SQL = Path(__file__).parent / "schema.sql"

# load order matters: respects FK dependencies (teams -> players/matches -> player_match_stats)
TABLE_ORDER = ["teams", "players", "matches", "player_match_stats"]

MATERIALIZED_VIEWS = [
    "mv_player_tournament_stats",
    "mv_team_standings",
    "mv_team_tournament_stats",
    "mv_tournament_progression",
]


def get_engine():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL env var is required, e.g. postgresql://user:pass@host:5432/db")
    return create_engine(db_url)


def split_sql_statements(ddl: str) -> list[str]:
    """Splits a `;`-delimited DDL script into individual statements, stripping
    full-line `--` comments per line rather than only checking each chunk's first
    line -- a comment block immediately preceding a statement (no blank statement
    between them) would otherwise make the whole chunk look comment-only and get
    dropped, SQL included.
    """
    statements = []
    for chunk in ddl.split(";"):
        lines = [line for line in chunk.splitlines() if not line.strip().startswith("--")]
        statement = "\n".join(lines).strip()
        if statement:
            statements.append(statement)
    return statements


def apply_schema(engine) -> None:
    ddl = SCHEMA_SQL.read_text()
    with engine.begin() as conn:
        for statement in split_sql_statements(ddl):
            conn.execute(text(statement))


def load_tables(engine, tables: dict[str, pd.DataFrame]) -> None:
    with engine.begin() as conn:
        # truncate in reverse FK order, then insert in forward order, so re-running is idempotent.
        # CASCADE also empties player_embeddings / team_embeddings / player_reports (they all have
        # FKs into players / teams) -- unavoidable with plain truncate+reload, so every ETL run
        # wipes them, not just a first run. That's why main() prints a reminder below.
        for name in reversed(TABLE_ORDER):
            conn.execute(text(f"truncate table {name} cascade"))
        for name in TABLE_ORDER:
            tables[name].to_sql(name, conn, if_exists="append", index=False, method="multi", chunksize=5000)


def refresh_views(engine) -> None:
    with engine.begin() as conn:
        for view in MATERIALIZED_VIEWS:
            conn.execute(text(f"refresh materialized view {view}"))


def main() -> None:
    csv_path = sys.argv[1] if len(sys.argv) > 1 else str(DEFAULT_CSV)
    engine = get_engine()

    print(f"Reading and transforming {csv_path} ...")
    tables = transform(csv_path)
    for name, df in tables.items():
        print(f"  {name}: {len(df)} rows")

    print("Applying schema ...")
    apply_schema(engine)

    print("Loading tables ...")
    load_tables(engine, tables)

    print("Refreshing materialized views ...")
    refresh_views(engine)

    print("Done.")
    print(
        "Note: this truncated (via CASCADE) any existing player_embeddings / team_embeddings / "
        "player_reports rows. Run `make genai-embed` and `make genai-embed-teams` to regenerate "
        "embeddings; cached scouting reports regenerate on demand via POST /reports/players/{id}."
    )


if __name__ == "__main__":
    main()
