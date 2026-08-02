from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Connection, text

from app.db import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/standings")
def team_standings(db: Connection = Depends(get_db)):
    rows = db.execute(
        text(
            "select * from mv_team_standings "
            "order by points desc, goal_difference desc, goals_for desc"
        )
    ).mappings().all()
    return list(rows)


@router.get("/progression")
def tournament_progression(db: Connection = Depends(get_db)):
    rows = db.execute(
        text(
            "select * from mv_tournament_progression "
            "order by array_position(array['Group Stage','Round of 32','Round of 16',"
            "'Quarter Finals','Semi Finals','Third Place Match','Final'], tournament_stage)"
        )
    ).mappings().all()
    return list(rows)


@router.get("/leaderboard")
def leaderboard(
    metric: str = Query("goals", pattern="^(goals|assists|avg_player_rating|tackles|saves)$"),
    limit: int = Query(10, ge=1, le=100),
    position: str | None = None,
    db: Connection = Depends(get_db),
):
    sql = "select * from mv_player_tournament_stats"  # noqa: S608 - metric/position are allowlisted below
    params: dict = {"limit": limit}
    if position:
        sql += " where position = :position"
        params["position"] = position
    sql += f" order by {metric} desc nulls last limit :limit"
    rows = db.execute(text(sql), params).mappings().all()
    return list(rows)


@router.get("/players/ids")
def player_ids(db: Connection = Depends(get_db)):
    """Every player ID, no ranking/limit -- a directory listing, distinct from
    /leaderboard's capped top-N. Exists so the static-exported frontend can enumerate
    every /players/{id} page to pre-render at build time (output: "export" requires
    knowing every dynamic route value upfront; there's no server left at request time
    to render one on demand)."""
    rows = db.execute(text("select player_id from mv_player_tournament_stats")).mappings().all()
    return [row["player_id"] for row in rows]


@router.get("/players/{player_id}")
def player_profile(player_id: str, db: Connection = Depends(get_db)):
    player = db.execute(
        text("select * from mv_player_tournament_stats where player_id = :pid"),
        {"pid": player_id},
    ).mappings().first()
    if not player:
        raise HTTPException(status_code=404, detail="player not found")

    matches = db.execute(
        text(
            "select m.match_id, m.match_date, m.tournament_stage, s.opponent_team, "
            "s.match_result, s.minutes_played, s.goals, s.assists, s.player_rating "
            "from player_match_stats s join matches m on m.match_id = s.match_id "
            "where s.player_id = :pid order by m.match_date"
        ),
        {"pid": player_id},
    ).mappings().all()

    return {"profile": dict(player), "matches": list(matches)}


@router.get("/teams/{team_name}")
def team_profile(team_name: str, db: Connection = Depends(get_db)):
    standing = db.execute(
        text("select * from mv_team_standings where team = :team"),
        {"team": team_name},
    ).mappings().first()
    if not standing:
        raise HTTPException(status_code=404, detail="team not found")

    roster = db.execute(
        text(
            "select * from mv_player_tournament_stats where team = :team "
            "order by avg_player_rating desc nulls last"
        ),
        {"team": team_name},
    ).mappings().all()

    return {"standing": dict(standing), "roster": list(roster)}


@router.get("/matches")
def matches(
    stage: str | None = None,
    team: str | None = None,
    db: Connection = Depends(get_db),
):
    sql = "select * from matches where 1=1"
    params: dict = {}
    if stage:
        sql += " and tournament_stage = :stage"
        params["stage"] = stage
    if team:
        sql += " and (team_a = :team or team_b = :team)"
        params["team"] = team
    sql += " order by match_date"
    rows = db.execute(text(sql), params).mappings().all()
    return list(rows)


@router.get("/matches/{match_id}")
def match_detail(match_id: str, db: Connection = Depends(get_db)):
    match = db.execute(
        text("select * from matches where match_id = :mid"),
        {"mid": match_id},
    ).mappings().first()
    if not match:
        raise HTTPException(status_code=404, detail="match not found")

    box_score = db.execute(
        text(
            "select p.player_name, s.team, s.goals, s.assists, s.player_rating, "
            "s.yellow_cards, s.red_cards "
            "from player_match_stats s join players p on p.player_id = s.player_id "
            "where s.match_id = :mid order by s.player_rating desc nulls last"
        ),
        {"mid": match_id},
    ).mappings().all()

    return {"match": dict(match), "box_score": list(box_score)}
