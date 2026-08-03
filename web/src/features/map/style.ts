/**
 * Self-contained blank MapLibre style (spec 5.5 / 19.2): a single dark
 * background layer matching the app background token, zero external
 * sources, glyphs, sprites, or tiles. All geography is drawn from the
 * local `web/public/geo/countries.geojson` (public-domain Natural Earth
 * data via the world-atlas package) added as a runtime GeoJSON source.
 */

import type { StyleSpecification } from "maplibre-gl";

/** Matches the `--color-background` token from spec section 19. */
export const MAP_BACKGROUND = "#070a12";

/** Local, pipeline-independent country polygons (built by scripts/build-geo.mjs). */
export const COUNTRIES_GEOJSON_URL = "/geo/countries.geojson";

export const BLANK_MAP_STYLE: StyleSpecification = {
  version: 8,
  name: "atlas-blank",
  sources: {},
  layers: [
    {
      id: "background",
      type: "background",
      paint: { "background-color": MAP_BACKGROUND },
    },
  ],
};
