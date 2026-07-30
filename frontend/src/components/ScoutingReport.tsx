"use client";

import { useEffect, useState } from "react";
import { generatePlayerReport, generateTeamReport, getPlayerReport, getTeamReport } from "@/lib/api";

type ReportData = { report_text: string; generated_at: string };

const FETCHERS: Record<"player" | "team", (id: string) => Promise<ReportData | null>> = {
  player: getPlayerReport,
  team: getTeamReport,
};

const GENERATORS: Record<"player" | "team", (id: string) => Promise<ReportData>> = {
  player: generatePlayerReport,
  team: generateTeamReport,
};

export function ScoutingReport({ kind, id }: { kind: "player" | "team"; id: string }) {
  const [report, setReport] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    FETCHERS[kind](id)
      .then((r) => {
        if (!cancelled) setReport(r);
      })
      .catch(() => {
        if (!cancelled) setError("Could not check for an existing report.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [kind, id]);

  const generate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const r = await GENERATORS[kind](id);
      setReport(r);
    } catch {
      setError("Could not generate a report right now. Is the backend running with a Groq API key set?");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
          Scouting report
        </h3>
        {!loading && (
          <button
            onClick={generate}
            disabled={generating}
            className="text-xs rounded-full px-3 py-1.5 font-medium disabled:opacity-50"
            style={{ background: "var(--series-1)", color: "white" }}
          >
            {generating ? "Generating..." : report ? "Regenerate" : "Generate report"}
          </button>
        )}
      </div>

      {loading && (
        <div
          className="rounded-lg p-4 text-sm"
          style={{ background: "var(--surface-1)", border: "1px solid var(--border-hairline)", color: "var(--text-muted)" }}
        >
          Checking for an existing report...
        </div>
      )}

      {!loading && error && (
        <p className="text-sm" style={{ color: "var(--status-critical)" }}>
          {error}
        </p>
      )}

      {!loading && !error && !report && (
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          No report yet — generate one from this {kind}&apos;s real stats and recent matches.
        </p>
      )}

      {!loading && report && (
        <div
          className="rounded-lg p-4 flex flex-col gap-2"
          style={{ background: "var(--surface-1)", border: "1px solid var(--border-hairline)" }}
        >
          <p className="text-sm whitespace-pre-wrap" style={{ color: "var(--text-primary)" }}>
            {report.report_text}
          </p>
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            Generated {new Date(report.generated_at).toLocaleString()}
          </span>
        </div>
      )}
    </section>
  );
}
