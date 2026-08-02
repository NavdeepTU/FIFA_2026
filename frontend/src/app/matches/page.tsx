import Link from "next/link";
import { DataTable } from "@/components/DataTable";
import { getMatches, type MatchRow } from "@/lib/api";

export default async function MatchesPage() {
  let matches: MatchRow[] = [];
  let error: string | null = null;
  try {
    matches = await getMatches();
  } catch {
    error = "Could not reach the API. Is the backend running and DATABASE_URL configured?";
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
          Matches
        </h1>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          Every match in the tournament — open one for the box score and an
          AI-generated recap.
        </p>
      </div>
      {error ? (
        <p style={{ color: "var(--text-secondary)" }}>{error}</p>
      ) : (
        <DataTable
          rows={matches}
          rowKey={(m) => m.match_id}
          columns={[
            { header: "Date", accessor: (m) => m.match_date },
            { header: "Stage", accessor: (m) => m.tournament_stage },
            {
              header: "Match",
              accessor: (m) => (
                <Link href={`/matches/${m.match_id}`} style={{ color: "var(--series-1)" }}>
                  {m.team_a} vs {m.team_b}
                </Link>
              ),
            },
            {
              header: "Score",
              accessor: (m) => `${m.goals_a}-${m.goals_b}`,
              align: "right",
            },
          ]}
        />
      )}
    </div>
  );
}
