import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export: builds to a plain folder of HTML/CSS/JS (`out/`) with no Node
  // server behind it, so it can be hosted on Azure Blob Storage's static website
  // feature instead of a running container -- appropriate here since this dataset is
  // a fixed synthetic snapshot, not live data that needs per-request server rendering.
  output: "export",
  // Azure's static website hosting has no pretty-URL rewriting (unlike Vercel/Netlify).
  // Without this, Next emits `players/P00001.html`, which won't be found by a direct
  // request to `/players/P00001/`. With it, Next emits `players/P00001/index.html`,
  // matching Azure's index-document convention for any path ending in `/`.
  trailingSlash: true,
};

export default nextConfig;
