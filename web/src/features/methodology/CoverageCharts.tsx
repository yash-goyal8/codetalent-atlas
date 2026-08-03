import { ChartContainer } from "../../components/ChartContainer";
import { DataTable, type DataTableColumn } from "../../components/DataTable";
import type { ECOption } from "../../lib/echarts";
import { formatCount, formatShare } from "../../lib/format";
import type { ConfidenceBucket, CountryCoverage, CoverageFile } from "../../types/data";
import {
  baseChartText,
  CHART_COLORS,
  darkCategoryAxis,
  darkValueAxis,
} from "../shared/chartTheme";

const COUNTRY_COLUMNS: DataTableColumn<CountryCoverage>[] = [
  { key: "name", header: "Country", cell: (c) => c.name, sortValue: (c) => c.name },
  {
    key: "share",
    header: "Located share",
    align: "right",
    cell: (c) => formatShare(c.share),
    sortValue: (c) => c.share,
    cellClassName: "score-value",
  },
  {
    key: "experts",
    header: "Observable experts",
    align: "right",
    cell: (c) => formatCount(c.expertCount),
    sortValue: (c) => c.expertCount,
    cellClassName: "score-value",
  },
];

function coverageOption(rows: CountryCoverage[]): ECOption {
  const sorted = [...rows].sort((a, b) => a.share - b.share);
  return {
    ...baseChartText,
    grid: { left: 140, right: 48, top: 8, bottom: 32 },
    tooltip: {
      ...baseChartText.tooltip,
      trigger: "item",
      formatter: (params: unknown) => {
        const p = params as { dataIndex?: number };
        const entry = sorted[p.dataIndex ?? -1];
        if (!entry) return "";
        return `<strong>${entry.name}</strong><br/>${formatShare(entry.share)} of ${formatCount(entry.expertCount)} observable experts have a normalized location`;
      },
    },
    xAxis: {
      type: "value",
      name: "Located-profile share",
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
      data: sorted.map((c) => c.name),
      ...darkCategoryAxis,
    },
    series: [
      {
        type: "bar",
        name: "Located-profile share",
        data: sorted.map((c) => c.share),
        itemStyle: { color: CHART_COLORS.accent, borderRadius: [0, 3, 3, 0] },
        barMaxWidth: 18,
      },
    ],
  };
}

function distributionOption(buckets: ConfidenceBucket[]): ECOption {
  return {
    ...baseChartText,
    grid: { left: 64, right: 24, top: 16, bottom: 48 },
    tooltip: {
      ...baseChartText.tooltip,
      trigger: "item",
      valueFormatter: (value) =>
        typeof value === "number" ? `${formatCount(value)} profiles` : String(value ?? ""),
    },
    xAxis: {
      type: "category",
      name: "Location confidence level",
      nameLocation: "middle",
      nameGap: 30,
      data: buckets.map((b) => b.level),
      ...darkCategoryAxis,
    },
    yAxis: {
      type: "value",
      name: "Profiles",
      ...darkValueAxis,
    },
    series: [
      {
        type: "bar",
        name: "Profiles",
        data: buckets.map((b) => b.count),
        itemStyle: { color: CHART_COLORS.positive, borderRadius: [3, 3, 0, 0] },
        barMaxWidth: 56,
        label: {
          show: true,
          position: "top",
          color: CHART_COLORS.text,
          formatter: (params: unknown) => {
            const p = params as { dataIndex?: number };
            const bucket = buckets[p.dataIndex ?? -1];
            return bucket ? formatCount(bucket.count) : "";
          },
        },
      },
    ],
  };
}

/**
 * Location-coverage charts (spec 19.6) from methodology/coverage.json:
 * located-profile share by country and the location-confidence
 * distribution, each with a tabular fallback.
 */
export function CoverageCharts({ coverage }: { coverage: CoverageFile }) {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <ChartContainer
        option={coverageOption(coverage.locatedShareByCountry)}
        height={Math.max(220, 34 * coverage.locatedShareByCountry.length + 60)}
        ariaLabel="Located-profile share by country"
        summary={`Horizontal bar chart of located-profile coverage for ${coverage.locatedShareByCountry.length} countries: the share of each country's observable experts with a usable normalized location. The same data is available in the table below.`}
        tableFallback={
          <DataTable
            columns={COUNTRY_COLUMNS}
            rows={coverage.locatedShareByCountry}
            rowKey={(c) => c.countryCode}
            caption="Located-profile share and observable expert count by country"
            initialSort={{ key: "share", direction: "desc" }}
          />
        }
      />
      <ChartContainer
        option={distributionOption(coverage.confidenceDistribution)}
        height={280}
        ariaLabel="Location-confidence distribution"
        summary={`Bar chart of location-normalization confidence: ${coverage.confidenceDistribution
          .map((b) => `${b.count} profiles at ${b.level} confidence`)
          .join(", ")}. Levels are labeled on the axis, never encoded by color alone.`}
        tableFallback={
          <table className="w-full border-collapse text-sm">
            <caption className="sr-only">
              Profile counts by location-confidence level
            </caption>
            <thead>
              <tr>
                <th scope="col" className="border-b border-border px-3 py-2 text-left text-xs font-medium text-secondary">
                  Confidence level
                </th>
                <th scope="col" className="border-b border-border px-3 py-2 text-right text-xs font-medium text-secondary">
                  Profiles
                </th>
              </tr>
            </thead>
            <tbody>
              {coverage.confidenceDistribution.map((bucket) => (
                <tr key={bucket.level}>
                  <td className="border-b border-border px-3 py-2 text-primary last:border-b-0">
                    {bucket.level}
                  </td>
                  <td className="score-value border-b border-border px-3 py-2 text-right text-primary">
                    {formatCount(bucket.count)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        }
      />
    </div>
  );
}
