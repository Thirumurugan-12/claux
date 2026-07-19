// Inline SVG icon set. Stroke icons inherit currentColor; kept dependency-free and uniform
// (24px grid, 1.6 stroke) so they read as one considered family rather than mixed clip-art.
import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

const stroke = (p: IconProps) => ({
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  ...p,
});

/**
 * Brand mark — a single Kasuti stepped-diamond drawn in line only (currentColor). This is the
 * one place the Karnataka motif appears as a functional glyph; everything else stays neutral.
 */
export function Emblem(p: IconProps) {
  return (
    <svg
      {...p}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinejoin="round"
    >
      <path d="M12 2.5 21.5 12 12 21.5 2.5 12 12 2.5Z" />
      <path d="M12 7.5 16.5 12 12 16.5 7.5 12 12 7.5Z" />
    </svg>
  );
}

export const Sun = (p: IconProps) => (
  <svg {...stroke(p)}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </svg>
);

export const Moon = (p: IconProps) => (
  <svg {...stroke(p)}>
    <path d="M21 12.8A8.5 8.5 0 1 1 11.2 3a6.6 6.6 0 0 0 9.8 9.8z" />
  </svg>
);

export const Send = (p: IconProps) => (
  <svg {...stroke(p)}>
    <path d="M4 12l16-8-6 16-3.5-6.5L4 12z" />
  </svg>
);

export const NetworkIcon = (p: IconProps) => (
  <svg {...stroke(p)}>
    <circle cx="12" cy="5" r="2.2" />
    <circle cx="5" cy="18" r="2.2" />
    <circle cx="19" cy="18" r="2.2" />
    <path d="M11 6.8 6 16M13 6.8 18 16M7 18h10" />
  </svg>
);

export const MapIcon = (p: IconProps) => (
  <svg {...stroke(p)}>
    <path d="M9 4 4 6v14l5-2 6 2 5-2V4l-5 2-6-2z" />
    <path d="M9 4v14M15 6v14" />
  </svg>
);

export const EvidenceIcon = (p: IconProps) => (
  <svg {...stroke(p)}>
    <path d="M9 3h6l1 3H8l1-3z" />
    <path d="M6 6h12v14a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V6z" />
    <path d="M9 11h6M9 15h4" />
  </svg>
);

export const ChatIcon = (p: IconProps) => (
  <svg {...stroke(p)}>
    <path d="M4 5h16v11H9l-4 4V5z" />
    <path d="M8 9h8M8 12h5" />
  </svg>
);

export const Alert = (p: IconProps) => (
  <svg {...stroke(p)}>
    <path d="M12 3l9 16H3l9-16z" />
    <path d="M12 10v4M12 17h.01" />
  </svg>
);

export const Close = (p: IconProps) => (
  <svg {...stroke(p)}>
    <path d="M6 6l12 12M18 6L6 18" />
  </svg>
);
