import { Info } from "lucide-react";
import { Link } from "react-router-dom";
import { REPRESENTATION_LIMITATIONS } from "../methodology/content";

/**
 * Prominent limitations note (spec 19.1 and spec 18: limitations must
 * be visible in the product). Lists the six documented representation
 * limitations verbatim.
 */
export function LimitationsNote() {
  return (
    <aside
      aria-label="Known limitations"
      className="rounded-lg border border-warning/30 bg-warning/5 p-5"
    >
      <h2 className="flex items-center gap-2 text-sm font-semibold text-primary">
        <Info aria-hidden="true" className="size-4 text-warning" />
        Read this before acting on any ranking
      </h2>
      <ul className="mt-3 grid list-disc gap-x-8 gap-y-1.5 pl-5 text-xs leading-5 text-secondary sm:grid-cols-2">
        {REPRESENTATION_LIMITATIONS.map((limitation) => (
          <li key={limitation}>{limitation}</li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-secondary">
        Full validation results, bias analysis, and coverage detail are on the{" "}
        <Link to="/methodology" className="font-medium text-accent hover:underline">
          Methodology page
        </Link>
        .
      </p>
    </aside>
  );
}
