"""P1 acceptance tests: the schema exists and the documented fixes were applied.

These are guard rails, not ceremony. `test_accused_is_not_a_person_identifier`
in particular exists because the single most damaging mistake anyone can make on
this project is treating accused_master_id as a stable person ID.
"""

import pytest
from sqlalchemy import text

from app.db import engine

KSP_TABLES = {
    "state", "district", "unit_type", "unit", "rank", "designation",
    "gender_master", "employee", "court", "act", "section", "crime_head",
    "crime_sub_head", "crime_head_act_section", "case_category",
    "gravity_offence", "case_status_master", "caste_master", "religion_master",
    "occupation_master", "case_master", "inv_occurance_time",
    "complainant_details", "victim", "accused", "act_section_association",
    "arrest_surrender", "inv_arrest_surrender_accused", "chargesheet_details",
}

DERIVED_TABLES = {
    "person_cluster", "person_cluster_member", "er_review_queue", "case_translation",
}


@pytest.fixture(scope="module")
def conn():
    with engine.connect() as c:
        yield c


def _tables(conn, schema: str) -> set[str]:
    rows = conn.execute(
        text("SELECT table_name FROM information_schema.tables WHERE table_schema = :s"),
        {"s": schema},
    )
    return {r[0] for r in rows}


def test_ksp_schema_complete(conn):
    assert KSP_TABLES <= _tables(conn, "ksp")


def test_derived_schema_complete(conn):
    assert DERIVED_TABLES <= _tables(conn, "derived")


def test_extensions_installed(conn):
    rows = conn.execute(text("SELECT extname FROM pg_extension"))
    installed = {r[0] for r in rows}
    assert {"postgis", "vector", "pg_trgm", "fuzzystrmatch"} <= installed


def test_fix1_act_section_association_uses_varchar(conn):
    """[FIX-1] Diagram types these as INT against VARCHAR parents."""
    rows = conn.execute(
        text(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema='ksp' AND table_name='act_section_association'"
        )
    )
    types = dict(rows.all())
    assert types["act_code"] == "character varying"
    assert types["section_code"] == "character varying"


def test_fix2_section_has_primary_key(conn):
    """[FIX-2] The supplied diagram declares no PK on Section."""
    pk = conn.execute(
        text(
            "SELECT constraint_name FROM information_schema.table_constraints "
            "WHERE table_schema='ksp' AND table_name='section' AND constraint_type='PRIMARY KEY'"
        )
    ).scalar_one_or_none()
    assert pk is not None


def test_cs_type_constrained_to_known_outcomes(conn):
    """cs_type is our only supervised label — a typo here silently corrupts P16."""
    with pytest.raises(Exception):
        conn.execute(
            text(
                "INSERT INTO ksp.chargesheet_details (cs_id, cs_type) VALUES (-1, 'X')"
            )
        )
        conn.commit()
    # Intentional error aborts the shared transaction — clear it for later tests.
    conn.rollback()


def test_accused_is_not_a_person_identifier(conn):
    """accused_master_id is scoped to one FIR. Cross-case identity lives in
    derived.person_cluster_member. This test documents that contract."""
    fk_target = conn.execute(
        text(
            "SELECT ccu.table_name FROM information_schema.table_constraints tc "
            "JOIN information_schema.constraint_column_usage ccu "
            "  ON tc.constraint_name = ccu.constraint_name "
            "WHERE tc.table_schema='derived' AND tc.table_name='person_cluster_member' "
            "  AND tc.constraint_type='FOREIGN KEY' AND ccu.table_name='accused'"
        )
    ).scalar_one_or_none()
    # person_cluster_member deliberately does NOT foreign-key to accused:
    # source_row_id is polymorphic across accused/victim/complainant.
    assert fk_target is None


def test_person_roles_share_one_namespace(conn):
    """P7a: victim-offender overlap requires all three roles in one enum."""
    rows = conn.execute(
        text(
            "SELECT e.enumlabel FROM pg_enum e "
            "JOIN pg_type t ON t.oid = e.enumtypid WHERE t.typname = 'party_role'"
        )
    )
    assert {r[0] for r in rows} == {"accused", "victim", "complainant"}
