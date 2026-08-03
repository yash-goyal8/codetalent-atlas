/**
 * Static centroids for territories absent from the 1:110m Natural Earth
 * polygon set (world-atlas countries-110m omits microstates and small
 * islands by design). Ranked countries in this table render as point
 * markers on the country choropleth instead of silently disappearing —
 * the spec 21 "all map geo IDs resolve" expectation.
 *
 * Coordinates are approximate geographic centroids ([longitude,
 * latitude], 2-decimal precision — display anchors, not findings).
 * A unit test asserts this table never overlaps the polygon ids in
 * public/geo/countries.geojson.
 */

/** ISO alpha-2 -> [longitude, latitude] for polygon-less territories. */
export const MICROSTATE_CENTROIDS: Readonly<Record<string, [number, number]>> =
  {
    AD: [1.52, 42.51], // Andorra
    AG: [-61.8, 17.08], // Antigua and Barbuda
    AW: [-69.97, 12.52], // Aruba
    BB: [-59.54, 13.19], // Barbados
    BH: [50.55, 26.03], // Bahrain
    BM: [-64.75, 32.31], // Bermuda
    CV: [-23.63, 15.11], // Cabo Verde
    CW: [-68.99, 12.2], // Curaçao
    DM: [-61.37, 15.42], // Dominica
    FO: [-6.91, 61.89], // Faroe Islands
    GD: [-61.68, 12.11], // Grenada
    GG: [-2.58, 49.46], // Guernsey
    GI: [-5.35, 36.14], // Gibraltar
    GU: [144.79, 13.44], // Guam
    HK: [114.17, 22.32], // Hong Kong
    IM: [-4.55, 54.24], // Isle of Man
    JE: [-2.13, 49.21], // Jersey
    KM: [43.87, -11.65], // Comoros
    KN: [-62.75, 17.34], // Saint Kitts and Nevis
    KY: [-81.25, 19.31], // Cayman Islands
    LC: [-60.98, 13.91], // Saint Lucia
    LI: [9.55, 47.16], // Liechtenstein
    MC: [7.42, 43.74], // Monaco
    MO: [113.55, 22.19], // Macao
    MT: [14.45, 35.9], // Malta
    MU: [57.55, -20.28], // Mauritius
    MV: [73.4, 3.2], // Maldives
    SC: [55.49, -4.68], // Seychelles
    SG: [103.82, 1.35], // Singapore
    SH: [-5.72, -15.95], // Saint Helena
    SM: [12.46, 43.94], // San Marino
    ST: [6.72, 0.33], // São Tomé and Príncipe
    VA: [12.45, 41.9], // Vatican City
    VC: [-61.19, 13.25], // Saint Vincent and the Grenadines
    VI: [-64.9, 18.34], // U.S. Virgin Islands
    WS: [-172.1, -13.76], // Samoa
  };

/** Centroid for a country geoId with no polygon, or null. */
export function microstateCentroid(geoId: string): [number, number] | null {
  return MICROSTATE_CENTROIDS[geoId.toUpperCase()] ?? null;
}
