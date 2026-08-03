// Next.js auto-loads this file on the client before hydration (App Router
// convention: https://nextjs.org/docs/app/guides/instrumentation). This site is a
// static export (`output: "export"` in next.config.ts) with no Node/edge server at
// request time, so the usual @sentry/nextjs wizard's server/edge config files and
// withSentryConfig() wrapper (source-map upload, request tunneling) don't apply --
// they're built for a running Next.js server. Client-side error capture is the
// piece that's actually relevant here, and Sentry.init() alone (no config wrapper)
// is enough for it: it installs global handlers for uncaught exceptions and
// unhandled promise rejections automatically.
import * as Sentry from "@sentry/nextjs";

Sentry.init({
  // Falsy/empty DSN disables the SDK entirely (a documented no-op, not an error) --
  // same "unset locally, real value only when explicitly configured" pattern as
  // NEXT_PUBLIC_API_URL and the backend's SENTRY_DSN.
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  // This project already has dedicated tracing via Application Insights on the
  // backend; Sentry here is scoped to error tracking only, not a second tracing
  // pipeline.
  tracesSampleRate: 0,
});
