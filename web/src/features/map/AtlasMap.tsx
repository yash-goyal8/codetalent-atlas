import { useEffect, useId, useMemo, useRef, useState } from "react";
import type {
  GeoJSONSource,
  Map as MapLibreMap,
  MapLayerMouseEvent,
} from "maplibre-gl";
import { Skeleton } from "../../components/Skeleton";
import { cn } from "../../lib/cn";
import {
  confidenceLabel,
  formatCount,
  formatScore,
  NO_VALUE,
} from "../../lib/format";
import type { ScoreLayer } from "../../lib/urlstate";
import type { GeographicRankingRow, GeoLevel } from "../../types/data";
import { MapLegend } from "./MapLegend";
import {
  cityFeatureCollection,
  cityIdFilter,
  countryFillColor,
  countryFillOpacity,
  countryIdFilter,
  countryPointFeatureCollection,
  EMPTY_CITY_COLLECTION,
  isLowConfidence,
  lowConfidenceCountryFilter,
  NO_DATA_FILL,
  NONE_FILTER,
  SCORE_LAYER_LABELS,
  subdomainLabel,
  SUBTLE_BORDER,
  type CityPointCollection,
} from "./scale";
import { BLANK_MAP_STYLE, COUNTRIES_GEOJSON_URL } from "./style";

export interface AtlasMapProps {
  /** Ranking rows for the active geographic level, already filtered. */
  rows: GeographicRankingRow[];
  layer: ScoreLayer;
  level: GeoLevel;
  selectedGeoId: string | null;
  /** Fired with the geoId of a clicked country or city point. */
  onSelect: (geoId: string) => void;
  /**
   * Space-separated element id(s) describing the map for assistive tech
   * — wire this to the ranked DataTable that mirrors the map data.
   */
  describedBy?: string;
  /**
   * false renders a static preview: no pan/zoom/hover/click handlers,
   * no navigation control, no interaction instructions (used by the
   * Overview map teaser, which overlays its own link to the Explorer).
   */
  interactive?: boolean;
  /** Override the default responsive height classes of the map frame. */
  heightClass?: string;
  className?: string;
}

interface TooltipContent {
  x: number;
  y: number;
  placeLeft: boolean;
  placeUp: boolean;
  name: string;
  row: GeographicRankingRow | null;
  clusterCount: number | null;
}

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

function setCitySource(
  map: MapLibreMap,
  collection: CityPointCollection,
): void {
  const source = map.getSource("cities") as GeoJSONSource | undefined;
  source?.setData(
    collection as unknown as Parameters<GeoJSONSource["setData"]>[0],
  );
}

/**
 * Self-contained MapLibre choropleth (spec 19.2): local blank style,
 * local Natural Earth GeoJSON, no keys or tile servers. `maplibre-gl`
 * itself is dynamically imported on first mount so it stays out of the
 * main bundle (spec 20, performance).
 *
 * Confidence is encoded without relying on color alone: low-confidence
 * geographies render faded with a dashed border (countries) or as a
 * hollow ring (cities), and the tooltip always states confidence in
 * text. The ranked table wired via `describedBy` is the accessible
 * fallback for the visualization.
 */
