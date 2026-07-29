import Link from "next/link";
import { StatTile } from "@/components/StatTile";
import { DataTable } from "@/components/DataTable";
import { BarChartCard } from "@/components/charts/BarChartCard";
import {
  getStandings,
  getProgression,
  getLeaderboard,
  type TeamStanding,
  type StageProgression,
  type PlayerLeaderboardRow,
} from "@/lib/api";

export default async function HomePage() {
  let standings: TeamStanding[] = [];
  let progression: StageProgression[] = [];
  let topScorers: PlayerLeaderboardRow[] = [];
  let error: string | null = null;

  try {
    [standings, progression, topScorers] = await Promise.all([
      getStandings(),
      getProgression(),
      getLeaderboard("goals", 8),
    ]);
  } catch {
    error = "Could not reach the API. Is the backend running and DATABASE_URL configured?";
  }

  if (error) {
    return (
      <div className="rounded-lg p-6" style={{ background: "var(--surface-1)", border: "1px solid var(--border-hairline)" }}>
        <p style={{ color: "var(--text-secondary)" }}>{error}</p>
      </div>
    );
  }

  const totalGoals = progression.reduce((sum, s) => sum + s.total_goals, 0);
  const totalMatches = progression.reduce((sum, s) => sum + s.matches_played, 0);

  return (
    <div className="flex flex-col gap-8">
      <section className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatTile label="Teams" value={standings.length} />
        <StatTile label="Matches played" value={totalMatches} />
        <StatTile label="Goals scored" value={totalGoals} />
        <StatTile
          label="Avg goals / match"
          value={totalMatches ? (totalGoals / totalMatches).toFixed(2) : "-"}
        />
      </section>

      <section className="grid gap-8 md:grid-cols-2">
        <BarChartCard
          title="Top scorers (goals)"
          data={topScorers}
          nameKey="player_name"
          valueKey="goals"
          color="var(--series-1)"
        />
        <div className="flex flex-col gap-3">
          <h3 className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
            Standings (top 8 by points)
          </h3>
          <DataTable
            rows={standings.slice(0, 8)}
            rowKey={(r) => r.team}
            columns={[
              {
                header: "Team",
                accessor: (r) => (
                  <Link href={`/teams/${encodeURIComponent(r.team)}`} style={{ color: "var(--series-1)" }}>
                    {r.team}
                  </Link>
                ),
              },
              { header: "P", accessor: (r) => r.matches_played, align: "right" },
              { header: "W", accessor: (r) => r.wins, align: "right" },
              { header: "D", accessor: (r) => r.draws, align: "right" },
              { header: "L", accessor: (r) => r.losses, align: "right" },
              { header: "GD", accessor: (r) => r.goal_difference, align: "right" },
              { header: "Pts", accessor: (r) => r.points, align: "right" },
            ]}
          />
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
          Tournament progression
        </h3>
        <DataTable
          rows={progression}
          rowKey={(r) => r.tournament_stage}
          columns={[
            { header: "Stage", accessor: (r) => r.tournament_stage },
            { header: "Matches", accessor: (r) => r.matches_played, align: "right" },
            { header: "Goals", accessor: (r) => r.total_goals, align: "right" },
            { header: "Avg goals/match", accessor: (r) => r.avg_goals_per_match.toFixed(2), align: "right" },
          ]}
        />
      </section>
    </div>
  );
}
