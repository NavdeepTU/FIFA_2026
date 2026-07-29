export function StatTile({ label, value, sublabel }: { label: string; value: string | number; sublabel?: string }) {
  return (
    <div
      className="rounded-lg p-4 flex flex-col gap-1"
      style={{ background: "var(--surface-1)", border: "1px solid var(--border-hairline)" }}
    >
      <span className="text-xs uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
        {label}
      </span>
      <span className="text-3xl font-semibold" style={{ color: "var(--text-primary)", fontVariantNumeric: "proportional-nums" }}>
        {value}
      </span>
      {sublabel && (
        <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
          {sublabel}
        </span>
      )}
    </div>
  );
}
