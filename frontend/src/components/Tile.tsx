import type { ReactNode } from "react";

interface TileProps {
  /** Small-caps header label. Ignored when `head` is provided. */
  title?: ReactNode;
  /** Header-right slot (controls / meta). Ignored when `head` is provided. */
  actions?: ReactNode;
  /** Custom header node that replaces the default title row entirely (e.g. a tab strip). */
  head?: ReactNode;
  /** Grid-placement / variant class applied to the tile element. */
  className?: string;
  /** Class applied to the body wrapper — use `tile-flow` for flex columns, `tile-pad` for padded. */
  bodyClassName?: string;
  ariaLabel?: string;
  children: ReactNode;
}

/**
 * A bento tile: a bordered, softly-elevated surface with a clear header and a body slot.
 * The single reusable unit the whole dashboard is composed from, so radii, hairlines, and
 * depth stay consistent across the chat, session, and analysis tiles.
 */
export function Tile({
  title,
  actions,
  head,
  className = "",
  bodyClassName = "",
  ariaLabel,
  children,
}: TileProps) {
  const hasDefaultHead = title != null || actions != null;
  return (
    <section className={`tile ${className}`.trim()} aria-label={ariaLabel}>
      {head
        ? head
        : hasDefaultHead && (
            <header className="tile-head">
              {title != null && <span className="tile-title">{title}</span>}
              {actions != null && <div className="tile-actions">{actions}</div>}
            </header>
          )}
      <div className={`tile-body ${bodyClassName}`.trim()}>{children}</div>
    </section>
  );
}
