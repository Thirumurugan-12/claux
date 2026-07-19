import { Emblem } from "../../components/icons";
import { ThemeToggle } from "../../components/ThemeToggle";
import { RoleSwitcher } from "../roles/RoleSwitcher";
import type { DemoRole } from "../../api";
import type { Theme } from "../../hooks/useTheme";

interface TopBarProps {
  roles: DemoRole[];
  roleIdx: number;
  onRoleChange: (idx: number) => void;
  theme: Theme;
  onToggleTheme: () => void;
}

/** Global controls only: brand, the RBAC role selector, and the theme toggle. The active
 * scope readout lives in the Session tile so the control and its status aren't duplicated. */
export function TopBar({ roles, roleIdx, onRoleChange, theme, onToggleTheme }: TopBarProps) {
  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-mark" aria-hidden>
          <Emblem />
        </span>
        <span className="brand-titles">
          <span className="brand-name">KSP Crime Intelligence</span>
          <span className="brand-sub">Karnataka State Police · SCRB</span>
        </span>
      </div>

      <div className="topbar-spacer" />

      <RoleSwitcher roles={roles} roleIdx={roleIdx} onChange={onRoleChange} />
      <ThemeToggle theme={theme} onToggle={onToggleTheme} />
    </header>
  );
}
