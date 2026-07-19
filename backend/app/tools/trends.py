"""Trend and hotspot tools (P13) — tools 11–16 of PLAN.md §3.

crime_trend, hotspot_scan (DBSCAN), spatiotemporal_clusters, compare_to_baseline (the
red-zone z-score), seasonality, and zero_fir_flows. These are the aggregate/pattern layer:
they answer "where, when, how much, and is that unusual" over the whole caseload, so they are
``aggregate`` (k-anonymised for the analyst/policymaker roles) and scoped to the caller's
units for operational roles.

Two honesty rules are baked in:

  * **Geo provenance is never blurred.** ``latitude``/``longitude`` are ~58% null, and the
    non-null points are district-centroid-ish, not survey-grade. hotspot_scan therefore
    clusters *only* the cases that carry their own coordinates and reports, in the open, how
    many cases it had to leave out because they could only be placed at a district centroid.
    Every geo result says whether a point is precise or an inferred centroid.
  * **No invented flows.** zero_fir_flows extracts the CrimeNo category digit (a real, unused
    signal) to find Zero FIRs, and derives cross-jurisdiction transfer only where the CrimeNo's
    embedded jurisdiction actually differs from the assigned unit's — it does not fabricate a
    destination where the data has none (see the data-surprise note in CONSISTENCY.md).
"""

from __future__ import annotations

from statistics import mean, pstdev

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.tools.base import (
    AGGREGATE_ONLY_ROLES,
    Principal,
    Provenance,
    Tool,
    ToolResult,
    apply_k_anonymity,
    sql_hash,
)

# -----------------------------------------------------------------------------
# Shared helpers
# -----------------------------------------------------------------------------


def parse_crime_no(crime_no: str) -> dict | None:
    """CrimeNo = 1 category + 4 district + 4 station + 4 year + 5 serial (18 digits).
    Returns the parsed segments, or None if it does not match the documented format.
    Category: 1=FIR, 3=UDR, 4=PAR, 8=Zero FIR (CLAUDE.md)."""
    if crime_no is None:
        return None
    s = str(crime_no).strip()
    if len(s) != 18 or not s.isdigit():
        return None
    return {
        "category": int(s[0]),
        "district": int(s[1:5]),
        "station": int(s[5:9]),
        "year": int(s[9:13]),
        "serial": int(s[13:18]),
    }


_CATEGORY = {1: "FIR", 3: "UDR", 4: "PAR", 8: "Zero FIR"}

_DISTRICT_CENTROIDS: dict[int, tuple[float, float]] | None = None


def district_centroids(session: Session) -> dict[int, tuple[float, float]]:
    """district_id -> (lat, lon) from the mean of that district's non-null case coordinates.
    Cached. Used as the honest fallback location for cases with null coordinates."""
    global _DISTRICT_CENTROIDS
    if _DISTRICT_CENTROIDS is None:
        rows = session.execute(
            text(
                "SELECT u.district_id, avg(c.latitude) AS lat, avg(c.longitude) AS lon "
                "FROM ksp.case_master c JOIN ksp.unit u ON u.unit_id = c.police_station_id "
                "WHERE c.latitude IS NOT NULL AND c.longitude IS NOT NULL "
                "GROUP BY u.district_id"
            )
        ).mappings()
        _DISTRICT_CENTROIDS = {
            r["district_id"]: (float(r["lat"]), float(r["lon"])) for r in rows
        }
    return _DISTRICT_CENTROIDS


def reset_centroids() -> None:
    global _DISTRICT_CENTROIDS
    _DISTRICT_CENTROIDS = None


def _kanon(principal: Principal, rows: list[dict], count_field: str) -> list[dict]:
    """Suppress sub-threshold cells for aggregate-only roles (analyst/policymaker)."""
    if principal.role in AGGREGATE_ONLY_ROLES:
        return apply_k_anonymity(rows, count_field)
    return rows


_PERIOD_TRUNC = {"day": "day", "week": "week", "month": "month", "year": "year"}


