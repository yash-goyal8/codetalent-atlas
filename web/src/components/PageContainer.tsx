import type { ReactNode } from "react";
import { cn } from "../lib/cn";

interface PageContainerProps {
  children: ReactNode;
  className?: string;
}

/** Route content container: max width ~1600px per spec layout rules. */
export function PageContainer({ children, className }: PageContainerProps) {
  return (
    <div
      className={cn(
        "mx-auto w-full max-w-[1600px] space-y-8 px-6 py-10",
        className,
      )}
    >
      {children}
    </div>
  );
}
