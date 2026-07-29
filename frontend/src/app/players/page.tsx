import Link from "next/link";
import { DataTable } from "@/components/DataTable";
import { MetricSelect } from "@/components/MetricSelect";
import { getLeaderboard, type PlayerLeaderboardRow } from "@/lib/api";

export default async function PlayersPage({
  searchParams,
}: {
  searchParams: Promise<{ metric?: string }>;
}) {
  const { metric = "goals" } = await searchParams;

  let rows: PlayerLeaderboardRow[] = [];
  let error: string | null = null;
  try {
    rows = await getLeaderboard(metric, 25);
  } catch {
    error = "Could not reach the API. Is the backend running and DATABASE_URL configured?";
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
          Player leaderboard
        </h1>
        <MetricSelect current={metric} />
      </div>

      {error ? (
        <p style={{ color: "var(--text-secondary)" }}>{error}</p>
      ) : (
        <DataTable
          rows={rows}
          rowKey={(r) => r.player_id}
          columns={[
            {
              header: "Player",
              accessor: (r) => (
                <Link href={`/players/${r.player_id}`} style={{ color: "var(--series-1)" }}>
                  {r.player_name}
                </Link>
              ),
            },
            { header: "Team", accessor: (r) => r.team },
            { header: "Pos", accessor: (r) => r.position },
            { header: "MP", accessor: (r) => r.matches_played, align: "right" },
            { header: "Goals", accessor: (r) => r.goals, align: "right" },
            { header: "Assists", accessor: (r) => r.assists, align: "right" },
            { header: "xG", accessor: (r) => r.expected_goals_xg?.toFixed(1), align: "right" },
            { header: "Rating", accessor: (r) => r.avg_player_rating?.toFixed(1), align: "right" },
          ]}
        />
      )}
    </div>
  );
}
