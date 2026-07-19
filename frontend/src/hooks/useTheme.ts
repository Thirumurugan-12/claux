import { useCallback, useEffect, useState } from "react";
import { THEME_STORAGE_KEY } from "../lib/constants";

export type Theme = "dark" | "light";

function readTheme(): Theme {
  try {
    const t = localStorage.getItem(THEME_STORAGE_KEY);
    if (t === "light" || t === "dark") return t;
  } catch {
    // localStorage unavailable (private mode / SSR) — fall through to the default.
  }
  return "dark";
}

/** Theme state synced to <html data-theme> and localStorage. Dark is the default. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(readTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // Ignore persistence failures; the in-memory theme still applies.
    }
  }, [theme]);

  const toggle = useCallback(() => setTheme((t) => (t === "dark" ? "light" : "dark")), []);

  return { theme, toggle };
}
