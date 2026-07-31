"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { DataTable } from "@/components/DataTable";
import { MetricSelect } from "@/components/MetricSelect";
import { getLeaderboard, type PlayerLeaderboardRow } from "@/lib/api";

// Split out so `key={metric}` (below) forces a real remount when the metric changes
// -- `loading`/`error` reset to their initial useState values for free, the same
// "reset state when a prop changes via remount" pattern ScoutingReport.tsx already
// uses, rather than calling setState synchronously inside the effect.
function Leaderboard({ metric }: { metric: string }) {
  const [rows, setRows] = useState<PlayerLeaderboardRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getLeaderboard(metric, 25)
      .then((data) => {
        if (!cancelled) setRows(data);
      })
      .catch(() => {
        if (!cancelled) setError("Could not reach the API. Is the backend running?");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [metric]);

  if (error) return <p style={{ color: "var(--text-secondary)" }}>{error}</p>;
  if (loading) return <p style={{ color: "var(--text-secondary)" }}>Loading…</p>;

  return (
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
  );
}

// Was a Server Component reading `searchParams` server-side -- incompatible with
// static export, which has no server left at request time to read a query string.
// `useSearchParams()` reads it client-side instead (same approach MetricSelect
// already used to *write* it via router.push), so filtering by metric still works
// as a real, shareable, back/forward-friendly URL, just resolved in the browser.
// Next.js requires any `useSearchParams()` usage to sit inside a Suspense boundary
// so the static shell can render before the client resolves the query string.
function PlayersContent() {
  const searchParams = useSearchParams();
  const metric = searchParams.get("metric") ?? "goals";

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
          Player leaderboard
        </h1>
        <MetricSelect current={metric} />
      </div>

      <Leaderboard key={metric} metric={metric} />
    </div>
  );
}

export default function PlayersPage() {
  return (
    <Suspense fallback={<p style={{ color: "var(--text-secondary)" }}>Loading…</p>}>
      <PlayersContent />
    </Suspense>
  );
}
