import { useMemo, useState, type FormEvent } from "react";
import { Plus } from "lucide-react";
import { PageContainer } from "../components/PageContainer";
import { PageHeader } from "../components/PageHeader";
import { Skeleton } from "../components/Skeleton";
import { Button } from "../components/ui/button";
import { Card, CardTitle } from "../components/ui/card";
import { loadCompare } from "../lib/data";
import { cn } from "../lib/cn";
import { MAX_SELECTED, normalizeSelected, useUrlState } from "../lib/urlstate";
import type { CompareFile, GeographicRankingRow } from "../types/data";
import { LocationColumn } from "../features/compare/LocationColumn";
import { buildComparisonSummary } from "../features/compare/summary";
import { DataGate } from "../features/shared/DataGate";
import { Section } from "../features/shared/Section";
import { useDataFile } from "../features/shared/useDataFile";

/** Accessible picker: native select + add button, fed by compare.json. */
function LocationPicker({
  rows,
  selected,
  onAdd,
}: {
  rows: GeographicRankingRow[];
  selected: string[];
  onAdd: (geoId: string) => void;
}) {
  const [pending, setPending] = useState("");
  const available = rows.filter((row) => !selected.includes(row.geoId));
  const countries = available.filter((row) => row.geoLevel === "country");
  const cities = available.filter((row) => row.geoLevel === "city");
  const full = selected.length >= MAX_SELECTED;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (pending && !full) {
      onAdd(pending);
      setPending("");
    }
  };

  return (
    <form
      onSubmit={submit}
      className="flex flex-wrap items-end gap-3"
      aria-label="Add a location to the comparison"
    >
      <label className="flex flex-col gap-1 text-xs text-secondary">
        Add location ({selected.length}/{MAX_SELECTED})
        <select
          value={pending}
          onChange={(event) => setPending(event.target.value)}
          disabled={full || available.length === 0}
          className="h-8 min-w-56 rounded-md border border-border bg-surface-1 px-2 text-xs text-primary disabled:cursor-not-allowed disabled:opacity-50"
        >
          <option value="">Choose a location…</option>
          {countries.length > 0 ? (
            <optgroup label="Countries">
              {countries.map((row) => (
                <option key={row.geoId} value={row.geoId}>
                  {row.name}
                </option>
              ))}
            </optgroup>
          ) : null}
          {cities.length > 0 ? (
            <optgroup label="Cities">
              {cities.map((row) => (
                <option key={row.geoId} value={row.geoId}>
                  {row.name} ({row.countryCode})
                </option>
              ))}
            </optgroup>
          ) : null}
        </select>
      </label>
      <Button type="submit" variant="secondary" size="sm" disabled={full || pending === ""}>
        <Plus aria-hidden="true" className="size-4" />
        Add
      </Button>
      {full ? (
        <p className="text-xs text-secondary">
          Maximum of {MAX_SELECTED} locations — remove one to add another.
        </p>
      ) : null}
    </form>
  );
}

function CompareContent({ file }: { file: CompareFile }) {
  const [urlState, setUrlState] = useUrlState();
  const selected = urlState.selected;

  const selectedRows = useMemo(() => {
    const byId = new Map(file.rows.map((row) => [row.geoId, row]));
    return selected
      .map((geoId) => byId.get(geoId))
      .filter((row): row is GeographicRankingRow => row !== undefined);
  }, [file.rows, selected]);

  const add = (geoId: string) =>
    setUrlState({ selected: normalizeSelected([...selected, geoId]) });
  const remove = (geoId: string) =>
    setUrlState({ selected: selected.filter((id) => id !== geoId) });

  const summary = buildComparisonSummary(selectedRows);

  return (
    <div className="space-y-8">
      <LocationPicker rows={file.rows} selected={selected} onAdd={add} />

      {selectedRows.length < 2 ? (
        <div
          role="status"
          className="rounded-lg border border-dashed border-white/15 bg-surface-1 px-6 py-14 text-center"
        >
          <p className="text-sm font-medium text-primary">
            Select at least two locations to compare
          </p>
          <p className="mx-auto mt-2 max-w-md text-xs leading-5 text-secondary">
            {selectedRows.length === 1
              ? `${selectedRows[0].name} is selected — add one more location (up to ${MAX_SELECTED}).`
              : `Pick two to ${MAX_SELECTED} ranked locations from the list above, or add them from any location detail page.`}
          </p>
        </div>
      ) : (
        <>
          {/* Small screens show only the first two columns (spec responsive rule). */}
          <p className="text-xs text-secondary md:hidden">
            Small screens compare the first two selections; rotate or widen the
            window for up to four.
          </p>
          <ul
            className="grid list-none gap-4 md:grid-cols-2 xl:grid-cols-4"
            aria-label="Selected locations, side by side"
          >
            {selectedRows.map((row, index) => (
              <li key={row.geoId} className={cn(index >= 2 && "hidden md:block")}>
                <LocationColumn row={row} onRemove={remove} />
              </li>
            ))}
          </ul>

          <Section
            title="Comparison summary"
            description="Assembled from fixed templates over the selected locations' published values — fully reproducible."
          >
            <Card>
              <CardTitle className="sr-only">Factual comparison summary</CardTitle>
              <ul className="list-disc space-y-1.5 pl-5 text-sm leading-6 text-primary">
                {summary.map((sentence) => (
                  <li key={sentence}>{sentence}</li>
                ))}
              </ul>
            </Card>
          </Section>
        </>
      )}
    </div>
  );
}

export default function Compare() {
  const state = useDataFile<CompareFile>(loadCompare);

  return (
    <PageContainer>
      <PageHeader
        title="Compare locations"
        description="Side-by-side comparison of two to four ranked locations: opportunity and confidence, the five score components, expert supply, subdomain strengths, momentum, breadth, and coverage — plus a template-assembled factual summary."
      />
      <DataGate
        state={state}
        skeleton={
          <div className="space-y-4">
            <Skeleton className="h-9 w-72" />
            <div className="grid gap-4 md:grid-cols-2">
              <Skeleton className="h-96" />
              <Skeleton className="h-96" />
            </div>
          </div>
        }
        emptyDetail="Location selection and comparison panels activate once ranked locations exist to choose from."
      >
        {(file) => <CompareContent file={file} />}
      </DataGate>
    </PageContainer>
  );
}
