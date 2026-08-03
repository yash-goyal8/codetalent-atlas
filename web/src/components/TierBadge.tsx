import { CircleHelp, Eye, Target, TrendingUp, type LucideIcon } from "lucide-react";
import type { RecommendationTier } from "../types/rankings";
import { tierLabel } from "../lib/format";
import { Badge, type BadgeProps } from "./ui/badge";

interface TierConfig {
  icon: LucideIcon;
  variant: NonNullable<BadgeProps["variant"]>;
}

const TIER_CONFIG: Record<RecommendationTier, TierConfig> = {
  priority: { icon: Target, variant: "positive" },
  promising: { icon: TrendingUp, variant: "accent" },
  monitor: { icon: Eye, variant: "warning" },
  insufficient_data: { icon: CircleHelp, variant: "neutral" },
};

export interface TierBadgeProps {
  tier: RecommendationTier;
  className?: string;
}

/**
 * Recommendation-tier badge: icon + text label, so tier is never
 * encoded by color alone (spec 19, accessibility).
 */
export function TierBadge({ tier, className }: TierBadgeProps) {
  const { icon: Icon, variant } = TIER_CONFIG[tier];
  return (
    <Badge variant={variant} className={className}>
      <Icon aria-hidden="true" className="size-3" />
      {tierLabel(tier)}
    </Badge>
  );
}
