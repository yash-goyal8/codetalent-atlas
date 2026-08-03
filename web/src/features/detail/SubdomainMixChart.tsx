import { ChartContainer } from "../../components/ChartContainer";
import { DataTable, type DataTableColumn } from "../../components/DataTable";
import type { ECOption } from "../../lib/echarts";
import { formatCount, formatShare } from "../../lib/format";
import type { SubdomainMixEntry } from "../../types/data";
import {
  baseChartText,
  CHART_COLORS,
  darkCategoryAxis,
  darkValueAxis,
} from "../shared/chartTheme";

const TABLE_COLUMNS: DataTableColumn<SubdomainMixEntry>[] = [
  {
    key: "subdomain",
    header: "Subdomain",
    cell: (e) => e.displayName,
    sortValue: (e) => e.displayName,
  },
  {
    key: "experts",
    header: "Observable experts",
    align: "right",
    cell: (e) => formatCount(e.expertCount),
    sortValue: (e) => e.expertCount,
    cellClassName: "score-value",
  },
  {
    key: "share",
    header: "Share",
    align: "right",
    cell: (e) => formatShare(e.share),
    sortValue: (e) => e.share,
    cellClassName: "score-value",
  },
];

function buildOption(mix: SubdomainMixEntry[]): ECOption {
  // Largest share at the top of the horizontal bar chart.
  const sorted = [...mix].sort((a, b) => a.share - b.share);
  return {
    ...baseChartText,
    grid: { left: 180, right: 48, top: 8, bottom: 32 },
    tooltip: {
      ...baseChartText.tooltip,
      trigger: "item",
      formatter: (params: unknown) => {
        const p = params as { name?: string; dataIndex?: number };
        const entry = sorted[p.dataIndex ?? -1];
        if (!entry) return "";
        return `<strong>${entry.displayName}</strong><br/>${formatCount(entry.expertCount)} observable experts (${formatShare(entry.share)} of the location's experts)`;
      },
    },
    xAxis: {
      type: "value",
      name: "Share of experts",
      nameLocation: "middle",
      nameGap: 26,
      min: 0,
      max: 1,
      axisLabel: {
        ...darkValueAxis.axisLabel,
        formatter: (value: number) => formatShare(value),
      },
      axisLine: darkValueAxis.axisLine,
      splitLine: darkValueAxis.splitLine,
      nameTextStyle: darkValueAxis.nameTextStyle,
    },
    yAxis: {
      type: "category",
      data: sorted.map((e) => e.displayName),
      ...darkCategoryAxis,
    },
    series: [
      {
        type: "bar",
        name: "Share of experts",
        data: sorted.map((e) => e.share),
        itemStyle: { color: CHART_COLORS.accent, borderRadius: [0, 3, 3, 0] },
        barMaxWidth: 22,
        label: {
          show: true,
          position: "right",
          color: CHART_COLORS.text,
          formatter: (params: unknown) => {
            const p = params as { dataIndex?: number };
            const entry = sorted[p.dataIndex ?? -1];
            return entry ? formatShare(entry.share) : "";
          },
        },
      },
    ],
  };
}

interface SubdomainMixChartProps {
  mix: SubdomainMixEntry[];
  locationName: string;
}

/**
 * Subdomain mix horizontal bars (spec 19.4 section 4) with an
 * accessible tabular fallback.
 */
export function SubdomainMixChart({ mix, locationName }: SubdomainMixChartProps) {
  return (
    <ChartContainer
      option={buildOption(mix)}
      height={Math.max(180, 48 * mix.length + 60)}
      ariaLabel={`Subdomain mix for ${locationName}`}
      summary={`Horizontal bar chart of ${mix.length} Cloud/DevOps subdomains in ${locationName}, each bar showing the share of the location's observable experts active in that subdomain. The same data is available in the table below.`}
      tableFallback={
        <DataTable
          columns={TABLE_COLUMNS}
          rows={mix}
          rowKey={(e) => e.subdomainId}
          caption={`Subdomain expert counts and shares for ${locationName}`}
          initialSort={{ key: "share", direction: "desc" }}
        />
      }
    />
  );
}
