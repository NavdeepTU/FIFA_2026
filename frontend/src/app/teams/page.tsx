import Link from "next/link";
import { DataTable } from "@/components/DataTable";
import { getStandings, type TeamStanding } from "@/lib/api";

export default async function TeamsPage() {
  let standings: TeamStanding[] = [];
  let error: string | null = null;
  try {
    standings = await getStandings();
  } catch {
    error = "Could not reach the API. Is the backend running and DATABASE_URL configured?";
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
        Team standings
      </h1>
      {error ? (
        <p style={{ color: "var(--text-secondary)" }}>{error}</p>
      ) : (
        <DataTable
          rows={standings}
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
            { header: "GF", accessor: (r) => r.goals_for, align: "right" },
            { header: "GA", accessor: (r) => r.goals_against, align: "right" },
            { header: "GD", accessor: (r) => r.goal_difference, align: "right" },
            { header: "Pts", accessor: (r) => r.points, align: "right" },
          ]}
        />
      )}
    </div>
  );
}
