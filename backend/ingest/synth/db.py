"""Load a generated :class:`Dataset` into Postgres via COPY.

COPY (not executemany) because the acceptance target is 50k cases — a few hundred
thousand rows across the party tables — and COPY is the only thing that loads that
in seconds. Connection details come from the same settings the app uses, so this
points at whatever database the rest of the stack does.
"""

from __future__ import annotations

import psycopg

from app.config import get_settings

from .generator import Dataset

# Truncated before a fresh load, in an order where CASCADE cleans up the rest.
# Truncating ksp.case_master cascades into its child tables and the derived tables
# that reference it; the reference tables are listed so a reload reseeds them too.
_TRUNCATE = [
    "ksp.chargesheet_details",
    "ksp.inv_arrest_surrender_accused",
    "ksp.arrest_surrender",
    "ksp.act_section_association",
    "ksp.accused",
    "ksp.victim",
    "ksp.complainant_details",
    "ksp.inv_occurance_time",
    "ksp.case_master",
    "ksp.crime_head_act_section",
    "ksp.crime_sub_head",
    "ksp.crime_head",
    "ksp.section",
    "ksp.act",
    "ksp.court",
    "ksp.employee",
    "ksp.unit",
    "ksp.designation",
    "ksp.rank",
    "ksp.unit_type",
    "ksp.district",
    "ksp.state",
    "ksp.gravity_offence",
    "ksp.case_status_master",
    "ksp.caste_master",
    "ksp.religion_master",
    "ksp.occupation_master",
]


def _conninfo() -> str:
    s = get_settings()
    return (
        f"host={s.postgres_host} port={s.postgres_port} dbname={s.postgres_db} "
        f"user={s.postgres_user} password={s.postgres_password}"
    )


def load(ds: Dataset, *, reset: bool = True) -> dict[str, int]:
    """Load every table in ``ds`` and return per-table row counts."""
    counts: dict[str, int] = {}
    with psycopg.connect(_conninfo(), autocommit=False) as conn:
        with conn.cursor() as cur:
            if reset:
                cur.execute("TRUNCATE " + ", ".join(_TRUNCATE) + " RESTART IDENTITY CASCADE")
            for table in ds.order():
                rows = ds.tables[table]
                cols = ds.columns(table)
                counts[table] = _copy(cur, table, cols, rows)
        conn.commit()
    return counts


def _copy(cur, table: str, columns: tuple[str, ...], rows: list[tuple]) -> int:
    if not rows:
        return 0
    collist = ", ".join(columns)
    with cur.copy(f"COPY {table} ({collist}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)
    return len(rows)
