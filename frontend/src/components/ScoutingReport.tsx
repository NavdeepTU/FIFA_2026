"use client";

import { useEffect, useState } from "react";
import {
  generateMatchReport,
  generatePlayerReport,
  generateTeamReport,
  getMatchReport,
  getPlayerReport,
  getTeamReport,
} from "@/lib/api";

type ReportData = { report_text: string; generated_at: string };
type ReportKind = "player" | "team" | "match";

const FETCHERS: Record<ReportKind, (id: string) => Promise<ReportData | null>> = {
  player: getPlayerReport,
  team: getTeamReport,
  match: getMatchReport,
};

const GENERATORS: Record<ReportKind, (id: string) => Promise<ReportData>> = {
  player: generatePlayerReport,
  team: generateTeamReport,
  match: generateMatchReport,
};

const LABELS: Record<ReportKind, string> = {
  player: "Scouting report",
  team: "Scouting report",
  match: "Match recap",
};

const EMPTY_STATE_COPY: Record<ReportKind, string> = {
  player: "No report yet — generate one from this player's real stats and recent matches.",
  team: "No report yet — generate one from this team's real stats and recent matches.",
  match: "No recap yet — generate one from this match's real box score.",
};

export function ScoutingReport({ kind, id }: { kind: ReportKind; id: string }) {
  const [report, setReport] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    // No setLoading(true) here -- `loading` already starts true, and the parent
    // passes key={id} so a change in id/kind remounts this component fresh rather
    // than reusing state across entities (React's recommended pattern for "reset
    // state when a prop changes" -- see https://react.dev/learn/you-might-not-need-an-effect).
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
          {LABELS[kind]}
        </h3>
        {!loading && (
          <button
            onClick={generate}
            disabled={generating}
            className="text-xs rounded-full px-3 py-1.5 font-medium disabled:opacity-50"
            style={{ background: "var(--series-1)", color: "white" }}
          >
            {generating ? "Generating..." : report ? "Regenerate" : "Generate"}
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
          {EMPTY_STATE_COPY[kind]}
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
