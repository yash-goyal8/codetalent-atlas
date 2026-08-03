import { ChartContainer } from "../../components/ChartContainer";
import { DataTable, type DataTableColumn } from "../../components/DataTable";
import type { ECOption } from "../../lib/echarts";
import { formatCount } from "../../lib/format";
import type { ActivityTrendPoint } from "../../types/data";
import {
  baseChartText,
  CHART_COLORS,
  darkCategoryAxis,
  darkValueAxis,
} from "../shared/chartTheme";

const TABLE_COLUMNS: DataTableColumn<ActivityTrendPoint>[] = [
  { key: "month", header: "Month", cell: (p) => p.month, sortValue: (p) => p.month },
  {
    key: "events",
    header: "Weighted events",
    align: "right",
    cell: (p) => formatCount(p.events),
    sortValue: (p) => p.events,
    cellClassName: "score-value",
  },
  {
    key: "contributors",
    header: "Active contributors",
    align: "right",
    cell: (p) => formatCount(p.activeContributors),
    sortValue: (p) => p.activeContributors,
    cellClassName: "score-value",
  },
];

function buildOption(trend: ActivityTrendPoint[]): ECOption {
  return {
    ...baseChartText,
    legend: { top: 0, textStyle: { color: CHART_COLORS.text } },
    grid: { left: 56, right: 56, top: 36, bottom: 32 },
    tooltip: {
      ...baseChartText.tooltip,
      trigger: "axis",
      valueFormatter: (value) =>
        typeof value === "number" ? formatCount(value) : String(value ?? ""),
    },
    xAxis: {
      type: "category",
      name: "Month",
      data: trend.map((p) => p.month),
      ...darkCategoryAxis,
    },
    yAxis: [
      {
        type: "value",
        name: "Events",
        ...darkValueAxis,
      },
      {
        type: "value",
        name: "Contributors",
        splitLine: { show: false },
        axisLine: darkValueAxis.axisLine,
        axisLabel: darkValueAxis.axisLabel,
        nameTextStyle: darkValueAxis.nameTextStyle,
      },
    ],
    series: [
      {
        type: "line",
        name: "Weighted events",
        data: trend.map((p) => p.events),
        itemStyle: { color: CHART_COLORS.accent },
        lineStyle: { color: CHART_COLORS.accent },
        symbol: "circle",
        symbolSize: 7,
      },
      {
        type: "line",
        name: "Active contributors",
        yAxisIndex: 1,
        data: trend.map((p) => p.activeContributors),
        itemStyle: { color: CHART_COLORS.positive },
        lineStyle: { color: CHART_COLORS.positive, type: "dashed" },
        symbol: "diamond",
        symbolSize: 8,
      },
    ],
  };
}

interface ActivityTrendChartProps {
  trend: ActivityTrendPoint[];
  locationName: string;
}

/**
 * Monthly activity trend line chart (spec 19.4 section 3): weighted
 * events and active contributors per month, with a tabular fallback.
 */
export function ActivityTrendChart({ trend, locationName }: ActivityTrendChartProps) {
  return (
    <ChartContainer
      option={buildOption(trend)}
      height={300}
      ariaLabel={`Monthly activity trend for ${locationName}`}
      summary={`Line chart of monthly activity in ${locationName} across ${trend.length} months: weighted event counts (solid line, left axis) and active contributors (dashed line, right axis). The same data is available in the table below.`}
      tableFallback={
        <DataTable
          columns={TABLE_COLUMNS}
          rows={trend}
          rowKey={(p) => p.month}
          caption={`Monthly weighted events and active contributors for ${locationName}`}
          initialSort={{ key: "month", direction: "asc" }}
        />
      }
    />
  );
}
