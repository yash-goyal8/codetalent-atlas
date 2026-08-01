import { Compass } from "lucide-react";
import { Link } from "react-router-dom";
import { PageContainer } from "../components/PageContainer";

export default function NotFound() {
  return (
    <PageContainer className="flex flex-col items-center py-24 text-center">
      <span
        aria-hidden="true"
        className="flex size-14 items-center justify-center rounded-full border border-border bg-surface-1"
      >
        <Compass className="size-7 text-secondary" />
      </span>
      <p className="score-value mt-6 text-5xl font-semibold text-primary">
        404
      </p>
      <h1 className="mt-3 text-xl font-semibold text-primary">
        Page not found
      </h1>
      <p className="mt-2 max-w-md text-sm leading-6 text-secondary">
        This location is off the map. The page you requested does not exist or
        may have moved.
      </p>
      <Link
        to="/"
        className="mt-8 inline-flex h-10 items-center rounded-md bg-accent px-4 text-sm font-semibold text-background transition-colors duration-150 hover:bg-accent/85"
      >
        Back to overview
      </Link>
    </PageContainer>
  );
}
