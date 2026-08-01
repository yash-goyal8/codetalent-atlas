import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  description: string;
  children?: ReactNode;
}

/** Consistent route heading block: h1 plus a short purpose statement. */
export function PageHeader({ title, description, children }: PageHeaderProps) {
  return (
    <header className="max-w-3xl space-y-3">
      <h1 className="text-2xl font-semibold tracking-tight text-primary">
        {title}
      </h1>
      <p className="text-sm leading-6 text-secondary">{description}</p>
      {children}
    </header>
  );
}
