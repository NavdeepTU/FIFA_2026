const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export type TeamStanding = {
  team: string;
  matches_played: number;
  wins: number;
  draws: number;
  losses: number;
  goals_for: number;
  goals_against: number;
  goal_difference: number;
  points: number;
};

export type StageProgression = {
  tournament_stage: string;
  matches_played: number;
  total_goals: number;
  avg_goals_per_match: number;
};

export type PlayerLeaderboardRow = {
  player_id: string;
  player_name: string;
  team: string;
  position: string;
  matches_played: number;
  minutes_played: number;
  goals: number;
  assists: number;
  shots: number;
  shots_on_target: number;
  expected_goals_xg: number;
  expected_assists_xa: number;
  avg_pass_accuracy: number;
  tackles: number;
  interceptions: number;
  saves: number;
  clean_sheets: number;
  yellow_cards: number;
  red_cards: number;
  avg_player_rating: number;
};

export type PlayerMatch = {
  match_id: string;
  match_date: string;
  tournament_stage: string;
  opponent_team: string;
  match_result: string;
  minutes_played: number;
  goals: number;
  assists: number;
  player_rating: number;
};

export type PlayerProfile = {
  profile: PlayerLeaderboardRow;
  matches: PlayerMatch[];
};

export type TeamProfile = {
  standing: TeamStanding;
  roster: PlayerLeaderboardRow[];
};

export type MatchRow = {
  match_id: string;
  match_date: string;
  stadium: string;
  city: string;
  tournament_stage: string;
  team_a: string;
  team_b: string;
  goals_a: number;
  goals_b: number;
};

export const getStandings = () => apiFetch<TeamStanding[]>("/analytics/standings");

export const getProgression = () => apiFetch<StageProgression[]>("/analytics/progression");

export const getLeaderboard = (metric: string, limit = 10, position?: string) => {
  const params = new URLSearchParams({ metric, limit: String(limit) });
  if (position) params.set("position", position);
  return apiFetch<PlayerLeaderboardRow[]>(`/analytics/leaderboard?${params}`);
};

export const getPlayerProfile = (playerId: string) =>
  apiFetch<PlayerProfile>(`/analytics/players/${playerId}`);

export const getTeamProfile = (teamName: string) =>
  apiFetch<TeamProfile>(`/analytics/teams/${encodeURIComponent(teamName)}`);

export type RatingPredictionInput = {
  minutes_played: number;
  goals: number;
  assists: number;
  shots: number;
  shots_on_target: number;
  expected_goals_xg: number;
  key_passes: number;
  successful_passes: number;
  total_passes: number;
  pass_accuracy: number;
  tackles: number;
  interceptions: number;
  position: string;
};

export const predictRating = (input: RatingPredictionInput) =>
  apiPost<{ predicted_rating: number }>("/predict/rating", input);

export type ChatSource = {
  entity_type: "player" | "team";
  entity_id: string;
  name: string;
  team: string;
  position: string | null;
  summary_text: string;
  distance: number;
};

export type ChatAskResponse = {
  answer: string;
  sources: ChatSource[];
};

export const askChat = (query: string, top_k = 5) =>
  apiPost<ChatAskResponse>("/chat/ask", { query, top_k });

export type ScoutingReport = {
  player_id: string;
  player_name: string;
  report_text: string;
  generated_at: string;
};

export async function getPlayerReport(playerId: string): Promise<ScoutingReport | null> {
  const res = await fetch(`${API_BASE_URL}/reports/players/${playerId}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API /reports/players/${playerId} failed: ${res.status}`);
  return res.json() as Promise<ScoutingReport>;
}

export const generatePlayerReport = (playerId: string) =>
  apiPost<ScoutingReport>(`/reports/players/${playerId}`, {});

export type TeamScoutingReport = {
  team_name: string;
  report_text: string;
  generated_at: string;
};

export async function getTeamReport(teamName: string): Promise<TeamScoutingReport | null> {
  const res = await fetch(`${API_BASE_URL}/reports/teams/${encodeURIComponent(teamName)}`, {
    cache: "no-store",
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API /reports/teams/${teamName} failed: ${res.status}`);
  return res.json() as Promise<TeamScoutingReport>;
}

export const generateTeamReport = (teamName: string) =>
  apiPost<TeamScoutingReport>(`/reports/teams/${encodeURIComponent(teamName)}`, {});

export const getMatches = (stage?: string, team?: string) => {
  const params = new URLSearchParams();
  if (stage) params.set("stage", stage);
  if (team) params.set("team", team);
  const qs = params.toString();
  return apiFetch<MatchRow[]>(`/analytics/matches${qs ? `?${qs}` : ""}`);
};
