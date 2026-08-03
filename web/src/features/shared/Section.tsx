import { useId, type ReactNode } from "react";
import { cn } from "../../lib/cn";

interface SectionProps {
  title: string;
  /** Optional one-line purpose statement under the heading. */
  description?: string;
  /** Optional inline extras next to the heading (badges, links). */
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}

/**
 * Labeled page section: semantic h2 wired via aria-labelledby so every
 * analytical block is a navigable landmark (spec 19, accessibility).
 */
export function Section({
  title,
  description,
  actions,
  children,
  className,
}: SectionProps) {
  const headingId = useId();
  return (
    <section aria-labelledby={headingId} className={cn("space-y-4", className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="space-y-1">
          <h2 id={headingId} className="text-lg font-semibold tracking-tight text-primary">
            {title}
          </h2>
          {description ? (
            <p className="max-w-3xl text-xs leading-5 text-secondary">{description}</p>
          ) : null}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}
