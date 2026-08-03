import { useEffect, useRef, type ReactNode } from "react";
import { cn } from "../lib/cn";
import type { EChartsInstance, ECOption } from "../lib/echarts";

export interface ChartContainerProps {
  /** Typed ECharts option (spec 20, chart requirements). */
  option: ECOption;
  /** Accessible name for the chart graphic. Required. */
  ariaLabel: string;
  /** Pixel height of the chart canvas. */
  height?: number;
  /**
   * Visually hidden prose summary of what the data shows, for screen
   * readers (spec 19, accessibility). Falls back to `ariaLabel`.
   */
  summary?: string;
  /**
   * Accessible tabular fallback for the visualization, rendered in a
   * disclosure below the chart. Pass a `DataTable` or a plain table.
   */
  tableFallback?: ReactNode;
  className?: string;
}

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/**
 * Lazy ECharts host: the echarts bundle is dynamically imported on first
 * mount so it never enters the main chunk. Handles container resize and
 * disposes the chart on unmount.
 */
export function ChartContainer({
  option,
  ariaLabel,
  height = 320,
  summary,
  tableFallback,
  className,
}: ChartContainerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<EChartsInstance | null>(null);
  const optionRef = useRef(option);
  optionRef.current = option;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    let cancelled = false;
    let observer: ResizeObserver | null = null;

    void import("../lib/echarts").then(({ echarts }) => {
      if (cancelled) return;
      const chart = echarts.init(container, null, { renderer: "canvas" });
      chartRef.current = chart;
      applyOption(chart, optionRef.current);
      if (typeof ResizeObserver !== "undefined") {
        observer = new ResizeObserver(() => {
          chart.resize();
        });
        observer.observe(container);
      }
    });

    return () => {
      cancelled = true;
      observer?.disconnect();
      chartRef.current?.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (chartRef.current) {
      applyOption(chartRef.current, option);
    }
  }, [option]);

  return (
    <figure className={cn("m-0", className)}>
      <div
        ref={containerRef}
        role="img"
        aria-label={ariaLabel}
        style={{ height }}
        className="w-full"
      />
      <figcaption className="sr-only">{summary ?? ariaLabel}</figcaption>
      {tableFallback ? (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs text-secondary hover:text-primary">
            View data as table
          </summary>
          <div className="mt-2">{tableFallback}</div>
        </details>
      ) : null}
    </figure>
  );
}

function applyOption(chart: EChartsInstance, option: ECOption): void {
  const merged: ECOption = prefersReducedMotion()
    ? { ...option, animation: false }
    : option;
  chart.setOption(merged, { notMerge: true });
}
