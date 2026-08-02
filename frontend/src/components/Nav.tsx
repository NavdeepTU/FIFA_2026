import Link from "next/link";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/players", label: "Players" },
  { href: "/teams", label: "Teams" },
  { href: "/predict", label: "Predictor" },
  { href: "/chat", label: "Ask" },
  { href: "/charts", label: "Charts" },
];

export function Nav() {
  return (
    <header style={{ borderBottom: "1px solid var(--border-hairline)" }}>
      <nav className="max-w-5xl mx-auto flex items-center gap-6 px-4 py-3">
        <span className="font-semibold" style={{ color: "var(--text-primary)" }}>
          FIFA World Cup 2026 Analytics
        </span>
        <div className="flex gap-4">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} className="text-sm" style={{ color: "var(--text-secondary)" }}>
              {l.label}
            </Link>
          ))}
        </div>
      </nav>
    </header>
  );
}
