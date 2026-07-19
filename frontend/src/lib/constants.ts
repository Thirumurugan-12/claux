/** Persisted theme key. */
export const THEME_STORAGE_KEY = "ksp-theme";

/** How many prior turns of context to send back to the backend. */
export const HISTORY_LIMIT = 12;

/** Network graph SVG rendering bounds and caps. */
export const GRAPH = {
  width: 460,
  height: 380,
  maxNodes: 40,
} as const;

/** Hotspot map SVG bounds and a rough Karnataka bounding box (lon/lat). */
export const MAP = {
  width: 460,
  height: 420,
  maxHotspots: 120,
  bbox: { lon0: 74.0, lon1: 78.6, lat0: 11.5, lat1: 18.6 },
} as const;

/** Cap on CrimeNo chips rendered per provenance card. */
export const MAX_CRIME_CHIPS = 24;
