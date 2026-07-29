"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";

const METRICS = [
  { value: "goals", label: "Goals" },
  { value: "assists", label: "Assists" },
  { value: "avg_player_rating", label: "Avg rating" },
  { value: "tackles", label: "Tackles" },
  { value: "saves", label: "Saves" },
];

export function MetricSelect({ current }: { current: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  return (
    <select
      value={current}
      onChange={(e) => {
        const params = new URLSearchParams(searchParams.toString());
        params.set("metric", e.target.value);
        router.push(`${pathname}?${params.toString()}`);
      }}
      className="text-sm rounded-md px-2 py-1"
      style={{ background: "var(--surface-1)", border: "1px solid var(--border-hairline)", color: "var(--text-primary)" }}
    >
      {METRICS.map((m) => (
        <option key={m.value} value={m.value}>
          {m.label}
        </option>
      ))}
    </select>
  );
}
