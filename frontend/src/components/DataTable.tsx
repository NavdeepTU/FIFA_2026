type Column<T> = {
  header: string;
  accessor: (row: T) => React.ReactNode;
  align?: "left" | "right";
};

export function DataTable<T>({ columns, rows, rowKey }: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
}) {
  return (
    <div className="overflow-x-auto rounded-lg" style={{ border: "1px solid var(--border-hairline)" }}>
      <table className="w-full text-sm" style={{ borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--gridline)" }}>
            {columns.map((col) => (
              <th
                key={col.header}
                className="px-3 py-2 font-medium text-xs uppercase tracking-wide"
                style={{
                  color: "var(--text-muted)",
                  textAlign: col.align ?? "left",
                  background: "var(--surface-1)",
                }}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)} style={{ borderBottom: "1px solid var(--gridline)" }}>
              {columns.map((col) => (
                <td
                  key={col.header}
                  className="px-3 py-2"
                  style={{
                    color: "var(--text-primary)",
                    textAlign: col.align ?? "left",
                    fontVariantNumeric: col.align === "right" ? "tabular-nums" : undefined,
                  }}
                >
                  {col.accessor(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
