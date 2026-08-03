"use client";

// Next.js App Router convention: replaces the root layout when an error escapes
// every error boundary below it. React render errors don't reach the global
// window.onerror handler instrumentation-client.ts's Sentry.init() installs (React
// catches and re-throws them differently) -- this is Sentry's documented hook for
// capturing those specifically, on top of the uncaught-exception/unhandled-rejection
// coverage Sentry.init() already provides for everything else.
import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

export default function GlobalError({
  error,
}: {
  error: Error & { digest?: string };
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang="en">
      <body>
        <div style={{ padding: "2rem", textAlign: "center" }}>
          <h2>Something went wrong.</h2>
        </div>
      </body>
    </html>
  );
}
