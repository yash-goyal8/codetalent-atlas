/**
 * Display formatting helpers. Scores render 0-100 with one decimal and
 * must be placed in an element carrying the `score-value` utility class
 * (tabular numerals). Tiers and confidence get text labels so meaning is
 * never carried by color alone (spec 19, accessibility).
 */

import type { RecommendationTier } from "../types/rankings";

/** Em dash placeholder for absent numeric values. */
export const NO_VALUE = "—";

/** Format a 0-100 score with exactly one decimal, e.g. 72.4 -> "72.4". */
export function formatScore(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return NO_VALUE;
  }
  return value.toFixed(1);
}

/**
 * Compact count formatting: 987 -> "987", 12_345 -> "12.3k",
 * 4_500_000 -> "4.5M". Trailing ".0" is trimmed ("2000" -> "2k").
 */
export function formatCount(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return NO_VALUE;
  }
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  const scale = (divisor: number, suffix: string): string => {
    const scaled = abs / divisor;
    const text = scaled >= 100 ? Math.round(scaled).toString() : scaled.toFixed(1);
    return `${sign}${text.replace(/\.0$/, "")}${suffix}`;
  };
  if (abs >= 1e9) return scale(1e9, "B");
  if (abs >= 1e6) return scale(1e6, "M");
  if (abs >= 1e3) return scale(1e3, "k");
  return `${sign}${Math.round(abs)}`;
}

/**
 * Format a 0-1 share as a percentage: 0.62 -> "62%", 0.057 -> "5.7%".
 * One decimal below 10% so small coverage shares stay distinguishable.
 */
export function formatShare(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return NO_VALUE;
  }
  const pct = value * 100;
  const text = Math.abs(pct) < 10 ? pct.toFixed(1).replace(/\.0$/, "") : Math.round(pct).toString();
  return `${text}%`;
}

const MONTH_NAMES = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
] as const;

/**
 * Human label for a trend month key. Accepts the pipeline's compact
 * "YYYYMM" ("202605" -> "May 2026") and the dashed "YYYY-MM"
 * ("2026-05" -> "May 2026"); anything else renders verbatim so bad
 * data degrades to the raw key rather than a wrong date.
 */
export function formatMonth(month: string): string {
  const match = /^(\d{4})-?(\d{2})$/.exec(month.trim());
  if (!match) return month;
  const monthIndex = Number.parseInt(match[2], 10) - 1;
  if (monthIndex < 0 || monthIndex > 11) return month;
  return `${MONTH_NAMES[monthIndex]} ${match[1]}`;
}

const TIER_LABELS: Record<RecommendationTier, string> = {
  priority: "Priority",
  promising: "Promising",
  monitor: "Monitor",
  insufficient_data: "Insufficient data",
};

/** Human label for a recommendation tier. */
export function tierLabel(tier: RecommendationTier): string {
  return TIER_LABELS[tier];
}

/**
 * Text-color utility class per tier. Never the only encoding — always
 * pair with `tierLabel` text or the TierBadge icon.
 */
const TIER_COLOR_CLASSES: Record<RecommendationTier, string> = {
  priority: "text-positive",
  promising: "text-accent",
  monitor: "text-warning",
  insufficient_data: "text-secondary",
};

export function tierColorClass(tier: RecommendationTier): string {
  return TIER_COLOR_CLASSES[tier];
}

export type ConfidenceLevel = "high" | "medium" | "low";

/**
 * Bucket a 0-100 confidence score for labeling. UI thresholds only
 * (>=70 high, >=40 medium) — the underlying score is always shown too.
 */
export function confidenceLevel(score: number): ConfidenceLevel {
  if (score >= 70) return "high";
  if (score >= 40) return "medium";
  return "low";
}

const CONFIDENCE_LABELS: Record<ConfidenceLevel, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
};

/** Human label for a 0-100 confidence score, e.g. 82 -> "High confidence". */
export function confidenceLabel(score: number): string {
  return CONFIDENCE_LABELS[confidenceLevel(score)];
}
