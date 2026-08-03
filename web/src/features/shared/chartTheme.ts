/**
 * Shared ECharts styling fragments for the dark theme tokens
 * (spec section 19 visual system). Pure option fragments — no runtime
 * echarts import, so this stays out of the lazy chart chunk decision.
 */

export const CHART_COLORS = {
  background: "transparent",
  text: "#9BA8BC",
  textStrong: "#F4F7FB",
  axisLine: "rgba(255,255,255,0.15)",
  splitLine: "rgba(255,255,255,0.07)",
  accent: "#6D8BFF",
  positive: "#36C98F",
  warning: "#F2B84B",
  risk: "#F06B7A",
  neutral: "#9BA8BC",
  tooltipBg: "#121A2B",
  tooltipBorder: "rgba(255,255,255,0.12)",
} as const;

/** Base text/tooltip styling merged into every chart option. */
export const baseChartText = {
  textStyle: { color: CHART_COLORS.text, fontFamily: "inherit" },
  tooltip: {
    backgroundColor: CHART_COLORS.tooltipBg,
    borderColor: CHART_COLORS.tooltipBorder,
    textStyle: { color: CHART_COLORS.textStrong, fontSize: 12 },
  },
} as const;

/** Standard value-axis styling on the dark surface. */
export const darkValueAxis = {
  axisLine: { lineStyle: { color: CHART_COLORS.axisLine } },
  axisLabel: { color: CHART_COLORS.text },
  splitLine: { lineStyle: { color: CHART_COLORS.splitLine } },
  nameTextStyle: { color: CHART_COLORS.text },
} as const;

/** Standard category-axis styling on the dark surface. */
export const darkCategoryAxis = {
  axisLine: { lineStyle: { color: CHART_COLORS.axisLine } },
  axisLabel: { color: CHART_COLORS.text },
  axisTick: { show: false },
  nameTextStyle: { color: CHART_COLORS.text },
} as const;
