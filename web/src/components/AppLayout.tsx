import { ChevronDown, Globe2 } from "lucide-react";
import { Suspense } from "react";
import { NavLink, Outlet, Link } from "react-router-dom";
import { useManifest } from "../hooks/useManifest";
import { cn } from "../lib/cn";

const navItems = [
  { to: "/", label: "Overview", end: true },
  { to: "/explore", label: "Explorer" },
  { to: "/compare", label: "Compare" },
  { to: "/methodology", label: "Methodology" },
  { to: "/recommendations", label: "Recommendations" },
  { to: "/about", label: "About" },
] as const;

function RouteFallback() {
  return (
    <div
      role="status"
      aria-label="Loading page"
      className="mx-auto w-full max-w-[1600px] px-6 py-10"
    >
      <div className="h-8 w-64 animate-pulse rounded-md bg-surface-2" />
      <div className="mt-4 h-4 w-96 max-w-full animate-pulse rounded-md bg-surface-1" />
    </div>
  );
}

/**
 * Shared application shell: skip link, sticky header with domain
 * selector and primary navigation, main landmark, and dataset footer.
 */
export function AppLayout() {
  const manifest = useManifest();

  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-accent focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-background"
      >
        Skip to content
      </a>

      <header className="sticky top-0 z-40 border-b border-border bg-background/85 backdrop-blur">
        <div className="mx-auto flex min-h-14 w-full max-w-[1600px] flex-wrap items-center gap-x-6 gap-y-1 px-6 py-2">
          <Link
            to="/"
            className="flex items-center gap-2 whitespace-nowrap text-sm font-semibold tracking-tight text-primary"
          >
            <Globe2 aria-hidden="true" className="size-5 text-accent" />
            CodeTalent Atlas
          </Link>

          {/* Single pilot domain; selector activates once expansion domains ship (Milestone F+). */}
          <button
            type="button"
            disabled
            title="Cloud and DevOps is the only pilot domain"
            className="inline-flex h-8 cursor-not-allowed items-center gap-2 whitespace-nowrap rounded-md border border-border bg-surface-1 px-3 text-xs font-medium text-secondary"
          >
            <span className="text-secondary/70">Domain</span>
            Cloud and DevOps
            <ChevronDown aria-hidden="true" className="size-3.5 opacity-50" />
          </button>

          <nav aria-label="Primary" className="ml-auto">
            <ul className="flex items-center gap-1">
              {navItems.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={"end" in item && item.end}
                    className={({ isActive }) =>
                      cn(
                        "rounded-md px-3 py-2 text-xs font-medium transition-colors duration-150",
                        isActive
                          ? "bg-surface-2 text-primary"
                          : "text-secondary hover:bg-surface-1 hover:text-primary",
                      )
                    }
                  >
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </header>

      <main id="main" tabIndex={-1} className="flex-1 outline-none">
        <Suspense fallback={<RouteFallback />}>
          <Outlet />
        </Suspense>
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto flex w-full max-w-[1600px] flex-wrap items-center justify-between gap-3 px-6 py-4 text-xs text-secondary">
          <p>
            Aggregate-only geographic intelligence from public GitHub activity.
            No individual developer data is published.
          </p>
          <p className="flex items-center gap-4">
            <span>
              {manifest.kind === "ok"
                ? `Dataset: ${manifest.manifest.datasetVersion}`
                : "Dataset: pending first pipeline run"}
            </span>
            <span aria-hidden="true" className="text-border">
              |
            </span>
            <span>
              {manifest.kind === "ok"
                ? `Methodology v${manifest.manifest.methodologyVersion}`
                : "Methodology v1.0.0"}
            </span>
          </p>
        </div>
      </footer>
    </div>
  );
}
