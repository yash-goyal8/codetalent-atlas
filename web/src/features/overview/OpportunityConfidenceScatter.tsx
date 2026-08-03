import { ChartContainer } from "../../components/ChartContainer";
import { DataTable, type DataTableColumn } from "../../components/DataTable";
import type { ECOption } from "../../lib/echarts";
import { formatScore, tierLabel } from "../../lib/format";
import type { GeographicRankingRow, RecommendationTier } from "../../types/data";
import {
  baseChartText,
  CHART_COLORS,
  darkValueAxis,
} from "../shared/chartTheme";

/**
 * Tier thresholds from the scoring configuration (spec section 17):
 * priority requires opportunity >= 75 and confidence >= 70. Rendered as
 * quadrant guides so the priority quadrant is visible at a glance.
 */
export const OPPORTUNITY_THRESHOLD = 75;
export const CONFIDENCE_THRESHOLD = 70;

/** Tier encoded by symbol shape AND color — never color alone (spec 19). */
const TIER_STYLE: Record<RecommendationTier, { symbol: string; color: string }> = {
  priority: { symbol: "diamond", color: CHART_COLORS.positive },
  promising: { symbol: "circle", color: CHART_COLORS.accent },
  monitor: { symbol: "triangle", color: CHART_COLORS.warning },
  insufficient_data: { symbol: "rect", color: CHART_COLORS.neutral },
};

const TIER_ORDER: RecommendationTier[] = [
  "priority",
  "promising",
  "monitor",
  "insufficient_data",
];

interface ScatterPoint {
  name: string;
  value: [number, number];
  row: GeographicRankingRow;
}

function buildOption(rows: GeographicRankingRow[]): ECOption {
  const series = TIER_ORDER.filter((tier) =>
    rows.some((row) => row.recommendationTier === tier),
  ).map((tier) => {
    const style = TIER_STYLE[tier];
    const data: ScatterPoint[] = rows
      .filter((row) => row.recommendationTier === tier)
      .map((row) => ({
        name: row.countryCode,
        value: [row.confidenceScore, row.opportunityScore],
        row,
      }));
    return {
      type: "scatter" as const,
      name: tierLabel(tier),
      symbol: style.symbol,
      symbolSize: 14,
      itemStyle: { color: style.color },
      label: {
        show: true,
        position: "top" as const,
        formatter: "{b}",
        color: CHART_COLORS.text,
        fontSize: 12,
      },
      data,
    };
  });

  // Quadrant guides at the configured tier thresholds, on the first series.
  if (series.length > 0) {
    Object.assign(series[0], {
      markLine: {
        silent: true,
        symbol: "none",
        lineStyle: { color: CHART_COLORS.axisLine, type: "dashed" as const },
        label: { color: CHART_COLORS.text, fontSize: 12 },
        data: [
          {
            xAxis: CONFIDENCE_THRESHOLD,
            label: { formatter: `Confidence ${CONFIDENCE_THRESHOLD}` },
          },
          {
            yAxis: OPPORTUNITY_THRESHOLD,
            label: { formatter: `Opportunity ${OPPORTUNITY_THRESHOLD}` },
          },
        ],
      },
    });
  }

  return {
    ...baseChartText,
    legend: {
      top: 0,
      textStyle: { color: CHART_COLORS.text },
      icon: "roundRect",
    },
    grid: { left: 48, right: 24, top: 40, bottom: 40 },
    xAxis: {
      type: "value",
      name: "Confidence score (0-100)",
      nameLocation: "middle",
      nameGap: 28,
      min: 0,
      max: 100,
      ...darkValueAxis,
    },
    yAxis: {
      type: "value",
      name: "Opportunity score (0-100)",
      nameLocation: "middle",
      nameGap: 34,
      min: 0,
      max: 100,
      ...darkValueAxis,
    },
    tooltip: {
      ...baseChartText.tooltip,
      trigger: "item",
      formatter: (params: unknown) => {
        const p = params as { data?: ScatterPoint };
        const row = p.data?.row;
        if (!row) return "";
        return [
          `<strong>${row.name}</strong> (${row.countryCode})`,
          `Opportunity: ${formatScore(row.opportunityScore)} / 100`,
          `Confidence: ${formatScore(row.confidenceScore)} / 100`,
          `Tier: ${tierLabel(row.recommendationTier)}`,
          `Scores are 0-100 — see Methodology.`,
        ].join("<br/>");
      },
    },
    series,
  };
}

const TABLE_COLUMNS: DataTableColumn<GeographicRankingRow>[] = [
  {
    key: "rank",
    header: "Rank",
    align: "right",
    cell: (row) => row.rank,
    sortValue: (row) => row.rank,
    cellClassName: "score-value",
  },
  { key: "name", header: "Location", cell: (row) => row.name, sortValue: (row) => row.name },
  { key: "code", header: "Code", cell: (row) => row.countryCode },
  {
    key: "opportunity",
    header: "Opportunity",
    align: "right",
    cell: (row) => formatScore(row.opportunityScore),
    sortValue: (row) => row.opportunityScore,
    cellClassName: "score-value",
  },
  {
    key: "confidence",
    header: "Confidence",
    align: "right",
    cell: (row) => formatScore(row.confidenceScore),
    sortValue: (row) => row.confidenceScore,
    cellClassName: "score-value",
  },
  {
    key: "tier",
    header: "Tier",
    cell: (row) => tierLabel(row.recommendationTier),
    sortValue: (row) => tierLabel(row.recommendationTier),
  },
];

interface OpportunityConfidenceScatterProps {
  rows: GeographicRankingRow[];
}

/**
 * Opportunity-vs-confidence scatterplot (spec 19.1): x = confidence,
 * y = opportunity, points labeled by country code, tier encoded by
 * symbol shape and color, quadrant guides at the tier thresholds.
 * Includes an accessible tabular fallback.
 */
export function OpportunityConfidenceScatter({
  rows,
}: OpportunityConfidenceScatterProps) {
  return (
    <ChartContainer
      option={buildOption(rows)}
      height={380}
      ariaLabel="Opportunity versus confidence scatterplot of ranked countries"
      summary={`Scatterplot of ${rows.length} ranked locations. Horizontal axis: confidence score 0-100; vertical axis: opportunity score 0-100. Dashed guides mark the priority-tier thresholds at confidence ${CONFIDENCE_THRESHOLD} and opportunity ${OPPORTUNITY_THRESHOLD}. Recommendation tier is encoded by both symbol shape and color. The same data is available in the table below.`}
      tableFallback={
        <DataTable
          columns={TABLE_COLUMNS}
          rows={rows}
          rowKey={(row) => row.geoId}
          caption="Ranked locations with opportunity score, confidence score, and recommendation tier"
          initialSort={{ key: "rank", direction: "asc" }}
        />
      }
    />
  );
}
