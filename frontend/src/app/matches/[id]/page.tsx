import { notFound } from "next/navigation";
import { DataTable } from "@/components/DataTable";
import { ScoutingReport } from "@/components/ScoutingReport";
import { getMatch, getMatches } from "@/lib/api";

// Static export (`output: "export"` in next.config.ts) has no server left at request
// time to render a page on demand, so every dynamic route value must be known and
// pre-rendered at build time. This runs once during `next build`, hitting the real
// deployed API's uncapped /analytics/matches list (no separate /ids endpoint needed,
// unlike players -- the list route already returns every match, not a capped top-N).
export async function generateStaticParams() {
  const matches = await getMatches();
  return matches.map((m) => ({ id: m.match_id }));
}

export default async function MatchDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let data;
  try {
    data = await getMatch(id);
  } catch {
    notFound();
  }

  const { match, box_score } = data!;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
          {match.team_a} {match.goals_a}-{match.goals_b} {match.team_b}
        </h1>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          {match.tournament_stage} &middot; {match.stadium}, {match.city} &middot; {match.match_date}
        </p>
      </div>

      <ScoutingReport key={match.match_id} kind="match" id={match.match_id} />

      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
          Box score
        </h3>
        <DataTable
          rows={box_score}
          rowKey={(p) => `${p.team}-${p.player_name}`}
          columns={[
            { header: "Player", accessor: (p) => p.player_name },
            { header: "Team", accessor: (p) => p.team },
            { header: "Goals", accessor: (p) => p.goals, align: "right" },
            { header: "Assists", accessor: (p) => p.assists, align: "right" },
            { header: "Rating", accessor: (p) => p.player_rating?.toFixed(1) ?? "-", align: "right" },
            { header: "YC", accessor: (p) => p.yellow_cards, align: "right" },
            { header: "RC", accessor: (p) => p.red_cards, align: "right" },
          ]}
        />
      </section>
    </div>
  );
}
