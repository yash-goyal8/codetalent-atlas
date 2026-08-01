import type { ButtonHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

type ButtonVariant = "primary" | "secondary" | "ghost";
type ButtonSize = "sm" | "md";

/*
 * Contrast note: the accent (#6D8BFF) fails WCAG AA against white text,
 * so primary buttons pair the accent fill with near-black text
 * (contrast ~6:1). Token values are unchanged.
 */
const variantClasses: Record<ButtonVariant, string> = {
  primary: "bg-accent text-background font-semibold hover:bg-accent/85",
  secondary:
    "border border-border bg-surface-2 text-primary hover:border-white/20",
  ghost: "text-secondary hover:bg-surface-1 hover:text-primary",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-xs",
  md: "h-10 px-4 text-sm",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export function Button({
  variant = "primary",
  size = "md",
  className,
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50",
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      {...props}
    />
  );
}
