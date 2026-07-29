"use client";

import { useState } from "react";
import { predictRating, type RatingPredictionInput } from "@/lib/api";

const DEFAULT_INPUT: RatingPredictionInput = {
  minutes_played: 90,
  goals: 0,
  assists: 0,
  shots: 2,
  shots_on_target: 1,
  expected_goals_xg: 0.3,
  key_passes: 1,
  successful_passes: 30,
  total_passes: 35,
  pass_accuracy: 0.85,
  tackles: 1,
  interceptions: 1,
  position: "Midfielder",
};

const FIELDS: { key: keyof RatingPredictionInput; label: string; step?: number }[] = [
  { key: "minutes_played", label: "Minutes played" },
  { key: "goals", label: "Goals" },
  { key: "assists", label: "Assists" },
  { key: "shots", label: "Shots" },
  { key: "shots_on_target", label: "Shots on target" },
  { key: "expected_goals_xg", label: "xG", step: 0.1 },
  { key: "key_passes", label: "Key passes" },
  { key: "successful_passes", label: "Successful passes" },
  { key: "total_passes", label: "Total passes" },
  { key: "pass_accuracy", label: "Pass accuracy (0-1)", step: 0.01 },
  { key: "tackles", label: "Tackles" },
  { key: "interceptions", label: "Interceptions" },
];

export default function PredictPage() {
  const [input, setInput] = useState<RatingPredictionInput>(DEFAULT_INPUT);
  const [result, setResult] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setLoading(true);
    setError(null);
    try {
      const { predicted_rating } = await predictRating(input);
      setResult(predicted_rating);
    } catch {
      setError("Could not reach the prediction API. Is the backend running with trained models?");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 max-w-xl">
      <div>
        <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
          Rating predictor (what-if)
        </h1>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          Adjust a stat line and see what the model predicts for player rating. Trained on
          genuine box-score actions only (composite/physical columns were excluded as leaky —
          see the architecture doc).
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {FIELDS.map((f) => (
          <label key={f.key} className="flex flex-col gap-1 text-sm" style={{ color: "var(--text-secondary)" }}>
            {f.label}
            <input
              type="number"
              step={f.step ?? 1}
              value={input[f.key] as number}
              onChange={(e) => setInput({ ...input, [f.key]: Number(e.target.value) })}
              className="rounded-md px-2 py-1"
              style={{ background: "var(--surface-1)", border: "1px solid var(--border-hairline)", color: "var(--text-primary)" }}
            />
          </label>
        ))}
        <label className="flex flex-col gap-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Position
          <select
            value={input.position}
            onChange={(e) => setInput({ ...input, position: e.target.value })}
            className="rounded-md px-2 py-1"
            style={{ background: "var(--surface-1)", border: "1px solid var(--border-hairline)", color: "var(--text-primary)" }}
          >
            {["Forward", "Midfielder", "Defender", "Goalkeeper"].map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
      </div>

      <button
        onClick={submit}
        disabled={loading}
        className="self-start rounded-md px-4 py-2 text-sm font-medium"
        style={{ background: "var(--series-1)", color: "white" }}
      >
        {loading ? "Predicting..." : "Predict rating"}
      </button>

      {error && <p style={{ color: "var(--status-critical)" }}>{error}</p>}
      {result !== null && !error && (
        <div
          className="rounded-lg p-4"
          style={{ background: "var(--surface-1)", border: "1px solid var(--border-hairline)" }}
        >
          <span className="text-xs uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
            Predicted rating
          </span>
          <div className="text-3xl font-semibold" style={{ color: "var(--text-primary)" }}>
            {result.toFixed(2)}
          </div>
        </div>
      )}
    </div>
  );
}