export function AtlasMap({
  rows,
  layer,
  level,
  selectedGeoId,
  onSelect,
  describedBy,
  interactive = true,
  heightClass = "h-[420px] lg:h-[600px]",
  className,
}: AtlasMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [tooltip, setTooltip] = useState<TooltipContent | null>(null);
  const instructionsId = useId();

  const byGeo = useMemo(
    () => new Map(rows.map((row) => [row.geoId, row])),
    [rows],
  );
  const cityCollection = useMemo(
    () => cityFeatureCollection(rows, layer),
    [rows, layer],
  );
  /* Ranked countries with no 110m polygon (SG, HK, MT, …) as points. */
  const microstateCollection = useMemo(
    () => countryPointFeatureCollection(rows, layer),
    [rows, layer],
  );
  const cityCoordsMissing =
    level === "city" && rows.length > 0 && cityCollection.features.length === 0;

  /* Latest props for stable map event handlers (bound once on load). */
  const byGeoRef = useRef(byGeo);
  byGeoRef.current = byGeo;
  const levelRef = useRef(level);
  levelRef.current = level;
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    let cancelled = false;
    let map: MapLibreMap | null = null;

    void Promise.all([
      import("maplibre-gl"),
      import("maplibre-gl/dist/maplibre-gl.css"),
    ])
      .then(([{ default: maplibre }]) => {
        if (cancelled) return;
        const reducedMotion = prefersReducedMotion();
        map = new maplibre.Map({
          container,
          style: BLANK_MAP_STYLE,
          center: [12, 22],
          zoom: 1.1,
          minZoom: 0.6,
          maxZoom: 10,
          attributionControl: false,
          interactive,
          fadeDuration: reducedMotion ? 0 : 300,
        });
        mapRef.current = map;
        if (interactive) {
          map.addControl(
            new maplibre.NavigationControl({ showCompass: false }),
            "top-right",
          );
        }
        map.on("error", (event) => {
          if ((event as { sourceId?: string }).sourceId === "countries") {
            setFailed(true);
          }
        });

        const m = map;
        m.on("load", () => {
          if (cancelled) return;
          m.addSource("countries", {
            type: "geojson",
            data: COUNTRIES_GEOJSON_URL,
          });
          m.addSource("cities", {
            type: "geojson",
            data: EMPTY_CITY_COLLECTION as unknown as Parameters<
              GeoJSONSource["setData"]
            >[0],
            cluster: true,
            clusterMaxZoom: 9,
            clusterRadius: 42,
          });
          /* Ranked countries with no 110m polygon, as point markers. */
          m.addSource("country-points", {
            type: "geojson",
            data: EMPTY_CITY_COLLECTION as unknown as Parameters<
              GeoJSONSource["setData"]
            >[0],
          });

          m.addLayer({
            id: "countries-fill",
            type: "fill",
            source: "countries",
            paint: { "fill-color": NO_DATA_FILL, "fill-opacity": 1 },
          });
          m.addLayer({
            id: "countries-border",
            type: "line",
            source: "countries",
            paint: { "line-color": SUBTLE_BORDER, "line-width": 0.4 },
          });
          /* Dashed border on low-confidence countries: the non-color
             confidence encoding, paired with reduced fill opacity. */
          m.addLayer({
            id: "countries-lowconf",
            type: "line",
            source: "countries",
            filter: NONE_FILTER,
            paint: {
              "line-color": "rgba(244, 247, 251, 0.55)",
              "line-width": 1.1,
              "line-dasharray": [1.6, 1.4],
            },
          });
          m.addLayer({
            id: "countries-hover",
            type: "line",
            source: "countries",
            filter: NONE_FILTER,
            paint: {
              "line-color": "rgba(244, 247, 251, 0.7)",
              "line-width": 1.4,
            },
          });
          m.addLayer({
            id: "countries-selected",
            type: "line",
            source: "countries",
            filter: NONE_FILTER,
            paint: { "line-color": "#b2c7ff", "line-width": 2 },
          });

          m.addLayer({
            id: "country-points",
            type: "circle",
            source: "country-points",
            paint: {
              "circle-color": ["get", "color"],
              "circle-radius": ["get", "radius"],
              "circle-opacity": ["get", "fillOpacity"],
              "circle-stroke-color": "rgba(244, 247, 251, 0.4)",
              "circle-stroke-width": ["get", "strokeWidth"],
            },
          });
          m.addLayer({
            id: "country-points-selected",
            type: "circle",
            source: "country-points",
            filter: cityIdFilter(null),
            paint: {
              "circle-color": "rgba(0, 0, 0, 0)",
              "circle-radius": ["+", ["get", "radius"], 3],
              "circle-stroke-color": "#b2c7ff",
              "circle-stroke-width": 2,
            },
          });

          m.addLayer({
            id: "cities-clusters",
            type: "circle",
            source: "cities",
            filter: ["has", "point_count"],
            paint: {
              "circle-color": "#4459a2",
              "circle-opacity": 0.8,
              "circle-radius": [
                "interpolate",
                ["linear"],
                ["get", "point_count"],
                2,
                12,
                50,
                24,
              ],
              "circle-stroke-color": "rgba(244, 247, 251, 0.3)",
              "circle-stroke-width": 1,
            },
          });
          m.addLayer({
            id: "cities-points",
            type: "circle",
            source: "cities",
            filter: ["!", ["has", "point_count"]],
            paint: {
              "circle-color": ["get", "color"],
              "circle-radius": ["get", "radius"],
              "circle-opacity": ["get", "fillOpacity"],
              "circle-stroke-color": "rgba(244, 247, 251, 0.4)",
              "circle-stroke-width": ["get", "strokeWidth"],
            },
          });
          m.addLayer({
            id: "cities-selected",
            type: "circle",
            source: "cities",
            filter: cityIdFilter(null),
            paint: {
              "circle-color": "rgba(0, 0, 0, 0)",
              "circle-radius": ["+", ["get", "radius"], 3],
              "circle-stroke-color": "#b2c7ff",
              "circle-stroke-width": 2,
            },
          });

          if (!interactive) {
            setReady(true);
            return;
          }

          const placeTooltip = (
            e: MapLayerMouseEvent,
            content: Pick<TooltipContent, "name" | "row" | "clusterCount">,
          ) => {
            const host = m.getContainer();
            setTooltip({
              x: e.point.x,
              y: e.point.y,
              placeLeft: e.point.x > host.clientWidth - 280,
              placeUp: e.point.y > host.clientHeight - 200,
              ...content,
            });
          };

          m.on("mousemove", "countries-fill", (e) => {
            if (levelRef.current !== "country") return;
            const feature = e.features?.[0];
            if (feature?.id == null) return;
            const geoId = String(feature.id);
            const row = byGeoRef.current.get(geoId) ?? null;
            m.setFilter("countries-hover", countryIdFilter(geoId));
            m.getCanvas().style.cursor = row ? "pointer" : "";
            placeTooltip(e, {
              name:
                (feature.properties as { name?: string } | null)?.name ?? geoId,
              row,
              clusterCount: null,
            });
          });
          m.on("mouseleave", "countries-fill", () => {
            m.setFilter("countries-hover", NONE_FILTER);
            m.getCanvas().style.cursor = "";
            setTooltip(null);
          });
          m.on("click", "countries-fill", (e) => {
            if (levelRef.current !== "country") return;
            const feature = e.features?.[0];
            if (feature?.id == null) return;
            const geoId = String(feature.id);
            if (byGeoRef.current.has(geoId)) {
              onSelectRef.current(geoId);
            }
          });

          /* Polygon-less ranked countries (point markers). */
          m.on("mousemove", "country-points", (e) => {
            if (levelRef.current !== "country") return;
            const properties = e.features?.[0]?.properties as
              | { geoId?: string; name?: string }
              | undefined;
            if (!properties?.geoId) return;
            const row = byGeoRef.current.get(properties.geoId) ?? null;
            m.getCanvas().style.cursor = row ? "pointer" : "";
            placeTooltip(e, {
              name: properties.name ?? properties.geoId,
              row,
              clusterCount: null,
            });
          });
          m.on("mouseleave", "country-points", () => {
            m.getCanvas().style.cursor = "";
            setTooltip(null);
          });
          m.on("click", "country-points", (e) => {
            if (levelRef.current !== "country") return;
            const properties = e.features?.[0]?.properties as
              | { geoId?: string }
              | undefined;
            if (properties?.geoId && byGeoRef.current.has(properties.geoId)) {
              onSelectRef.current(properties.geoId);
            }
          });

          m.on("mousemove", "cities-points", (e) => {
            if (levelRef.current !== "city") return;
            const properties = e.features?.[0]?.properties as
              | { geoId?: string; name?: string }
              | undefined;
            if (!properties?.geoId) return;
            const row = byGeoRef.current.get(properties.geoId) ?? null;
            m.getCanvas().style.cursor = row ? "pointer" : "";
            placeTooltip(e, {
              name: properties.name ?? properties.geoId,
              row,
              clusterCount: null,
            });
          });
          m.on("mouseleave", "cities-points", () => {
            m.getCanvas().style.cursor = "";
            setTooltip(null);
          });
          m.on("click", "cities-points", (e) => {
            if (levelRef.current !== "city") return;
            const properties = e.features?.[0]?.properties as
              | { geoId?: string }
              | undefined;
            if (properties?.geoId && byGeoRef.current.has(properties.geoId)) {
              onSelectRef.current(properties.geoId);
            }
          });

          m.on("mousemove", "cities-clusters", (e) => {
            const properties = e.features?.[0]?.properties as
              | { point_count?: number }
              | undefined;
            if (properties?.point_count == null) return;
            m.getCanvas().style.cursor = "pointer";
            placeTooltip(e, {
              name: "Cluster",
              row: null,
              clusterCount: properties.point_count,
            });
          });
          m.on("mouseleave", "cities-clusters", () => {
            m.getCanvas().style.cursor = "";
            setTooltip(null);
          });
          m.on("click", "cities-clusters", (e) => {
            const feature = e.features?.[0];
            const clusterId = (
              feature?.properties as { cluster_id?: number } | undefined
            )?.cluster_id;
            const source = m.getSource("cities") as GeoJSONSource | undefined;
            if (
              clusterId == null ||
              !source ||
              feature?.geometry.type !== "Point"
            ) {
              return;
            }
            const center = feature.geometry.coordinates as [number, number];
            void Promise.resolve(source.getClusterExpansionZoom(clusterId))
              .then((zoom) => {
                m.easeTo({
                  center,
                  zoom,
                  duration: reducedMotion ? 0 : 400,
                });
              })
              .catch(() => {
                /* cluster no longer on screen — ignore */
              });
          });

          setReady(true);
        });
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });

    return () => {
      cancelled = true;
      mapRef.current = null;
      setReady(false);
      map?.remove();
    };
  }, [interactive]);

  /* Accessible name + description on the MapLibre canvas. */
  useEffect(() => {
    if (!ready) return;
    const canvas = mapRef.current?.getCanvas();
    if (!canvas) return;
    canvas.setAttribute(
      "aria-label",
      `Interactive world map of ${SCORE_LAYER_LABELS[layer]} scores`,
    );
    canvas.setAttribute(
      "aria-describedby",
      describedBy ? `${instructionsId} ${describedBy}` : instructionsId,
    );
  }, [ready, layer, describedBy, instructionsId]);

  /* Re-style when rows, score layer, or geographic level change. */
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const countryPointsSource = map.getSource("country-points") as
      | GeoJSONSource
      | undefined;
    if (level === "country") {
      map.setPaintProperty(
        "countries-fill",
        "fill-color",
        countryFillColor(rows, layer),
      );
      map.setPaintProperty(
        "countries-fill",
        "fill-opacity",
        countryFillOpacity(rows),
      );
      map.setFilter("countries-lowconf", lowConfidenceCountryFilter(rows));
      setCitySource(map, EMPTY_CITY_COLLECTION);
      countryPointsSource?.setData(
        microstateCollection as unknown as Parameters<
          GeoJSONSource["setData"]
        >[0],
      );
    } else {
      map.setPaintProperty("countries-fill", "fill-color", NO_DATA_FILL);
      map.setPaintProperty("countries-fill", "fill-opacity", 1);
      map.setFilter("countries-lowconf", NONE_FILTER);
      setCitySource(map, cityCollection);
      countryPointsSource?.setData(
        EMPTY_CITY_COLLECTION as unknown as Parameters<
          GeoJSONSource["setData"]
        >[0],
      );
    }
    map.setFilter("countries-hover", NONE_FILTER);
  }, [ready, rows, layer, level, cityCollection, microstateCollection]);

  /* Selection outline. */
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    map.setFilter(
      "countries-selected",
      level === "country" ? countryIdFilter(selectedGeoId) : NONE_FILTER,
    );
    map.setFilter(
      "country-points-selected",
      cityIdFilter(level === "country" ? selectedGeoId : null),
    );
    map.setFilter(
      "cities-selected",
      cityIdFilter(level === "city" ? selectedGeoId : null),
    );
  }, [ready, selectedGeoId, level]);

  return (
    <div className={cn("min-w-0", className)}>
      <div
        className={cn(
          "relative w-full overflow-hidden rounded-lg border border-border bg-background",
          heightClass,
        )}
      >
        <div ref={containerRef} className="absolute inset-0" />

        {!ready && !failed ? (
          <div
            role="status"
            aria-label="Loading map"
            className="absolute inset-0 z-10"
          >
            <Skeleton className="size-full rounded-none" />
          </div>
        ) : null}

        {failed ? (
          <div
            role="alert"
            className="absolute inset-0 z-10 flex items-center justify-center bg-background/85 p-6 text-center"
          >
            <div className="max-w-sm space-y-2">
              <p className="text-sm font-medium text-primary">
                Map failed to load
              </p>
              <p className="text-xs leading-5 text-secondary">
                The map library or the local country boundaries could not be
                loaded. The ranked table alongside contains the same data.
              </p>
            </div>
          </div>
        ) : null}

        {!failed && cityCoordsMissing ? (
          <div
            role="status"
            className="absolute inset-x-0 top-3 z-10 mx-auto w-fit max-w-[90%] rounded-md border border-border bg-surface-1/95 px-4 py-2 text-center text-xs leading-5 text-secondary backdrop-blur"
          >
            <span className="font-medium text-primary">
              City map unavailable:
            </span>{" "}
            this dataset does not include city centroid coordinates yet. City
            rankings remain fully available in the ranked table.
          </div>
        ) : null}

        <MapLegend
          layer={layer}
          level={level}
          hasMicrostates={
            level === "country" && microstateCollection.features.length > 0
          }
          className="absolute bottom-3 left-3 z-10"
        />

        {tooltip ? (
          <div
            aria-hidden="true"
            className="pointer-events-none absolute z-20 w-max max-w-64 rounded-md border border-border bg-surface-1/95 px-3 py-2 text-xs leading-5 shadow-lg backdrop-blur"
            style={{
              left: tooltip.x,
              top: tooltip.y,
              transform: `translate(${
                tooltip.placeLeft ? "calc(-100% - 12px)" : "12px"
              }, ${tooltip.placeUp ? "calc(-100% - 12px)" : "12px"})`,
            }}
          >
            {tooltip.clusterCount !== null ? (
              <p className="text-primary">
                <span className="score-value font-medium">
                  {tooltip.clusterCount}
                </span>{" "}
                cities — click to zoom in
              </p>
            ) : tooltip.row ? (
              <>
                <p className="font-medium text-primary">{tooltip.name}</p>
                <div className="mt-1 space-y-0.5 text-secondary">
                  <p>
                    Rank{" "}
                    <span className="score-value text-primary">
                      #{tooltip.row.rank}
                    </span>
                  </p>
                  <p>
                    Opportunity{" "}
                    <span className="score-value text-primary">
                      {formatScore(tooltip.row.opportunityScore)}
                    </span>
                  </p>
                  <p>
                    Confidence{" "}
                    <span className="score-value text-primary">
                      {formatScore(tooltip.row.confidenceScore)}
                    </span>{" "}
                    — {confidenceLabel(tooltip.row.confidenceScore)}
                  </p>
                  <p>
                    Observable experts{" "}
                    <span className="score-value text-primary">
                      {formatCount(tooltip.row.observableExpertCount)}
                    </span>
                  </p>
                  <p>
                    Top subdomain{" "}
                    <span className="text-primary">
                      {tooltip.row.topSubdomains[0]
                        ? subdomainLabel(tooltip.row.topSubdomains[0])
                        : NO_VALUE}
                    </span>
                  </p>
                  {tooltip.row.momentumProvisional ? (
                    <p className="text-warning">
                      Momentum provisional (incomplete window)
                    </p>
                  ) : null}
                  {isLowConfidence(tooltip.row) ? (
                    <p className="text-warning">
                      Shown faded with a dashed border on the map
                    </p>
                  ) : null}
                </div>
              </>
            ) : (
              <>
                <p className="font-medium text-primary">{tooltip.name}</p>
                <p className="mt-1 text-secondary">
                  No data in the current view — unranked or filtered out.
                </p>
              </>
            )}
          </div>
        ) : null}
      </div>

      {interactive ? (
        <p id={instructionsId} className="mt-2 text-xs leading-5 text-secondary">
          Focus the map and use the arrow keys to pan, plus and minus to zoom.
          Hover a location for details; click to select it, click again to
          open its detail page. The ranked table alongside is the accessible
          text alternative with the same data.
        </p>
      ) : (
        <p id={instructionsId} className="sr-only">
          Static map preview — open the Explorer for the interactive version
          with a full accessible table alternative.
        </p>
      )}
      <p className="mt-1 text-xs leading-4 text-secondary/80">
        Basemap: Natural Earth country boundaries (public domain), rendered
        locally — no external tile services or API keys.
      </p>
    </div>
  );
}
