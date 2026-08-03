// k6 load test against the read-only /analytics/* endpoints.
//
// Deliberately excludes /chat/*, /charts/*, /reports/* -- those call Groq, and
// generating synthetic load against a rate-limited, token-metered LLM endpoint
// would burn real API quota for no useful signal (this is testing the API's own
// serving capacity, not Groq's). /predict/* is skipped too, since it's CPU-bound
// on the container rather than DB-bound like everything tested here.
//
// Usage:
//   BASE_URL=http://localhost:8000 k6 run loadtest/analytics.js   (local)
//   BASE_URL=https://<deployed-api> k6 run loadtest/analytics.js  (real deployment)
// BASE_URL defaults to localhost so a bare `k6 run` never accidentally hits
// production.
import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

// Ramps up, holds, ramps down -- rather than a constant load -- so the results
// show how latency behaves as concurrency changes, not just one data point.
// Deliberately modest (peak 15 virtual users): enough to see real behavior
// (including Container Apps cold start on the deployed API) without generating
// meaningful load against a consumption-tier, pay-per-use resource.
export const options = {
  stages: [
    { duration: "15s", target: 5 },
    { duration: "20s", target: 15 },
    { duration: "15s", target: 15 },
    { duration: "10s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"], // fewer than 1% of requests should fail
    http_req_duration: ["p(95)<1000"], // 95% of requests should complete under 1s
  },
};

// A real player ID and team name from the actual dataset (confirmed live
// earlier this project), so these requests exercise real lookups, not 404s.
const PLAYER_ID = "P00107";
const TEAM_NAME = "Qatar";

export default function () {
  const endpoints = [
    "/analytics/standings",
    "/analytics/progression",
    "/analytics/leaderboard?metric=goals&limit=10",
    `/analytics/players/${PLAYER_ID}`,
    `/analytics/teams/${TEAM_NAME}`,
  ];

  for (const path of endpoints) {
    const res = http.get(`${BASE_URL}${path}`);
    check(res, {
      "status is 200": (r) => r.status === 200,
    });
  }

  sleep(1);
}
