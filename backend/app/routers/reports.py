from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from genai.embeddings import build_summary_text, build_team_summary_text
from genai.llm import generate_player_report, generate_team_report
from pydantic import BaseModel
from sqlalchemy import Connection, text

from app.db import get_db
from app.rate_limit import rate_limit

router = APIRouter(prefix="/reports", tags=["reports"])


class ScoutingReport(BaseModel):
    player_id: str
    player_name: str
    report_text: str
    generated_at: datetime


class TeamScoutingReport(BaseModel):
    team_name: str
    report_text: str
    generated_at: datetime


def _fetch_player_context(player_id: str, db: Connection) -> dict | None:
    profile = db.execute(
        text("select * from mv_player_tournament_stats where player_id = :pid"),
        {"pid": player_id},
    ).mappings().first()
    if not profile:
        return None

    matches = db.execute(
        text(
            "select m.match_date, m.tournament_stage, s.opponent_team, s.match_result, "
            "s.minutes_played, s.goals, s.assists, s.player_rating "
            "from player_match_stats s join matches m on m.match_id = s.match_id "
            "where s.player_id = :pid order by m.match_date desc limit 5"
        ),
        {"pid": player_id},
    ).mappings().all()
    return {"profile": dict(profile), "recent_matches": [dict(m) for m in matches]}


@router.get("/players/{player_id}", response_model=ScoutingReport)
def get_cached_report(player_id: str, db: Connection = Depends(get_db)):
    row = db.execute(
        text(
            "select pr.player_id, p.player_name, pr.report_text, pr.generated_at "
            "from player_reports pr join players p on p.player_id = pr.player_id "
            "where pr.player_id = :pid"
        ),
        {"pid": player_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="no report generated yet for this player")
    return row


@router.post("/players/{player_id}", response_model=ScoutingReport)
def generate_report(
    player_id: str, db: Connection = Depends(get_db), _rate_limit: None = Depends(rate_limit)
):
    """Generates a fresh scouting report from the player's genuine box-score summary
    (build_summary_text(), same as embeddings) plus their 5 most recent matches for
    form/narrative color, then caches it -- repeat views don't re-spend Groq tokens
    unless explicitly regenerated.
    """
    context = _fetch_player_context(player_id, db)
    if not context:
        raise HTTPException(status_code=404, detail="player not found")

    summary = build_summary_text(context["profile"])
    try:
        report_text = generate_player_report(summary, context["recent_matches"])
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"generation unavailable: {e}") from e

    row = db.execute(
        text(
            "insert into player_reports (player_id, report_text, generated_at) "
            "values (:pid, :report_text, now()) "
            "on conflict (player_id) do update "
            "set report_text = excluded.report_text, generated_at = excluded.generated_at "
            "returning player_id, report_text, generated_at"
        ),
        {"pid": player_id, "report_text": report_text},
    ).mappings().first()
    db.commit()

    return {
        "player_id": row["player_id"],
        "player_name": context["profile"]["player_name"],
        "report_text": row["report_text"],
        "generated_at": row["generated_at"],
    }


def _fetch_team_context(team_name: str, db: Connection) -> dict | None:
    profile = db.execute(
        text(
            "select s.team, s.matches_played, s.wins, s.draws, s.losses, s.goals_for, "
            "s.goals_against, s.points, t.tackles, t.interceptions, t.clearances, t.saves, "
            "t.clean_sheets, t.yellow_cards, t.red_cards, t.avg_pass_accuracy, t.avg_player_rating "
            "from mv_team_standings s join mv_team_tournament_stats t on t.team = s.team "
            "where s.team = :team"
        ),
        {"team": team_name},
    ).mappings().first()
    if not profile:
        return None

    matches = db.execute(
        text(
            "select match_date, tournament_stage, "
            "case when team_a = :team then team_b else team_a end as opponent, "
            "case when team_a = :team then goals_a else goals_b end as goals_for, "
            "case when team_a = :team then goals_b else goals_a end as goals_against "
            "from matches where team_a = :team or team_b = :team "
            "order by match_date desc limit 5"
        ),
        {"team": team_name},
    ).mappings().all()
    return {"profile": dict(profile), "recent_matches": [dict(m) for m in matches]}


@router.get("/teams/{team_name}", response_model=TeamScoutingReport)
def get_cached_team_report(team_name: str, db: Connection = Depends(get_db)):
    row = db.execute(
        text("select team_name, report_text, generated_at from team_reports where team_name = :team"),
        {"team": team_name},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="no report generated yet for this team")
    return row


@router.post("/teams/{team_name}", response_model=TeamScoutingReport)
def generate_team_report_route(
    team_name: str, db: Connection = Depends(get_db), _rate_limit: None = Depends(rate_limit)
):
    """Mirrors POST /reports/players/{id} for teams: build_team_summary_text() (same
    as team embeddings) plus the team's 5 most recent matches, generated via Groq,
    cached in team_reports.
    """
    context = _fetch_team_context(team_name, db)
    if not context:
        raise HTTPException(status_code=404, detail="team not found")

    summary = build_team_summary_text(context["profile"])
    try:
        report_text = generate_team_report(summary, context["recent_matches"])
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"generation unavailable: {e}") from e

    row = db.execute(
        text(
            "insert into team_reports (team_name, report_text, generated_at) "
            "values (:team, :report_text, now()) "
            "on conflict (team_name) do update "
            "set report_text = excluded.report_text, generated_at = excluded.generated_at "
            "returning team_name, report_text, generated_at"
        ),
        {"team": team_name, "report_text": report_text},
    ).mappings().first()
    db.commit()

    return row
