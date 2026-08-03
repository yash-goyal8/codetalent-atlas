/**
 * Auto-generated FACTUAL comparison summary (spec 19.5): sentences are
 * assembled from fixed templates over the selected locations' published
 * numbers. No model calls, no adjectives outside template slots.
 */

import { formatCount, formatScore } from "../../lib/format";
import type { GeographicRankingRow } from "../../types/data";

type Metric = (row: GeographicRankingRow) => number;

/**
 * One leader sentence for a metric:
 * - clear leader, 2 locations:  "X leads on <label> (a vs b)."
 * - clear leader, 3-4 locations: "X leads on <label> (a; next b)."
 * - tie at the top:             "X and Y are tied on <label> (a)."
 * The confidence metric uses "has higher confidence" phrasing.
 */
function leaderSentence(
  rows: GeographicRankingRow[],
  label: string,
  metric: Metric,
  phrasing: "leads" | "higher",
): string {
  const sorted = [...rows].sort((a, b) => metric(b) - metric(a));
  const top = sorted[0];
  const second = sorted[1];
  const topValue = formatScore(metric(top));

  const tied = sorted.filter((row) => metric(row) === metric(top));
  if (tied.length > 1) {
    const names = tied.map((row) => row.name);
    const nameList =
      names.length === 2
        ? `${names[0]} and ${names[1]}`
        : `${names.slice(0, -1).join(", ")}, and ${names[names.length - 1]}`;
    return `${nameList} are tied on ${label} (${topValue}).`;
  }

  const secondValue = formatScore(metric(second));
  const comparison =
    rows.length === 2
      ? `${topValue} vs ${secondValue}`
      : `${topValue}; next ${secondValue}`;
  if (phrasing === "higher") {
    return `${top.name} has higher confidence (${comparison}).`;
  }
  return `${top.name} leads on ${label} (${comparison}).`;
}

/**
 * Build the full factual summary for 2-4 selected locations. Returns an
 * empty array below two locations (nothing to compare).
 */
export function buildComparisonSummary(rows: GeographicRankingRow[]): string[] {
  if (rows.length < 2) {
    return [];
  }

  const sentences = [
    leaderSentence(rows, "opportunity", (r) => r.opportunityScore, "leads"),
    leaderSentence(rows, "confidence", (r) => r.confidenceScore, "higher"),
    leaderSentence(rows, "expert supply", (r) => r.expertSupplyScore, "leads"),
    leaderSentence(rows, "expert quality", (r) => r.expertQualityScore, "leads"),
    `Observable expert pools: ${rows
      .map((row) => `${row.name} ${formatCount(row.observableExpertCount)}`)
      .join(", ")}.`,
  ];

  const provisional = rows.filter((row) => row.momentumProvisional);
  if (provisional.length > 0) {
    sentences.push(
      `Momentum is provisional for ${provisional
        .map((row) => row.name)
        .join(" and ")} (pilot window too short for a full trend).`,
    );
  }

  return sentences;
}
