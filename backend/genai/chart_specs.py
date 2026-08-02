"""The allowlist behind the natural-language -> chart feature.

Every query here is a fixed string literal, never built from user or LLM input --
the LLM's only job (see genai/llm.py's classify_chart_template()) is to pick one of
these dict KEYS by name, never to contribute to SQL text. This is the actual security
boundary: even a fully compromised or hallucinating LLM response can, at worst, select
a name that isn't in this dict (rejected) -- it cannot inject SQL, because no LLM
output ever reaches a query string. See docs/project_scope.md §5: "an allowlisted
query spec the backend validates and executes -- never LLM-generated SQL run directly."
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChartSpecDef:
    description: str  # shown to the LLM so it can match a question to this template
    sql: str  # fixed, parameter-free query; every column is aliased to label/value
    chart_type: str  # "bar" (the only type the frontend needs to support for now)
    title: str


CHART_SPECS: dict[str, ChartSpecDef] = {
    "top_scorers": ChartSpecDef(
        description="top goal scorers, players with the most goals",
        sql="select player_name as label, goals as value from mv_player_tournament_stats "
        "order by goals desc nulls last limit 10",
        chart_type="bar",
        title="Top 10 goal scorers",
    ),
    "top_assists": ChartSpecDef(
        description="players with the most assists, best playmakers",
        sql="select player_name as label, assists as value from mv_player_tournament_stats "
        "order by assists desc nulls last limit 10",
        chart_type="bar",
        title="Top 10 by assists",
    ),
    "top_tacklers": ChartSpecDef(
        description="players with the most tackles, best defenders by tackles",
        sql="select player_name as label, tackles as value from mv_player_tournament_stats "
        "order by tackles desc nulls last limit 10",
        chart_type="bar",
        title="Top 10 by tackles",
    ),
    "top_goalkeepers": ChartSpecDef(
        description="goalkeepers with the most saves, best goalkeepers",
        sql="select player_name as label, saves as value from mv_player_tournament_stats "
        "where position = 'Goalkeeper' order by saves desc nulls last limit 10",
        chart_type="bar",
        title="Top 10 goalkeepers by saves",
    ),
    "team_points": ChartSpecDef(
        description="team standings, league table, teams ranked by points",
        sql="select team as label, points as value from mv_team_standings "
        "order by points desc limit 16",
        chart_type="bar",
        title="Team standings by points",
    ),
    "team_goals_for": ChartSpecDef(
        description="teams that scored the most goals, top attacking teams",
        sql="select team as label, goals_for as value from mv_team_standings "
        "order by goals_for desc limit 16",
        chart_type="bar",
        title="Teams by goals scored",
    ),
    "team_clean_sheets": ChartSpecDef(
        description="teams with the most clean sheets, best defensive teams",
        sql="select team as label, clean_sheets as value from mv_team_tournament_stats "
        "order by clean_sheets desc nulls last limit 16",
        chart_type="bar",
        title="Teams by clean sheets",
    ),
    "goals_by_stage": ChartSpecDef(
        description="goals scored per tournament stage, how scoring changed through the tournament",
        sql="select tournament_stage as label, total_goals as value from mv_tournament_progression "
        "order by array_position(array['Group Stage','Round of 32','Round of 16',"
        "'Quarter Finals','Semi Finals','Third Place Match','Final'], tournament_stage)",
        chart_type="bar",
        title="Total goals by tournament stage",
    ),
    "avg_rating_by_position": ChartSpecDef(
        description="average player rating by position, which position rates highest",
        sql="select position as label, avg(avg_player_rating) as value "
        "from mv_player_tournament_stats group by position order by value desc nulls last",
        chart_type="bar",
        title="Average player rating by position",
    ),
}
