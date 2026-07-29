import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from load import split_sql_statements  # noqa: E402


def test_split_sql_statements_basic():
    ddl = "create table a (id int);\ncreate table b (id int);"
    assert split_sql_statements(ddl) == ["create table a (id int)", "create table b (id int)"]


def test_split_sql_statements_ignores_leading_top_level_comment():
    ddl = "-- header comment\ncreate table a (id int);"
    assert split_sql_statements(ddl) == ["create table a (id int)"]


def test_split_sql_statements_keeps_statement_preceded_by_comment_with_no_separating_semicolon():
    """Regression test: a comment block directly preceding a CREATE TABLE, with no
    blank statement between them, previously made the whole `;`-delimited chunk look
    comment-only and get silently dropped -- this is exactly how `player_embeddings`
    ended up missing from freshly-loaded databases despite `etl/load.py` reporting
    success.
    """
    ddl = (
        "create table a (id int);\n\n"
        "-- comment describing table b\n"
        "-- second line of the comment\n"
        "create table b (id int);"
    )
    assert split_sql_statements(ddl) == ["create table a (id int)", "create table b (id int)"]