# =============================================================================
# 11. crime_trend
# =============================================================================


class CrimeTrendParams(BaseModel):
    period: str = Field("month", description="Bucket size: day, week, month, or year.")
    district_id: int | None = None
    station_id: int | None = None
    crime_major_head_id: int | None = None
    gravity_offence_id: int | None = None
    date_from: str | None = None
    date_to: str | None = None


class CrimeTrendTool(Tool):
    name = "crime_trend"
    description = (
        "Case counts over time, bucketed by day/week/month/year, optionally filtered by "
        "district, station, crime head, or gravity. The time series behind any 'is crime "
        "rising?' question."
    )
    Params = CrimeTrendParams
    aggregate = True
    count_field = "count"

    def _run(self, principal: Principal, params: CrimeTrendParams, session: Session) -> ToolResult:
        trunc = _PERIOD_TRUNC.get(params.period, "month")
        scope_sql, bind = self.scope_clause(principal, session, "c.police_station_id")
        clauses = []
        if params.district_id is not None:
            clauses.append("u.district_id = :district")
            bind["district"] = params.district_id
        if params.station_id is not None:
            clauses.append("c.police_station_id = :station")
            bind["station"] = params.station_id
        if params.crime_major_head_id is not None:
            clauses.append("c.crime_major_head_id = :head")
            bind["head"] = params.crime_major_head_id
        if params.gravity_offence_id is not None:
            clauses.append("c.gravity_offence_id = :grav")
            bind["grav"] = params.gravity_offence_id
        if params.date_from:
            clauses.append("c.crime_registered_date >= :dfrom")
            bind["dfrom"] = params.date_from
        if params.date_to:
            clauses.append("c.crime_registered_date <= :dto")
            bind["dto"] = params.date_to
        where = (" AND " + " AND ".join(clauses)) if clauses else ""
        sql = (
            f"SELECT date_trunc('{trunc}', c.crime_registered_date)::date AS bucket, "
            "count(*) AS count "
            "FROM ksp.case_master c JOIN ksp.unit u ON u.unit_id = c.police_station_id "
            "WHERE c.crime_registered_date IS NOT NULL" + scope_sql + where + " "
            "GROUP BY 1 ORDER BY 1"
        )
        rows = session.execute(text(sql), bind).mappings().all()
        series = [{"period": str(r["bucket"]), "count": r["count"]} for r in rows]
        series = _kanon(principal, series, "count")
        total = sum(s["count"] for s in series)
        return ToolResult(
            data={"period": trunc, "points": len(series), "total": total, "series": series},
            provenance=Provenance(
                sql_hash=sql_hash(sql, {k: str(v) for k, v in bind.items()}),
                row_ids=[],
                crime_nos=[],
            ),
        )


# =============================================================================
# 12. hotspot_scan (DBSCAN over precise coordinates)
# =============================================================================


class HotspotScanParams(BaseModel):
    district_id: int | None = None
    crime_major_head_id: int | None = None
    date_from: str | None = None
    date_to: str | None = None
    eps_km: float = Field(2.0, ge=0.1, le=50, description="DBSCAN neighbourhood radius in km.")
    min_samples: int = Field(5, ge=2, le=100, description="Min cases to form a hotspot.")


