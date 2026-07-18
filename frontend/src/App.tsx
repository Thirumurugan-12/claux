import { useEffect, useState } from "react";

/**
 * P1 placeholder. Verifies the frontend container can reach the backend
 * through the Vite proxy. The real four-pane shell lands in P19.
 */

type DbHealth = {
  status: string;
  postgres?: string;
  postgis?: string;
  ksp_tables?: number;
  derived_tables?: number;
  detail?: string;
};

export default function App() {
  const [health, setHealth] = useState<DbHealth | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/health/db")
      .then((r) => r.json())
      .then(setHealth)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <main className="shell">
      <h1>KSP Crime Intelligence Platform</h1>
      <p className="sub">Karnataka State Police · SCRB — Datathon 2026</p>

      <section className="panel">
        <h2>System status</h2>
        {error && <p className="err">Backend unreachable: {error}</p>}
        {!health && !error && <p className="muted">Checking…</p>}
        {health && (
          <dl>
            <dt>Backend</dt>
            <dd className={health.status === "ok" ? "ok" : "err"}>{health.status}</dd>
            <dt>Postgres</dt>
            <dd>{health.postgres ?? "—"}</dd>
            <dt>PostGIS</dt>
            <dd>{health.postgis ?? "—"}</dd>
            <dt>ksp tables</dt>
            <dd>{health.ksp_tables ?? "—"}</dd>
            <dt>derived tables</dt>
            <dd>{health.derived_tables ?? "—"}</dd>
          </dl>
        )}
        {health?.detail && <p className="err">{health.detail}</p>}
      </section>

      <p className="muted next">Next: P2 — synthetic data generator.</p>
    </main>
  );
}
