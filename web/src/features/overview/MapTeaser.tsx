import { useEffect, useRef, useState } from "react";
import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";
import { Skeleton } from "../../components/Skeleton";
import type { GeographicRankingRow } from "../../types/data";
import { AtlasMap } from "../map/AtlasMap";

const TEASER_HEIGHT = "h-72 lg:h-96";

interface MapTeaserProps {
  rows: GeographicRankingRow[];
}

/**
 * Non-interactive choropleth preview for the Executive overview (spec
 * 19.1 "interactive globe preview"): the country opportunity map with
 * pan/zoom/hover disabled and one overlay link into the Explorer, which
 * holds the fully interactive map plus its accessible table fallback.
 *
 * The map (and the lazy MapLibre chunk behind it) only mounts once the
 * section scrolls near the viewport, so the overview's 3-second
 * interactive budget is unaffected on load.
 */
export function MapTeaser({ rows }: MapTeaserProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    if (typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "300px" },
    );
    observer.observe(host);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={hostRef} className="relative">
      {visible ? (
        <AtlasMap
          rows={rows}
          layer="opportunity"
          level="country"
          selectedGeoId={null}
          onSelect={() => {}}
          interactive={false}
          heightClass={TEASER_HEIGHT}
        />
      ) : (
        <Skeleton className={`w-full ${TEASER_HEIGHT}`} />
      )}
      <Link
        to="/explore"
        aria-label="Open the interactive geographic explorer"
        className="group absolute inset-0 z-20 rounded-lg outline-offset-2 focus-visible:outline-2 focus-visible:outline-accent"
      >
        <span className="absolute right-3 top-3 inline-flex h-8 items-center gap-1.5 rounded-md border border-border bg-surface-1/95 px-3 text-xs font-medium text-primary backdrop-blur transition-colors duration-150 group-hover:border-accent/50 group-hover:text-accent">
          Explore the full map
          <ArrowUpRight aria-hidden="true" className="size-3.5" />
        </span>
      </Link>
    </div>
  );
}