class HotspotScanTool(Tool):
    name = "hotspot_scan"
    description = (
        "Find spatial crime hotspots via DBSCAN over case coordinates. Clusters only cases "
        "with precise coordinates and reports, openly, how many cases were left out because "
        "they have no coordinates and could only be placed at a district centroid."
    )
    Params = HotspotScanParams
    aggregate = True
    count_field = "size"

    def _run(self, principal: Principal, params: HotspotScanParams, session: Session) -> ToolResult:
        import numpy as np
        from sklearn.cluster import DBSCAN

        scope_sql, bind = self.scope_clause(principal, session, "c.police_station_id")
        clauses = []
        if params.district_id is not None:
            clauses.append("u.district_id = :district")
            bind["district"] = params.district_id
        if params.crime_major_head_id is not None:
            clauses.append("c.crime_major_head_id = :head")
            bind["head"] = params.crime_major_head_id
        if params.date_from:
            clauses.append("c.crime_registered_date >= :dfrom")
            bind["dfrom"] = params.date_from
        if params.date_to:
            clauses.append("c.crime_registered_date <= :dto")
            bind["dto"] = params.date_to
        where = (" AND " + " AND ".join(clauses)) if clauses else ""
        sql = (
            "SELECT c.case_master_id, c.crime_no, c.latitude, c.longitude, u.district_id "
            "FROM ksp.case_master c JOIN ksp.unit u ON u.unit_id = c.police_station_id "
            "WHERE 1=1" + scope_sql + where
        )
        rows = session.execute(text(sql), bind).mappings().all()
        precise = [r for r in rows if r["latitude"] is not None and r["longitude"] is not None]
        inferred = len(rows) - len(precise)

        hotspots: list[dict] = []
        noise = 0
        if len(precise) >= params.min_samples:
            coords = np.array([[float(r["latitude"]), float(r["longitude"])] for r in precise])
            # ~111 km per degree of latitude; convert the km radius to degrees for DBSCAN.
            eps_deg = params.eps_km / 111.0
            labels = DBSCAN(eps=eps_deg, min_samples=params.min_samples).fit_predict(coords)
            noise = int((labels == -1).sum())
            for cid in sorted(set(labels) - {-1}):
                members = [precise[i] for i in range(len(precise)) if labels[i] == cid]
                pts = coords[labels == cid]
                hotspots.append(
                    {
                        "hotspot_id": int(cid),
                        "size": len(members),
                        "center_lat": round(float(pts[:, 0].mean()), 5),
                        "center_lon": round(float(pts[:, 1].mean()), 5),
                        "districts": sorted({m["district_id"] for m in members}),
                        "point_type": "precise",
                        "sample_crime_nos": [m["crime_no"] for m in members[:5] if m["crime_no"]],
                    }
                )
            hotspots.sort(key=lambda h: h["size"], reverse=True)
        hotspots = _kanon(principal, hotspots, "size")

        total = len(rows)
        data = {
            "coverage": {
                "total_cases": total,
                "precise": len(precise),
                "inferred_centroid_only": inferred,
                "precise_pct": round(100.0 * len(precise) / total, 1) if total else 0.0,
            },
            "hotspot_count": len(hotspots),
            "hotspots": hotspots,
            "noise_points": noise,
            "caveat": (
                "Hotspots are computed on cases carrying precise coordinates only "
                f"({len(precise)} of {total}). The remaining {inferred} case(s) have null "
                "coordinates and are placed at their district centroid, not used for "
                "clustering — treat them as area-level, not point-level."
            ),
        }
        sample = [h["sample_crime_nos"][0] for h in hotspots if h["sample_crime_nos"]]
        return ToolResult(
            data=data,
            provenance=Provenance(
                sql_hash=sql_hash(sql, {k: str(v) for k, v in bind.items()}),
                row_ids=[],
                crime_nos=sample,
            ),
        )


# =============================================================================
# 13. spatiotemporal_clusters (time-of-day x location)
# =============================================================================

_DAYPARTS = [(0, 6, "night (00-06)"), (6, 12, "morning (06-12)"),
             (12, 18, "afternoon (12-18)"), (18, 24, "evening (18-24)")]


class SpatioTemporalParams(BaseModel):
    district_id: int | None = None
    crime_major_head_id: int | None = None
    top: int = Field(15, ge=1, le=100, description="How many hot (place x daypart) cells.")


