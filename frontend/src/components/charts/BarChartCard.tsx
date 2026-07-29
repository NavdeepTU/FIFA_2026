"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Datum = Record<string, string | number>;

export function BarChartCard({
  title,
  data,
  nameKey,
  valueKey,
  color = "var(--series-1)",
  height = 320,
}: {
  title: string;
  data: Datum[];
  nameKey: string;
  valueKey: string;
  color?: string;
  height?: number;
}) {
  return (
    <div
      className="rounded-lg p-4"
      style={{ background: "var(--surface-1)", border: "1px solid var(--border-hairline)" }}
    >
      <h3 className="text-sm font-medium mb-3" style={{ color: "var(--text-secondary)" }}>
        {title}
      </h3>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
          <CartesianGrid horizontal={false} stroke="var(--gridline)" />
          <XAxis type="number" tick={{ fill: "var(--text-muted)", fontSize: 12 }} stroke="var(--axis)" />
          <YAxis
            type="category"
            dataKey={nameKey}
            width={110}
            tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
            stroke="var(--axis)"
          />
          <Tooltip
            cursor={{ fill: "var(--gridline)", opacity: 0.4 }}
            contentStyle={{
              background: "var(--surface-1)",
              border: "1px solid var(--border-hairline)",
              borderRadius: 6,
              color: "var(--text-primary)",
              fontSize: 12,
            }}
          />
          <Bar dataKey={valueKey} fill={color} radius={[0, 4, 4, 0]} maxBarSize={22} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
