"""Load party rows out of the KSP schema into parsed records for entity resolution.

A ``PartyRecord`` is one accused / victim / complainant row with its name already
parsed (P5) and the context signals ER needs attached: district, station, an
estimated birth year (from AgeYear + registration year), and, for accused, the set
of arrest events it belongs to (the co-offending signal P7 propagates over).

This module reads only ``ksp`` — never the ground truth, never ``derived`` person
tables. It is the single place the pipeline touches the source rows.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import psycopg

from app.config import get_settings
from er.names import ParsedName, normalize_token, parse


@dataclass
class PartyRecord:
    idx: int  # dense index into the loaded list (pair keys use this)
    role: str  # 'accused' | 'victim' | 'complainant'
    source_row_id: int
    case_master_id: int
    raw_name: str
    age_year: int | None
    gender_id: int | None
    district_id: int | None
    station_id: int | None
    reg_year: int | None
    parsed: ParsedName
    est_birth_year: int | None
    alias_norm: str | None
    arrest_events: frozenset[int]

    # convenience accessors onto the parsed name
    @property
    def phonetic_key(self) -> str:
        return self.parsed.phonetic_key

    @property
    def patronymic_key(self) -> str | None:
        return self.parsed.patronymic_key

    @property
    def normalized_given(self) -> str:
        return self.parsed.normalized_given

    @property
    def normalized_patronymic(self) -> str | None:
        return self.parsed.normalized_patronymic


def connect() -> psycopg.Connection:
    s = get_settings()
    return psycopg.connect(
        f"host={s.postgres_host} port={s.postgres_port} dbname={s.postgres_db} "
        f"user={s.postgres_user} password={s.postgres_password}"
    )


_PARTY_SQL = """
SELECT '{role}' AS role, {id_col} AS source_row_id, p.case_master_id, {name_col} AS raw_name,
       p.age_year, p.gender_id, u.district_id, c.police_station_id AS station_id,
       EXTRACT(YEAR FROM c.crime_registered_date)::int AS reg_year
FROM ksp.{table} p
JOIN ksp.case_master c ON c.case_master_id = p.case_master_id
LEFT JOIN ksp.unit u ON u.unit_id = c.police_station_id
"""

_ROLE_TABLES = {
    "accused": ("accused", "accused_master_id", "accused_name"),
    "victim": ("victim", "victim_master_id", "victim_name"),
    "complainant": ("complainant_details", "complainant_id", "complainant_name"),
}


def load_party_records(
    conn: psycopg.Connection, roles: tuple[str, ...] = ("accused", "victim", "complainant")
) -> list[PartyRecord]:
    """Load and parse every party row for the requested roles."""
    arrests = _load_arrest_events(conn)
    records: list[PartyRecord] = []
    idx = 0
    with conn.cursor() as cur:
        for role in roles:
            table, id_col, name_col = _ROLE_TABLES[role]
            cur.execute(_PARTY_SQL.format(role=role, id_col=id_col, name_col=name_col, table=table))
            for row in cur.fetchall():
                (
                    r_role,
                    source_row_id,
                    case_id,
                    raw_name,
                    age,
                    gender,
                    district_id,
                    station_id,
                    reg_year,
                ) = row
                parsed = parse(raw_name)
                est_by = (reg_year - age) if (reg_year is not None and age is not None) else None
                alias_norm = normalize_token(parsed.alias) if parsed.alias else None
                events = (
                    arrests.get(source_row_id, frozenset()) if role == "accused" else frozenset()
                )
                records.append(
                    PartyRecord(
                        idx=idx,
                        role=r_role,
                        source_row_id=source_row_id,
                        case_master_id=case_id,
                        raw_name=raw_name or "",
                        age_year=age,
                        gender_id=gender,
                        district_id=district_id,
                        station_id=station_id,
                        reg_year=reg_year,
                        parsed=parsed,
                        est_birth_year=est_by,
                        alias_norm=alias_norm,
                        arrest_events=events,
                    )
                )
                idx += 1
    return records


def _load_arrest_events(conn: psycopg.Connection) -> dict[int, frozenset[int]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT accused_master_id, array_agg(arrest_surrender_id) "
            "FROM ksp.inv_arrest_surrender_accused GROUP BY accused_master_id"
        )
        return {row[0]: frozenset(row[1]) for row in cur.fetchall()}


# -----------------------------------------------------------------------------
# District adjacency — the "same/adjacent district" geography signal.
# Derived from case-coordinate centroids so ER stays self-contained on ksp.
# -----------------------------------------------------------------------------


def district_adjacency(conn: psycopg.Connection, threshold_deg: float = 1.6) -> dict[int, set[int]]:
    """Map district_id -> set of adjacent district_ids, from coordinate centroids.

    Uses the mean of non-null case coordinates per district. lat/long is ~58% null
    but the non-null points cluster at the district centroid, so the mean is a good
    proxy. Districts within ``threshold_deg`` (~1.6° ≈ 175 km) are treated adjacent.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT u.district_id, avg(c.latitude), avg(c.longitude) "
            "FROM ksp.case_master c JOIN ksp.unit u ON u.unit_id = c.police_station_id "
            "WHERE c.latitude IS NOT NULL AND c.longitude IS NOT NULL "
            "GROUP BY u.district_id"
        )
        centroids = {row[0]: (float(row[1]), float(row[2])) for row in cur.fetchall()}

    adj: dict[int, set[int]] = {d: set() for d in centroids}
    ids = list(centroids)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            (la, lo), (lb, lob) = centroids[a], centroids[b]
            if math.hypot(la - lb, lo - lob) <= threshold_deg:
                adj[a].add(b)
                adj[b].add(a)
    return adj