class SpatioTemporalClustersTool(Tool):
    name = "spatiotemporal_clusters"
    description = (
        "The hot combinations of place (district) and time-of-day — where and *when* crime "
        "concentrates. Uses the incident timestamp; cases with no incident time are counted "
        "separately as time-unknown."
    )
    Params = SpatioTemporalParams
    aggregate = True
    count_field = "count"

    def _run(
        self, principal: Principal, params: SpatioTemporalParams, session: Session
    ) -> ToolResult:
        scope_sql, bind = self.scope_clause(principal, session, "c.police_station_id")
        clauses = []
        if params.district_id is not None:
            clauses.append("u.district_id = :district")
            bind["district"] = params.district_id
        if params.crime_major_head_id is not None:
            clauses.append("c.crime_major_head_id = :head")
            bind["head"] = params.crime_major_head_id
        where = (" AND " + " AND ".join(clauses)) if clauses else ""
        sql = (
            "SELECT u.district_id, "
            "       extract(hour FROM c.incident_from_date)::int AS hr, "
            "       count(*) AS count "
            "FROM ksp.case_master c JOIN ksp.unit u ON u.unit_id = c.police_station_id "
            "WHERE 1=1" + scope_sql + where + " "
            "GROUP BY u.district_id, hr"
        )
        rows = session.execute(text(sql), bind).mappings().all()

        cells: dict[tuple[int, str], int] = {}
        time_unknown = 0
        for r in rows:
            if r["hr"] is None:
                time_unknown += r["count"]
                continue
            daypart = next(lbl for lo, hi, lbl in _DAYPARTS if lo <= r["hr"] < hi)
            key = (r["district_id"], daypart)
            cells[key] = cells.get(key, 0) + r["count"]
        combos = [
            {"district_id": d, "daypart": dp, "count": n} for (d, dp), n in cells.items()
        ]
        combos.sort(key=lambda c: c["count"], reverse=True)
        combos = _kanon(principal, combos, "count")[: params.top]
        return ToolResult(
            data={
                "cells": len(combos),
                "time_unknown_cases": time_unknown,
                "hot_cells": combos,
            },
            provenance=Provenance(
                sql_hash=sql_hash(sql, {k: str(v) for k, v in bind.items()}),
                row_ids=[],
                crime_nos=[],
            ),
        )


# =============================================================================
# 14. compare_to_baseline (red-zone z-score)
# =============================================================================


class CompareBaselineParams(BaseModel):
    window_days: int = Field(30, ge=7, le=365, description="Length of the recent window.")
    baseline_windows: int = Field(6, ge=2, le=24, description="Prior windows forming the baseline.")
    crime_major_head_id: int | None = None
    z_threshold: float = Field(
        2.0, ge=0.5, le=6.0, description="z at/above which a district is a red zone."
    )


