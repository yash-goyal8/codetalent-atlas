import { Download, Scale } from "lucide-react";
import { EmptyState } from "../components/EmptyState";
import { PageContainer } from "../components/PageContainer";
import { PageHeader } from "../components/PageHeader";
import { Skeleton } from "../components/Skeleton";
import { Card, CardTitle } from "../components/ui/card";
import { useManifest } from "../hooks/useManifest";
import {
  DEFAULT_DOMAIN_ID,
  loadCoverage,
  loadValidation,
  MANIFEST_URL,
} from "../lib/data";
import type { CoverageFile, ValidationFile } from "../types/data";
import { CoverageCharts } from "../features/methodology/CoverageCharts";
import { FormulaCard } from "../features/methodology/FormulaCard";
import { FunnelChart } from "../features/methodology/FunnelChart";
import { PipelineDiagram } from "../features/methodology/PipelineDiagram";
import { ValidationResults } from "../features/methodology/ValidationResults";
import {
  EXCLUSION_RULES,
  INCLUSION_RULES,
  REPRESENTATION_LIMITATIONS,
  SCORE_FORMULAS,
} from "../features/methodology/content";
import { loadSensitivity } from "../features/methodology/sensitivity";
import { DataGate } from "../features/shared/DataGate";
import { Section } from "../features/shared/Section";
import { formatDateTime } from "../features/shared/format";
import { useDataFile } from "../features/shared/useDataFile";

/** Aggregate-data download links (spec 19.6). Static file paths. */
const DOWNLOAD_LINKS = [
  { label: "Dataset manifest", href: MANIFEST_URL },
  {
    label: "Country rankings",
    href: `/data/rankings/${DEFAULT_DOMAIN_ID}/countries.json`,
  },
  {
    label: "City rankings",
    href: `/data/rankings/${DEFAULT_DOMAIN_ID}/cities.json`,
  },
  { label: "Compare dataset", href: `/data/compare/${DEFAULT_DOMAIN_ID}.json` },
] as const;

function FreshnessBlock() {
  const manifest = useManifest();
  if (manifest.kind === "loading") {
    return <Skeleton className="h-16 w-full max-w-xl" />;
  }
  if (manifest.kind === "missing") {
    return (
      <p className="rounded-lg border border-border bg-surface-1 px-4 py-4 text-xs text-secondary">
        Dataset freshness appears here after the first pipeline publish. The
        methodology described on this page is versioned independently of the
        data.
      </p>
    );
  }
  const { datasetVersion, generatedAt, methodologyVersion, window } =
    manifest.manifest;
  return (
    <dl className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <div className="rounded-lg border border-border bg-surface-1 px-4 py-3">
        <dt className="text-xs text-secondary">Dataset version</dt>
        <dd className="score-value mt-1 text-sm font-semibold text-primary">
          {datasetVersion}
        </dd>
      </div>
      <div className="rounded-lg border border-border bg-surface-1 px-4 py-3">
        <dt className="text-xs text-secondary">Generated at</dt>
        <dd className="score-value mt-1 text-sm font-semibold text-primary">
          {formatDateTime(generatedAt)}
        </dd>
      </div>
      <div className="rounded-lg border border-border bg-surface-1 px-4 py-3">
        <dt className="text-xs text-secondary">Data window</dt>
        <dd className="score-value mt-1 text-sm font-semibold text-primary">
          {window.start} to {window.end}
        </dd>
      </div>
      <div className="rounded-lg border border-border bg-surface-1 px-4 py-3">
        <dt className="text-xs text-secondary">Methodology version</dt>
        <dd className="score-value mt-1 text-sm font-semibold text-primary">
          {methodologyVersion}
        </dd>
      </div>
    </dl>
  );
}

/** "Download aggregate data" links, gated on the manifest existing. */
function DownloadBlock() {
  const manifest = useManifest();
  if (manifest.kind === "loading") {
    return <Skeleton className="h-10 w-96 max-w-full" />;
  }
  if (manifest.kind === "missing") {
    return (
      <EmptyState detail="Aggregate downloads become available with the first published dataset." />
    );
  }
  return (
    <ul className="flex list-none flex-wrap gap-3">
      {DOWNLOAD_LINKS.map((link) => (
        <li key={link.href}>
          <a
            href={link.href}
            download
            className="inline-flex h-8 items-center gap-2 rounded-md border border-border bg-surface-2 px-3 text-xs font-medium text-primary transition-colors duration-150 hover:border-white/20"
          >
            <Download aria-hidden="true" className="size-3.5" />
            {link.label}
          </a>
        </li>
      ))}
    </ul>
  );
}

