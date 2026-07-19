"""Compliance tools (P11) — PLAN.md §4.1 and §4.6.

Two operational tools, both pure SQL over the date chain, both worth getting exactly
right because they are immediately useful to a real officer:

  * ``chargesheet_deadline_watch`` — the default-bail early-warning board. Under CrPC
    §167 (now the BNSS equivalent) an accused in custody becomes entitled to *default
    bail* if no chargesheet is filed within the statutory window — 90 days for grave
    (heinous) offences, 60 otherwise. This finds cases where an arrest exists, no
    chargesheet has been filed, and the clock is running out, bucketed by urgency.
  * ``registration_delay_report`` — the FIR-registration integrity metric. A persistent
    lag between when a station received information and when it registered the FIR is the
    statistical signature of delayed or refused registration. Reports the lag per unit and
    flags statistical outliers.

Both inherit the RBAC / provenance / audit machinery from :mod:`app.tools.base`.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.tools.base import Principal, Provenance, Tool, ToolResult, sql_hash

# Statutory default-bail windows (days). Configurable per call, but these are the defaults.
HEINOUS_DEFAULT_DAYS = 90
NON_HEINOUS_DEFAULT_DAYS = 60
HEINOUS_GRAVITY_ID = 1  # gravity_offence: 1 = Heinous, 2 = Non-Heinous


class DeadlineWatchParams(BaseModel):
    district_id: int | None = Field(None, description="Restrict to one district.")
    warn_within_days: int = Field(
        15,
        description="Flag cases within this many days of the deadline (and any already breached).",
    )
    max_overdue_days: int = Field(
        45,
        description=(
            "Only report breaches up to this many days past the deadline. Beyond this the "
            "accused has long since been released, so it is a stale open case, not an "
            "actionable default-bail risk. Raise it to audit historical breaches."
        ),
    )
    heinous_deadline_days: int = Field(
        HEINOUS_DEFAULT_DAYS, description="Window for heinous offences."
    )
    non_heinous_deadline_days: int = Field(
        NON_HEINOUS_DEFAULT_DAYS, description="Window for non-heinous offences."
    )
    as_of: date | None = Field(None, description="Evaluate as of this date (defaults to today).")


def _bucket(days_remaining: int) -> str:
    if days_remaining < 0:
        return "BREACHED"
    if days_remaining <= 7:
        return "critical (0-7d)"
    if days_remaining <= 15:
        return "warning (8-15d)"
    if days_remaining <= 30:
        return "watch (16-30d)"
    return "ok (>30d)"


class ChargesheetDeadlineWatchTool(Tool):
    name = "chargesheet_deadline_watch"
    description = (
        "Cases with an arrest and no chargesheet whose statutory default-bail deadline "
        "(60/90 days) is approaching or breached, bucketed by days remaining."
    )
    Params = DeadlineWatchParams
    # operational/compliance: no offender names in the output, scoped to the caller's units
    person_level = False

    _SQL = """
        WITH arr AS (
            SELECT case_master_id, MIN(arrest_surrender_date) AS first_arrest
            FROM ksp.arrest_surrender
            WHERE arrest_surrender_date IS NOT NULL
            GROUP BY case_master_id
        ),
        board AS (
            SELECT c.case_master_id, c.crime_no, c.police_station_id, u.district_id,
                   u.unit_name AS station_name, c.gravity_offence_id, arr.first_arrest,
                   (COALESCE(:as_of, CURRENT_DATE) - arr.first_arrest) AS days_in_custody,
                   CASE WHEN c.gravity_offence_id = :heinous_id
                        THEN :heinous_days ELSE :non_heinous_days END AS deadline_days
            FROM ksp.case_master c
            JOIN arr ON arr.case_master_id = c.case_master_id
            JOIN ksp.unit u ON u.unit_id = c.police_station_id
            LEFT JOIN ksp.chargesheet_details cs ON cs.case_master_id = c.case_master_id
            WHERE cs.cs_id IS NULL {scope} {district}
        )
        SELECT case_master_id, crime_no, police_station_id, station_name, district_id,
               gravity_offence_id, first_arrest, days_in_custody, deadline_days,
               (deadline_days - days_in_custody) AS days_remaining
        FROM board
        WHERE (deadline_days - days_in_custody) <= :warn_within
          AND (deadline_days - days_in_custody) >= -:max_overdue
        ORDER BY days_remaining ASC
    """

    def _run(
        self, principal: Principal, params: DeadlineWatchParams, session: Session
    ) -> ToolResult:
        scope_sql, bind = self.scope_clause(principal, session, "c.police_station_id")
        district_sql = ""
        if params.district_id is not None:
            district_sql = " AND u.district_id = :district"
            bind["district"] = params.district_id
        bind.update(
            {
                "as_of": params.as_of,
                "heinous_id": HEINOUS_GRAVITY_ID,
                "heinous_days": params.heinous_deadline_days,
                "non_heinous_days": params.non_heinous_deadline_days,
                "warn_within": params.warn_within_days,
                "max_overdue": params.max_overdue_days,
            }
        )
        sql = self._SQL.format(scope=scope_sql, district=district_sql)
        rows = session.execute(text(sql), bind).mappings().all()

        cases = []
        summary: dict[str, int] = {}
        for r in rows:
            bucket = _bucket(r["days_remaining"])
            summary[bucket] = summary.get(bucket, 0) + 1
            cases.append(
                {
                    "case_master_id": r["case_master_id"],
                    "crime_no": r["crime_no"],
                    "station": r["station_name"],
                    "district_id": r["district_id"],
                    "heinous": r["gravity_offence_id"] == HEINOUS_GRAVITY_ID,
                    "arrest_date": str(r["first_arrest"]),
                    "days_in_custody": r["days_in_custody"],
                    "deadline_days": r["deadline_days"],
                    "days_remaining": r["days_remaining"],
                    "bucket": bucket,
                }
            )

        data = {
            "as_of": str(params.as_of) if params.as_of else "today",
            "total_flagged": len(cases),
            "summary_by_bucket": summary,
            "cases": cases,
        }
        return ToolResult(
            data=data,
            provenance=Provenance(
                sql_hash=sql_hash(sql, {k: str(v) for k, v in bind.items()}),
                row_ids=[c["case_master_id"] for c in cases],
                crime_nos=[c["crime_no"] for c in cases if c["crime_no"]],
            ),
        )


class RegistrationDelayParams(BaseModel):
    district_id: int | None = Field(None, description="Restrict to one district.")
    slow_threshold_days: int = Field(
        3, description="A case is 'slow to register' if its lag exceeds this many days."
    )
    min_cases: int = Field(10, description="Ignore units with fewer than this many cases.")
    outlier_z: float = Field(
        2.0, description="Flag units above mean + z*stddev of the per-unit lag."
    )


class RegistrationDelayReportTool(Tool):
    name = "registration_delay_report"
    description = (
        "Per-unit distribution of the info-received to FIR-registered lag, flagging "
        "statistical outliers — the signature of delayed or refused registration."
    )
    Params = RegistrationDelayParams
    aggregate = True
    count_field = "cases"

    _SQL = """
        SELECT u.unit_id, u.unit_name, u.district_id,
               count(*) AS cases,
               round(avg(c.crime_registered_date - c.info_received_ps_date::date)::numeric, 2)
                   AS avg_lag_days,
               max(c.crime_registered_date - c.info_received_ps_date::date) AS max_lag_days,
               round((100.0 * count(*) FILTER (
                   WHERE (c.crime_registered_date - c.info_received_ps_date::date) > :slow
               ) / count(*))::numeric, 1) AS pct_slow
        FROM ksp.case_master c
        JOIN ksp.unit u ON u.unit_id = c.police_station_id
        WHERE c.info_received_ps_date IS NOT NULL AND c.crime_registered_date IS NOT NULL
              {scope} {district}
        GROUP BY u.unit_id, u.unit_name, u.district_id
        HAVING count(*) >= :min_cases
        ORDER BY avg_lag_days DESC
    """

    def _run(
        self, principal: Principal, params: RegistrationDelayParams, session: Session
    ) -> ToolResult:
        scope_sql, bind = self.scope_clause(principal, session, "c.police_station_id")
        district_sql = ""
        if params.district_id is not None:
            district_sql = " AND u.district_id = :district"
            bind["district"] = params.district_id
        bind.update({"slow": params.slow_threshold_days, "min_cases": params.min_cases})
        sql = self._SQL.format(scope=scope_sql, district=district_sql)
        rows = session.execute(text(sql), bind).mappings().all()

        avgs = [float(r["avg_lag_days"]) for r in rows]
        threshold = _outlier_threshold(avgs, params.outlier_z)
        units = [
            {
                "unit_id": r["unit_id"],
                "unit_name": r["unit_name"],
                "district_id": r["district_id"],
                "cases": r["cases"],
                "avg_lag_days": float(r["avg_lag_days"]),
                "max_lag_days": r["max_lag_days"],
                "pct_slow": float(r["pct_slow"]),
                "is_outlier": threshold is not None and float(r["avg_lag_days"]) > threshold,
            }
            for r in rows
        ]
        data = {
            "outlier_threshold_days": round(threshold, 2) if threshold is not None else None,
            "n_units": len(units),
            "n_outliers": sum(1 for u in units if u["is_outlier"]),
            "units": units,
            "caveat": (
                "Lag is an integrity signal, not proof; investigate flagged units, "
                "don't sanction on this alone."
            ),
        }
        return ToolResult(
            data=data,
            provenance=Provenance(
                sql_hash=sql_hash(sql, {k: str(v) for k, v in bind.items()}),
                row_ids=[u["unit_id"] for u in units],
                crime_nos=[],
            ),
        )


def _outlier_threshold(values: list[float], z: float) -> float | None:
    """mean + z*stddev over the per-unit averages, or None if too few units."""
    n = len(values)
    if n < 3:
        return None
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    return mean + z * (var**0.5)
