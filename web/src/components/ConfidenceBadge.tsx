import { Shield, ShieldAlert, ShieldCheck, type LucideIcon } from "lucide-react";
import {
  confidenceLabel,
  confidenceLevel,
  formatScore,
  type ConfidenceLevel,
} from "../lib/format";
import { Badge, type BadgeProps } from "./ui/badge";

interface LevelConfig {
  icon: LucideIcon;
  variant: NonNullable<BadgeProps["variant"]>;
}

const LEVEL_CONFIG: Record<ConfidenceLevel, LevelConfig> = {
  high: { icon: ShieldCheck, variant: "positive" },
  medium: { icon: Shield, variant: "warning" },
  low: { icon: ShieldAlert, variant: "risk" },
};

export interface ConfidenceBadgeProps {
  /** Confidence score on the 0-100 scale. */
  score: number;
  /** Hide the numeric score when a neighboring cell already shows it. */
  showScore?: boolean;
  className?: string;
}

/**
 * Confidence badge: icon + text label (+ numeric score by default), so
 * confidence is never encoded by color alone (spec 19, accessibility).
 */
export function ConfidenceBadge({
  score,
  showScore = true,
  className,
}: ConfidenceBadgeProps) {
  const { icon: Icon, variant } = LEVEL_CONFIG[confidenceLevel(score)];
  return (
    <Badge variant={variant} className={className}>
      <Icon aria-hidden="true" className="size-3" />
      {confidenceLabel(score)}
      {showScore ? <span className="score-value">{formatScore(score)}</span> : null}
    </Badge>
  );
}
