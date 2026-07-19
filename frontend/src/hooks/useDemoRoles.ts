import { useEffect, useMemo, useState } from "react";
import { fetchDemoRoles } from "../api";
import type { DemoRole, Principal } from "../api";

const FALLBACK_PRINCIPAL: Principal = { name: "SP", role: "sp" };

/**
 * Loads the demo RBAC roles and tracks the active one. Defaults to SP — a district officer who
 * can see people, networks, and trends in scope, which makes the cross-jurisdiction demo work.
 */
export function useDemoRoles() {
  const [roles, setRoles] = useState<DemoRole[]>([]);
  const [roleIdx, setRoleIdx] = useState(0);

  useEffect(() => {
    let live = true;
    fetchDemoRoles()
      .then((r) => {
        if (!live) return;
        setRoles(r);
        const sp = r.findIndex((x) => x.role === "sp");
        if (sp >= 0) setRoleIdx(sp);
      })
      .catch(() => live && setRoles([]));
    return () => {
      live = false;
    };
  }, []);

  const current: DemoRole | null = roles[roleIdx] ?? null;
  const principal = useMemo<Principal>(() => current?.principal ?? FALLBACK_PRINCIPAL, [current]);

  return { roles, roleIdx, setRoleIdx, current, principal };
}
