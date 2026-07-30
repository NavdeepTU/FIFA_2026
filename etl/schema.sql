-- FIFA World Cup 2026 analytics schema
-- Grain: one row in player_match_stats per (player_id, match_id).
-- Note: the source dataset's total_*_tournament / tournament_rating columns are noisy/synthetic
-- (not true running totals) -- they're kept for reference but real aggregates are computed via
-- the materialized views below from the granular per-match stats instead.

create extension if not exists vector;

create table if not exists teams (
    team_name text primary key
);

create table if not exists players (
    player_id text primary key,
    player_name text not null,
    age integer,
    nationality text,
    team text references teams(team_name),
    jersey_number integer,
    position text,
    height_cm integer,
    weight_kg integer,
    preferred_foot text,
    club_name text,
    market_value_eur bigint
);

create table if not exists matches (
    match_id text primary key,
    match_date date,
    stadium text,
    city text,
    tournament_stage text,
    team_a text references teams(team_name),
    team_b text references teams(team_name),
    goals_a integer,
    goals_b integer
);

create table if not exists player_match_stats (
    player_id text references players(player_id),
    match_id text references matches(match_id),
    team text references teams(team_name),
    opponent_team text references teams(team_name),
    match_result text,
    minutes_played integer,
    goals integer,
    assists integer,
    shots integer,
    shots_on_target integer,
    expected_goals_xg numeric,
    expected_assists_xa numeric,
    key_passes integer,
    successful_passes integer,
    total_passes integer,
    pass_accuracy numeric,
    dribbles_attempted integer,
    successful_dribbles integer,
    crosses integer,
    successful_crosses integer,
    tackles integer,
    interceptions integer,
    clearances integer,
    blocks integer,
    aerial_duels_won integer,
    aerial_duels_lost integer,
    recoveries integer,
    defensive_actions integer,
    fouls_committed integer,
    fouls_suffered integer,
    yellow_cards integer,
    red_cards integer,
    offsides integer,
    saves integer,
    save_percentage numeric,
    punches integer,
    clean_sheet boolean,
    goals_conceded integer,
    penalty_saves integer,
    distance_covered_km numeric,
    sprint_distance_km numeric,
    top_speed_kmh numeric,
    accelerations integer,
    decelerations integer,
    stamina_score numeric,
    player_rating numeric,
    performance_score numeric,
    offensive_contribution numeric,
    defensive_contribution numeric,
    possession_impact numeric,
    pressure_resistance numeric,
    creativity_score numeric,
    consistency_score numeric,
    clutch_performance_score numeric,
    primary key (player_id, match_id)
);

create index if not exists idx_pms_match on player_match_stats(match_id);
create index if not exists idx_pms_player on player_match_stats(player_id);
create index if not exists idx_pms_team on player_match_stats(team);

-- Embeddings for the GenAI RAG layer (Phase 3): one summary text + vector per player,
-- computed from the aggregates below, refreshed after ETL loads.
create table if not exists player_embeddings (
    player_id text primary key references players(player_id),
    summary_text text not null,
    embedding vector(384),
    updated_at timestamptz default now()
);

-- Same idea as player_embeddings, one row per team -- lets /chat answer team-level
-- questions ("which team had the best defense?") instead of only player ones.
create table if not exists team_embeddings (
    team_name text primary key references teams(team_name),
    summary_text text not null,
    embedding vector(384),
    updated_at timestamptz default now()
);

-- Cached, Groq-generated scouting reports (Phase 3): one per player, regenerated
-- on demand via POST /reports/players/{id} rather than every request -- keeps repeat
-- views free and avoids re-spending Groq tokens on unchanged data.
create table if not exists player_reports (
    player_id text primary key references players(player_id),
    report_text text not null,
    generated_at timestamptz default now()
);

-- Same idea as player_reports, one per team -- POST /reports/teams/{team}.
create table if not exists team_reports (
    team_name text primary key references teams(team_name),
    report_text text not null,
    generated_at timestamptz default now()
);

-- ==== Materialized aggregate views (Phase 1 analytics) ====

drop materialized view if exists mv_player_tournament_stats;
create materialized view mv_player_tournament_stats as
select
    p.player_id,
    p.player_name,
    p.team,
    p.position,
    count(*) as matches_played,
    sum(s.minutes_played) as minutes_played,
    sum(s.goals) as goals,
    sum(s.assists) as assists,
    sum(s.shots) as shots,
    sum(s.shots_on_target) as shots_on_target,
    sum(s.expected_goals_xg) as expected_goals_xg,
    sum(s.expected_assists_xa) as expected_assists_xa,
    avg(s.pass_accuracy) as avg_pass_accuracy,
    sum(s.tackles) as tackles,
    sum(s.interceptions) as interceptions,
    sum(s.saves) as saves,
    sum(case when s.clean_sheet then 1 else 0 end) as clean_sheets,
    sum(s.yellow_cards) as yellow_cards,
    sum(s.red_cards) as red_cards,
    avg(s.player_rating) as avg_player_rating
from player_match_stats s
join players p on p.player_id = s.player_id
group by p.player_id, p.player_name, p.team, p.position;

create unique index if not exists idx_mv_player_tournament_stats on mv_player_tournament_stats(player_id);

drop materialized view if exists mv_team_standings;
create materialized view mv_team_standings as
with team_matches as (
    select team_a as team, match_id, goals_a as goals_for, goals_b as goals_against, tournament_stage
    from matches
    union all
    select team_b as team, match_id, goals_b as goals_for, goals_a as goals_against, tournament_stage
    from matches
)
select
    team,
    count(*) as matches_played,
    sum(case when goals_for > goals_against then 1 else 0 end) as wins,
    sum(case when goals_for = goals_against then 1 else 0 end) as draws,
    sum(case when goals_for < goals_against then 1 else 0 end) as losses,
    sum(goals_for) as goals_for,
    sum(goals_against) as goals_against,
    sum(goals_for - goals_against) as goal_difference,
    sum(case when goals_for > goals_against then 3 when goals_for = goals_against then 1 else 0 end) as points
from team_matches
group by team;

create unique index if not exists idx_mv_team_standings on mv_team_standings(team);

-- Box-score aggregates by team (as opposed to mv_team_standings' W/D/L/points from
-- match results) -- gives team summaries real defensive/offensive numbers (tackles,
-- saves, clean sheets) instead of just goals for/against.
drop materialized view if exists mv_team_tournament_stats;
create materialized view mv_team_tournament_stats as
select
    team,
    count(distinct match_id) as matches_played,
    sum(goals) as goals,
    sum(assists) as assists,
    sum(shots) as shots,
    sum(tackles) as tackles,
    sum(interceptions) as interceptions,
    sum(clearances) as clearances,
    sum(saves) as saves,
    sum(case when clean_sheet then 1 else 0 end) as clean_sheets,
    sum(yellow_cards) as yellow_cards,
    sum(red_cards) as red_cards,
    avg(pass_accuracy) as avg_pass_accuracy,
    avg(player_rating) as avg_player_rating
from player_match_stats
group by team;

create unique index if not exists idx_mv_team_tournament_stats on mv_team_tournament_stats(team);

drop materialized view if exists mv_tournament_progression;
create materialized view mv_tournament_progression as
select
    tournament_stage,
    count(distinct match_id) as matches_played,
    sum(goals_a + goals_b) as total_goals,
    avg(goals_a + goals_b) as avg_goals_per_match
from matches
group by tournament_stage;

-- Call after each ETL load to refresh aggregates.
-- refresh materialized view mv_player_tournament_stats;
-- refresh materialized view mv_team_standings;
-- refresh materialized view mv_tournament_progression;
