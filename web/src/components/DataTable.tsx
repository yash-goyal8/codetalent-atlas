import { useMemo, useState, type ReactNode } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { cn } from "../lib/cn";

export type SortDirection = "asc" | "desc";

export interface DataTableColumn<T> {
  /** Stable column id, used for sort state. */
  key: string;
  header: string;
  align?: "left" | "right";
  /** Cell renderer. */
  cell: (row: T) => ReactNode;
  /** Enables sorting; returns the comparable value for a row. */
  sortValue?: (row: T) => number | string;
  /** Extra classes for body cells (e.g. `score-value`). */
  cellClassName?: string;
}

export interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  /** Accessible description of the table (visually hidden caption). */
  caption: string;
  /** Initial sort; column must have `sortValue`. */
  initialSort?: { key: string; direction: SortDirection };
  /** Constrain height and scroll vertically; header stays sticky. */
  maxHeight?: number;
  className?: string;
}

function compareValues(a: number | string, b: number | string): number {
  if (typeof a === "number" && typeof b === "number") {
    return a - b;
  }
  return String(a).localeCompare(String(b));
}

/**
 * Semantic, sortable data table with a sticky header row and horizontal
 * overflow scrolling. Sorting is exposed through real buttons in column
 * headers with `aria-sort` on the active column (spec 19, accessibility).
 */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  caption,
  initialSort,
  maxHeight,
  className,
}: DataTableProps<T>) {
  const [sort, setSort] = useState<{ key: string; direction: SortDirection } | null>(
    initialSort ?? null,
  );

  const sortedRows = useMemo(() => {
    if (!sort) return rows;
    const column = columns.find((c) => c.key === sort.key);
    const sortValue = column?.sortValue;
    if (!sortValue) return rows;
    const factor = sort.direction === "asc" ? 1 : -1;
    return [...rows].sort(
      (a, b) => factor * compareValues(sortValue(a), sortValue(b)),
    );
  }, [rows, columns, sort]);

  const toggleSort = (key: string) => {
    setSort((current) => {
      // First click sorts descending (top scores first), second ascending.
      if (!current || current.key !== key) {
        return { key, direction: "desc" };
      }
      return { key, direction: current.direction === "desc" ? "asc" : "desc" };
    });
  };

  return (
    <div
      className={cn(
        "overflow-x-auto rounded-lg border border-border",
        maxHeight !== undefined && "overflow-y-auto",
        className,
      )}
      style={maxHeight !== undefined ? { maxHeight } : undefined}
    >
      <table className="w-full min-w-max border-collapse text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            {columns.map((column) => {
              const isSorted = sort?.key === column.key;
              const ariaSort = isSorted
                ? sort.direction === "asc"
                  ? "ascending"
                  : "descending"
                : undefined;
              const SortIcon = isSorted
                ? sort.direction === "asc"
                  ? ArrowUp
                  : ArrowDown
                : ArrowUpDown;
              return (
                <th
                  key={column.key}
                  scope="col"
                  aria-sort={ariaSort}
                  className={cn(
                    "sticky top-0 z-10 border-b border-border bg-surface-1 px-3 py-2 text-xs font-medium text-secondary",
                    column.align === "right" ? "text-right" : "text-left",
                  )}
                >
                  {column.sortValue ? (
                    <button
                      type="button"
                      onClick={() => toggleSort(column.key)}
                      className={cn(
                        "inline-flex items-center gap-1 rounded-sm hover:text-primary",
                        isSorted && "text-primary",
                      )}
                    >
                      {column.header}
                      <SortIcon
                        aria-hidden="true"
                        className={cn("size-3", !isSorted && "opacity-50")}
                      />
                    </button>
                  ) : (
                    column.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sortedRows.map((row) => (
            <tr
              key={rowKey(row)}
              className="border-b border-border last:border-b-0 hover:bg-surface-2/60"
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={cn(
                    "px-3 py-2 text-primary",
                    column.align === "right" ? "text-right" : "text-left",
                    column.cellClassName,
                  )}
                >
                  {column.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
