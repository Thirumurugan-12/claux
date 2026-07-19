import type { DemoRole } from "../../api";

interface RoleSwitcherProps {
  roles: DemoRole[];
  roleIdx: number;
  onChange: (idx: number) => void;
}

/** RBAC role selector. Changing role remounts the chat with a new principal (see App). */
export function RoleSwitcher({ roles, roleIdx, onChange }: RoleSwitcherProps) {
  return (
    <div className="role-switcher">
      <label htmlFor="role">Acting as</label>
      <span className="select-wrap">
        <select
          id="role"
          value={roleIdx}
          onChange={(e) => onChange(Number(e.target.value))}
          disabled={!roles.length}
        >
          {roles.map((r, i) => (
            <option value={i} key={r.role}>
              {r.label}
            </option>
          ))}
        </select>
      </span>
    </div>
  );
}