export default function Methodology() {
  const validationState = useDataFile<ValidationFile>(loadValidation);
  const coverageState = useDataFile<CoverageFile>(loadCoverage);
  const sensitivityState = useDataFile(loadSensitivity);

  return (
    <PageContainer>
      <PageHeader
        title="Methodology"
        description="The full recipe behind every score: pipeline, data funnel, inclusion and exclusion rules, exact score formulas, validation results, coverage, limitations, and data freshness. Every displayed ranking can be reconstructed from this page."
      />

      <Section
        title="Pipeline"
        description="Public GitHub activity flows through a deterministic, versioned pipeline — no paid services, no private data."
      >
        <PipelineDiagram />
      </Section>

      <Section
        title="Data funnel"
        description="How many candidates survive each qualification stage of the published dataset."
      >
        <DataGate
          state={validationState}
          skeleton={<Skeleton className="h-40 w-full" />}
          emptyDetail="The funnel renders from methodology/validation.json once the pipeline publishes it."
        >
          {(validation) => (
            <Card>
              <FunnelChart funnel={validation.funnel} />
            </Card>
          )}
        </DataGate>
      </Section>

      <Section
        title="Inclusion and exclusion rules"
        description="Deterministic repository qualification rules — no LLM classification, no manual cherry-picking."
      >
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardTitle>A repository must be</CardTitle>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-xs leading-5 text-secondary">
              {INCLUSION_RULES.map((rule) => (
                <li key={rule}>{rule}</li>
              ))}
            </ul>
          </Card>
          <Card>
            <CardTitle>Excluded</CardTitle>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-xs leading-5 text-secondary">
              {EXCLUSION_RULES.map((rule) => (
                <li key={rule}>{rule}</li>
              ))}
            </ul>
          </Card>
        </div>
      </Section>

      <Section
        title="Score formulas"
        description="The four scores with their exact configured weights. Component weights always sum to 100."
      >
        <div className="grid gap-4 lg:grid-cols-2">
          {SCORE_FORMULAS.map((formula) => (
            <FormulaCard key={formula.id} formula={formula} />
          ))}
        </div>
      </Section>

      <Section title="Opportunity vs confidence: kept separate by design">
        <Card className="flex gap-4">
          <span
            aria-hidden="true"
            className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-full border border-accent/30 bg-accent/10"
          >
            <Scale className="size-4.5 text-accent" />
          </span>
          <p className="max-w-3xl text-sm leading-6 text-secondary">
            Opportunity measures how strong a location's observable expert pool
            looks; confidence measures how much the underlying data can be
            trusted for that location (coverage, location certainty, sample
            size, diversity). The two are never merged into one opaque number,
            and a high-opportunity location with low confidence is never
            labeled a priority recommendation.
          </p>
        </Card>
      </Section>

      <Section
        title="Location coverage"
        description="Coverage bias is measured, not assumed: located-profile share by country and the location-confidence distribution."
      >
        <DataGate
          state={coverageState}
          skeleton={
            <div className="grid gap-6 lg:grid-cols-2">
              <Skeleton className="h-64" />
              <Skeleton className="h-64" />
            </div>
          }
          emptyDetail="Coverage charts render from methodology/coverage.json once the pipeline publishes it."
        >
          {(coverage) => <CoverageCharts coverage={coverage} />}
        </DataGate>
      </Section>

      <Section
        title="Validation results"
        description="Manual-sample precision and automated data-quality checks for the published dataset."
      >
        <DataGate
          state={validationState}
          skeleton={
            <div className="grid gap-4 lg:grid-cols-2">
              <Skeleton className="h-48" />
              <Skeleton className="h-48" />
            </div>
          }
          emptyDetail="Validation results render from methodology/validation.json once the pipeline publishes it."
        >
          {(validation) => <ValidationResults validation={validation} />}
        </DataGate>
      </Section>

      {/* Sensitivity analysis: rendered ONLY when the pipeline has published it. */}
      {sensitivityState.status === "ok" ? (
        <Section
          title="Ranking sensitivity"
          description="How stable the rankings are when top repositories, largest organizations, weights, and windows are varied."
        >
          <Card className="space-y-3">
            {sensitivityState.data.summary ? (
              <p className="max-w-3xl text-sm leading-6 text-secondary">
                {sensitivityState.data.summary}
              </p>
            ) : null}
            {sensitivityState.data.scenarios &&
            sensitivityState.data.scenarios.length > 0 ? (
              <dl className="space-y-2">
                {sensitivityState.data.scenarios.map((scenario) => (
                  <div key={scenario.name} className="text-xs leading-5">
                    <dt className="font-medium text-primary">{scenario.name}</dt>
                    <dd className="text-secondary">{scenario.result}</dd>
                  </div>
                ))}
              </dl>
            ) : null}
          </Card>
        </Section>
      ) : null}

      <Section
        title="Limitations"
        description="What this dataset cannot measure. These apply to every ranking and recommendation in the product."
      >
        <Card>
          <ul className="list-disc space-y-1.5 pl-5 text-sm leading-6 text-primary">
            {REPRESENTATION_LIMITATIONS.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        </Card>
      </Section>

      <Section
        title="Data freshness"
        description="Version and provenance of the dataset currently served by this app."
      >
        <FreshnessBlock />
      </Section>

      <Section
        title="Download aggregate data"
        description="Every published file is aggregate-only JSON — no usernames, no raw locations."
      >
        <DownloadBlock />
      </Section>
    </PageContainer>
  );
}
