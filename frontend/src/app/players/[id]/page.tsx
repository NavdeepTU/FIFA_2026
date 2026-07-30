import { notFound } from "next/navigation";
import { DataTable } from "@/components/DataTable";
import { ScoutingReport } from "@/components/ScoutingReport";
import { StatTile } from "@/components/StatTile";
import { getPlayerProfile } from "@/lib/api";

export default async function PlayerProfilePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let data;
  try {
    data = await getPlayerProfile(id);
  } catch {
    notFound();
  }

  const { profile, matches } = data!;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
          {profile.player_name}
        </h1>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          {profile.team} &middot; {profile.position}
        </p>
      </div>

      <section className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatTile label="Matches" value={profile.matches_played} />
        <StatTile label="Goals" value={profile.goals} />
        <StatTile label="Assists" value={profile.assists} />
        <StatTile label="Avg rating" value={profile.avg_player_rating?.toFixed(1)} />
      </section>

      <ScoutingReport key={profile.player_id} kind="player" id={profile.player_id} />

      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
          Match log
        </h3>
        <DataTable
          rows={matches}
          rowKey={(m) => m.match_id}
          columns={[
            { header: "Date", accessor: (m) => m.match_date },
            { header: "Stage", accessor: (m) => m.tournament_stage },
            { header: "Opponent", accessor: (m) => m.opponent_team },
            { header: "Result", accessor: (m) => m.match_result },
            { header: "Mins", accessor: (m) => m.minutes_played, align: "right" },
            { header: "Goals", accessor: (m) => m.goals, align: "right" },
            { header: "Assists", accessor: (m) => m.assists, align: "right" },
            { header: "Rating", accessor: (m) => m.player_rating?.toFixed(1), align: "right" },
          ]}
        />
      </section>
    </div>
  );
}
