/**
 * prune-data-strays.mjs — remove macOS/Finder-style duplicate exports
 * ("summary 2.json" alongside "summary.json") from web/public/data so a
 * double pipeline publish can never ship stale duplicate datasets.
 *
 * Runs as part of `prebuild` (before `vite build` copies public/ into
 * dist/). Only deletes a file when BOTH hold:
 *   - the basename matches "<name> <digits>.json"
 *   - the sibling "<name>.json" exists (so the live file is untouched)
 *
 * Usage: node scripts/prune-data-strays.mjs [--check]
 *   --check  exit 1 if strays are found instead of deleting (CI guard)
 */
import { existsSync, readdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const dataDir = join(
  dirname(fileURLToPath(import.meta.url)),
  "..",
  "public",
  "data",
);
const checkOnly = process.argv.includes("--check");

const STRAY_PATTERN = /^(.+) \d+\.json$/;

function findStrays(dir) {
  const strays = [];
  if (!existsSync(dir)) return strays;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      strays.push(...findStrays(full));
      continue;
    }
    const match = STRAY_PATTERN.exec(entry.name);
    if (match && existsSync(join(dir, `${match[1]}.json`))) {
      strays.push(full);
    }
  }
  return strays;
}

const strays = findStrays(dataDir);
if (strays.length === 0) {
  console.log("prune-data-strays: no stray duplicate exports found");
  process.exit(0);
}
for (const stray of strays) {
  if (checkOnly) {
    console.error(`prune-data-strays: stray duplicate export: ${stray}`);
  } else {
    rmSync(stray);
    console.log(`prune-data-strays: removed ${stray}`);
  }
}
process.exit(checkOnly ? 1 : 0);
