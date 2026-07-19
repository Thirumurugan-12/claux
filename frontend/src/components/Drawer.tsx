import { useEffect } from "react";
import type { ReactNode } from "react";
import { IconButton } from "./IconButton";
import { Close } from "./icons";

interface DrawerProps {
  title: string;
  subtitle?: ReactNode;
  onClose: () => void;
  children: ReactNode;
}

/** Right-side modal drawer with scrim, Esc-to-close, and a sticky header. */
export function Drawer({ title, subtitle, onClose, children }: DrawerProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="drawer-scrim" onClick={onClose}>
      <aside
        className="drawer"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <header className="drawer-head">
          <div className="drawer-head-titles">
            <h2>{title}</h2>
            {subtitle && <span className="drawer-head-sub">{subtitle}</span>}
          </div>
          <IconButton label="Close" className="drawer-close" onClick={onClose}>
            <Close />
          </IconButton>
        </header>
        <div className="drawer-body">{children}</div>
      </aside>
    </div>
  );
}