class CompareToBaselineTool(Tool):
    name = "compare_to_baseline"
    description = (
        "Flag red-zone districts: compare each district's most recent window of case volume to "
        "its own historical baseline and report a z-score. High z = a district doing markedly "
        "more crime than usual — the signal behind proactive early warning."
    )
    Params = CompareBaselineParams
    aggregate = True
    count_field = "recent_count"

    def _run(
        self, principal: Principal, params: CompareBaselineParams, session: Session
    ) -> ToolResult:
        scope_sql, bind = self.scope_clause(principal, session, "c.police_station_id")
        head_sql = ""
        if params.crime_major_head_id is not None:
            head_sql = " AND c.crime_major_head_id = :head"
            bind["head"] = params.crime_major_head_id
        # anchor windows at the latest registered date in scope
        latest = session.execute(
            text(
                "SELECT max(c.crime_registered_date) FROM ksp.case_master c "
                "JOIN ksp.unit u ON u.unit_id = c.police_station_id "
                "WHERE c.crime_registered_date IS NOT NULL" + scope_sql + head_sql
            ),
            bind,
        ).scalar_one_or_none()
        if latest is None:
            return ToolResult(
                data={"red_zones": [], "districts": [], "note": "no dated cases in scope"},
                provenance=Provenance(sql_hash=sql_hash("compare_to_baseline", bind),
                                      row_ids=[], crime_nos=[]),
            )
        n_windows = params.baseline_windows + 1
        span_from = f"DATE '{latest}' - INTERVAL '{params.window_days * n_windows} days'"
        bind["win"] = params.window_days
        # bucket each in-scope case into a window index counting back from `latest`
        sql = (
            "SELECT u.district_id, "
            f"       floor((DATE '{latest}' - c.crime_registered_date) / :win)::int AS widx, "
            "       count(*) AS count "
            "FROM ksp.case_master c JOIN ksp.unit u ON u.unit_id = c.police_station_id "
            "WHERE c.crime_registered_date IS NOT NULL "
            f"  AND c.crime_registered_date > ({span_from})"
            f"  AND c.crime_registered_date <= DATE '{latest}'" + scope_sql + head_sql + " "
            "GROUP BY u.district_id, widx"
        )
        rows = session.execute(text(sql), bind).mappings().all()

        by_district: dict[int, dict[int, int]] = {}
        for r in rows:
            if 0 <= r["widx"] <= params.baseline_windows:
                by_district.setdefault(r["district_id"], {})[r["widx"]] = r["count"]

        districts = []
        for did, wins in by_district.items():
            recent = wins.get(0, 0)  # widx 0 = most recent window
            baseline = [wins.get(i, 0) for i in range(1, n_windows)]
            mu = mean(baseline) if baseline else 0.0
            sigma = pstdev(baseline) if len(baseline) > 1 else 0.0
            z = (recent - mu) / sigma if sigma > 0 else (0.0 if recent <= mu else float("inf"))
            districts.append(
                {
                    "district_id": did,
                    "recent_count": recent,
                    "baseline_mean": round(mu, 2),
                    "baseline_std": round(sigma, 2),
                    "z_score": round(z, 2) if z != float("inf") else None,
                    "is_red_zone": (z >= params.z_threshold),
                }
            )
        districts.sort(key=lambda d: (d["z_score"] is None, d["z_score"] or 0), reverse=True)
        districts = _kanon(principal, districts, "recent_count")
        red = [d for d in districts if d["is_red_zone"]]
        return ToolResult(
            data={
                "window_days": params.window_days,
                "baseline_windows": params.baseline_windows,
                "red_zone_count": len(red),
                "red_zones": red,
                "districts": districts,
                "caveat": (
                    "z-score vs the district's own recent history; a red zone is a prompt to "
                    "look, not a verdict. Low-volume districts swing easily."
                ),
            },
            provenance=Provenance(
                sql_hash=sql_hash(sql, {k: str(v) for k, v in bind.items()}),
                row_ids=[d["district_id"] for d in districts],
                crime_nos=[],
            ),
        )


# =============================================================================
# 15. seasonality
# =============================================================================


class SeasonalityParams(BaseModel):
    district_id: int | None = None
    crime_major_head_id: int | None = None


