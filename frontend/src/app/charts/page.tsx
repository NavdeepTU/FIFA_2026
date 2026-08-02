"use client";

import { useState } from "react";
import { askChart, type ChartAskResponse } from "@/lib/api";
import { BarChartCard } from "@/components/charts/BarChartCard";

const EXAMPLE_PROMPTS = [
  "Who scored the most goals?",
  "Show me the league table by points",
  "Which teams kept the most clean sheets?",
  "How did goals per game change through the tournament stages?",
];

export default function ChartsPage() {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ChartAskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const ask = async (question: string) => {
    const query = question.trim();
    if (!query || loading) return;

    setLoading(true);
    setError(null);
    try {
      const response = await askChart(query);
      setResult(response);
    } catch (err) {
      setResult(null);
      // askChart surfaces the backend's real 422 `detail` (e.g. "couldn't match that
      // question to an available chart") rather than a generic failure message.
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-4 max-w-2xl mx-auto">
      <div>
        <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
          Ask for a chart
        </h1>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          Describe what you want to see in plain English. Questions are matched to a
          fixed set of pre-written, allowlisted queries — the model picks a chart, it
          never writes SQL.
        </p>
      </div>

      <div className="flex flex-col gap-2 mt-1">
        <span className="text-xs uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
          Try asking
        </span>
        <div className="flex flex-wrap gap-2">
          {EXAMPLE_PROMPTS.map((p) => (
            <button
              key={p}
              onClick={() => ask(p)}
              disabled={loading}
              className="text-left text-sm rounded-lg px-4 py-2.5 transition-colors disabled:opacity-50"
              style={{
                background: "var(--surface-1)",
                border: "1px solid var(--border-hairline)",
                color: "var(--text-secondary)",
              }}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(input);
        }}
        className="flex gap-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask for a chart..."
          disabled={loading}
          className="flex-1 rounded-full px-4 py-2.5 text-sm outline-none"
          style={{
            background: "var(--surface-1)",
            border: "1px solid var(--border-hairline)",
            color: "var(--text-primary)",
          }}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="rounded-full px-5 py-2.5 text-sm font-medium disabled:opacity-50"
          style={{ background: "var(--series-1)", color: "white" }}
        >
          Ask
        </button>
      </form>

      {loading && (
        <div className="flex items-center gap-1.5 rounded-2xl px-4 py-3 self-start"
          style={{ background: "var(--surface-1)", border: "1px solid var(--border-hairline)" }}
        >
          <Dot delay="0ms" />
          <Dot delay="150ms" />
          <Dot delay="300ms" />
        </div>
      )}

      {error && !loading && (
        <div
          className="rounded-2xl px-4 py-2.5 text-sm"
          style={{
            background: "var(--surface-1)",
            border: "1px solid var(--status-critical)",
            color: "var(--status-critical)",
          }}
        >
          {error}
        </div>
      )}

      {result && !loading && (
        <BarChartCard
          title={result.title}
          // BarChartCard's recharts data expects `string | number`; a null value
          // (a row with no data for that stat, e.g. a keeper who never got a rating)
          // renders as a zero-length bar rather than breaking the chart.
          data={result.data.map((d) => ({ label: d.label, value: d.value ?? 0 }))}
          nameKey="label"
          valueKey="value"
        />
      )}
    </div>
  );
}

function Dot({ delay }: { delay: string }) {
  return (
    <span
      className="w-1.5 h-1.5 rounded-full animate-bounce"
      style={{ background: "var(--text-muted)", animationDelay: delay }}
    />
  );
}
