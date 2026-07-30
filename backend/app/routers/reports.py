from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from genai.embeddings import build_summary_text
from genai.llm import generate_player_report
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