class SeasonalityTool(Tool):
    name = "seasonality"
    description = (
        "Seasonal structure of crime: case counts by month-of-year and by day-of-week across "
        "all history, with the peak month and peak weekday."
    )
    Params = SeasonalityParams
    aggregate = True
    count_field = "count"

    def _run(self, principal: Principal, params: SeasonalityParams, session: Session) -> ToolResult:
        scope_sql, bind = self.scope_clause(principal, session, "c.police_station_id")
        clauses = []
        if params.district_id is not None:
            clauses.append("u.district_id = :district")
            bind["district"] = params.district_id
        if params.crime_major_head_id is not None:
            clauses.append("c.crime_major_head_id = :head")
            bind["head"] = params.crime_major_head_id
        where = (" AND " + " AND ".join(clauses)) if clauses else ""
        base = (
            "FROM ksp.case_master c JOIN ksp.unit u ON u.unit_id = c.police_station_id "
            "WHERE c.crime_registered_date IS NOT NULL" + scope_sql + where
        )
        month_rows = session.execute(
            text(
                "SELECT extract(month FROM c.crime_registered_date)::int AS m, count(*) AS count "
                + base + " GROUP BY m ORDER BY m"
            ),
            bind,
        ).mappings().all()
        dow_rows = session.execute(
            text(
                "SELECT extract(dow FROM c.crime_registered_date)::int AS d, count(*) AS count "
                + base + " GROUP BY d ORDER BY d"
            ),
            bind,
        ).mappings().all()
        months = [{"month": r["m"], "count": r["count"]} for r in month_rows]
        dows = [{"dow": r["d"], "count": r["count"]} for r in dow_rows]
        peak_month = max(months, key=lambda x: x["count"])["month"] if months else None
        peak_dow = max(dows, key=lambda x: x["count"])["dow"] if dows else None
        return ToolResult(
            data={
                "by_month": months,
                "by_day_of_week": dows,
                "peak_month": peak_month,
                "peak_day_of_week": peak_dow,
                "dow_legend": "0=Sunday .. 6=Saturday",
            },
            provenance=Provenance(
                sql_hash=sql_hash("seasonality", {k: str(v) for k, v in bind.items()}),
                row_ids=[],
                crime_nos=[],
            ),
        )


# =============================================================================
# 16. zero_fir_flows (CrimeNo category digit)
# =============================================================================


class ZeroFirFlowsParams(BaseModel):
    top: int = Field(20, ge=1, le=200, description="How many registering units to list.")


class ZeroFirFlowsTool(Tool):
    name = "zero_fir_flows"
    description = (
        "Zero FIRs — cases a station registers outside its own jurisdiction, identified by the "
        "CrimeNo category digit (8). Reports the Zero-FIR load per district and any genuine "
        "cross-jurisdiction transfer where the CrimeNo's embedded jurisdiction differs from the "
        "assigned unit's."
    )
    Params = ZeroFirFlowsParams
    aggregate = True
    count_field = "zero_firs"

    def _run(
        self, principal: Principal, params: ZeroFirFlowsParams, session: Session
    ) -> ToolResult:
        scope_sql, bind = self.scope_clause(principal, session, "c.police_station_id")
        sql = (
            "SELECT c.crime_no, u.district_id, c.police_station_id "
            "FROM ksp.case_master c JOIN ksp.unit u ON u.unit_id = c.police_station_id "
            "WHERE left(c.crime_no, 1) = '8'" + scope_sql
        )
        rows = session.execute(text(sql), bind).mappings().all()

        by_district: dict[int, int] = {}
        flows: dict[tuple[int, int], int] = {}
        for r in rows:
            by_district[r["district_id"]] = by_district.get(r["district_id"], 0) + 1
            parsed = parse_crime_no(r["crime_no"])
            if parsed and parsed["district"] != r["district_id"]:
                key = (parsed["district"], r["district_id"])  # registered-under -> assigned
                flows[key] = flows.get(key, 0) + 1

        districts = [
            {"district_id": d, "zero_firs": n} for d, n in by_district.items()
        ]
        districts.sort(key=lambda x: x["zero_firs"], reverse=True)
        districts = _kanon(principal, districts, "zero_firs")[: params.top]
        flow_list = [
            {"from_district": a, "to_district": b, "count": n} for (a, b), n in flows.items()
        ]
        flow_list.sort(key=lambda x: x["count"], reverse=True)
        return ToolResult(
            data={
                "total_zero_firs": len(rows),
                "by_registering_district": districts,
                "cross_jurisdiction_flows": flow_list,
                "note": (
                    "Zero FIRs identified by CrimeNo category digit 8. Cross-jurisdiction "
                    "flow is reported only where the CrimeNo's embedded district differs from "
                    "the assigned unit's; if empty, the source data records no such divergence."
                ),
            },
            provenance=Provenance(
                sql_hash=sql_hash(sql, {k: str(v) for k, v in bind.items()}),
                row_ids=[],
                crime_nos=[r["crime_no"] for r in rows[:20] if r["crime_no"]],
            ),
        )
