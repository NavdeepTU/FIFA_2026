import Link from "next/link";
import { notFound } from "next/navigation";
import { DataTable } from "@/components/DataTable";
import { ScoutingReport } from "@/components/ScoutingReport";
import { StatTile } from "@/components/StatTile";
import { getTeamProfile } from "@/lib/api";

export default async function TeamProfilePage({
  params,
}: {
  params: Promise<{ team: string }>;
}) {
  const { team } = await params;

  let data;
  try {
    data = await getTeamProfile(team);
  } catch {
    notFound();
  }

  const { standing, roster } = data!;

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
        {standing.team}
      </h1>

      <section className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatTile label="Points" value={standing.points} />
        <StatTile label="Record" value={`${standing.wins}-${standing.draws}-${standing.losses}`} sublabel="W-D-L" />
        <StatTile label="Goals for" value={standing.goals_for} />
        <StatTile label="Goal difference" value={standing.goal_difference} />
      </section>

      <ScoutingReport kind="team" id={standing.team} />

      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
          Roster (by avg rating)
        </h3>
        <DataTable
          rows={roster}
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
            { header: "Pos", accessor: (r) => r.position },
            { header: "MP", accessor: (r) => r.matches_played, align: "right" },
            { header: "Goals", accessor: (r) => r.goals, align: "right" },
            { header: "Assists", accessor: (r) => r.assists, align: "right" },
            { header: "Rating", accessor: (r) => r.avg_player_rating?.toFixed(1), align: "right" },
          ]}
        />
      </section>
    </div>
  );
}
