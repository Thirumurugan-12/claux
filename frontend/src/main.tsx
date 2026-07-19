import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

// Fonts bundled offline (docker-friendly, no runtime CDN). Only the weights the design system
// actually uses are imported, to keep the bundle lean:
//   Outfit 600        — the wordmark only
//   Inter 400/500/600 — body + UI
//   JetBrains Mono    — IDs / CrimeNos / metrics
//   Noto Sans Kannada — glyph coverage for Kannada voice/text output
import "@fontsource/outfit/600.css";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";
import "@fontsource/jetbrains-mono/600.css";
import "@fontsource/noto-sans-kannada/400.css";
import "@fontsource/noto-sans-kannada/500.css";

import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
