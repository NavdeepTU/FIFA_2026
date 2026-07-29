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
    "mv_tournament_progression",
]


def get_engine():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL env var is required, e.g. postgresql://user:pass@host:5432/db")
    return create_engine(db_url)


def apply_schema(engine) -> None:
    ddl = SCHEMA_SQL.read_text()
    with engine.begin() as conn:
        for statement in ddl.split(";"):
            statement = statement.strip()
            if statement and not statement.startswith("--"):
                conn.execute(text(statement))


def load_tables(engine, tables: dict[str, pd.DataFrame]) -> None:
    with engine.begin() as conn:
        # truncate in reverse FK order, then insert in forward order, so re-running is idempotent
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


if __name__ == "__main__":
    main()
