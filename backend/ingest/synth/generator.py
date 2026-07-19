"""Assemble a full synthetic KSP dataset.

Produces every ksp table as a list of row tuples, keyed by table name in
FK-safe insertion order, plus the hidden ground truth. Nothing here talks to the
database — :mod:`ingest.synth.db` loads what this returns, which keeps generation
deterministic and unit-testable without a live Postgres.

The invariants that make the data usable downstream:
  * CrimeNo is well-formed and its segments agree with the row's district/station.
  * The date chain is monotonic: incident <= info-received <= registered <= arrest
    <= chargesheet, with a realistic (and occasionally pathological) lag injected.
  * Multi-accused cases share a single arrest event via the junction table, so the
    co-offending graph P7/P12 read has real edges.
  * A deliberate cohort of recent arrested-but-not-chargesheeted cases sits in the
    60/90-day danger band so the chargesheet deadline board (P11) has something to find.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from . import karnataka as ka
from . import narratives as nv
from .names import render_variant
from .registry import PersonRegistry, RegistryConfig

REFERENCE_NOW = date(2026, 7, 18)
YEAR_WEIGHTS = {2022: 0.10, 2023: 0.16, 2024: 0.22, 2025: 0.28, 2026: 0.24}


@dataclass
class Dataset:
    tables: dict[str, list[tuple]] = field(default_factory=dict)
    ground_truth: dict = field(default_factory=dict)
    _columns: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def add(self, table: str, columns: tuple[str, ...], rows: list[tuple]) -> None:
        self.tables[table] = rows
        self._columns[table] = columns

    def columns(self, table: str) -> tuple[str, ...]:
        return self._columns[table]

    def order(self) -> list[str]:
        return list(self.tables.keys())


class Generator:
    def __init__(self, n_cases: int, seed: int = 42):
        self.n = n_cases
        self.rng = random.Random(seed)
        self.registry = PersonRegistry(self.rng, RegistryConfig(n_cases=n_cases), ka.DISTRICTS)

        # id counters
        self._case_id = 0
        self._complainant_id = 0
        self._victim_id = 0
        self._accused_id = 0
        self._arrest_id = 0
        self._cs_id = 0
        self._serial: dict[tuple, int] = {}
        self._mo_truth: dict[int, str] = {}  # case_master_id -> MO signature (P15 answer key)

        # station -> [employee_id] for IO assignment
        self.ref = ka.build_reference(self.rng)
        self._station_ios: dict[int, list[int]] = {}
        for emp in self.ref.employees:
            self._station_ios.setdefault(emp[2], []).append(emp[0])
        self.stations = self.ref.stations

    # -- id helpers ----------------------------------------------------------

    def _next(self, attr: str) -> int:
        v = getattr(self, attr) + 1
        setattr(self, attr, v)
        return v

    def _crime_no(
        self, category_id: int, district_id: int, station_id: int, year: int
    ) -> tuple[str, str]:
        key = (category_id, district_id, station_id, year)
        serial = self._serial.get(key, 0) + 1
        self._serial[key] = serial
        crime_no = (
            f"{category_id:1d}{district_id:04d}{station_id % 10000:04d}{year:04d}{serial:05d}"
        )
        case_no = f"{year:04d}{serial:05d}"
        return crime_no, case_no

    # -- date chain ----------------------------------------------------------

    def _year(self) -> int:
        return self.rng.choices(list(YEAR_WEIGHTS), weights=list(YEAR_WEIGHTS.values()))[0]

    def _incident_dt(self, year: int) -> datetime:
        start = datetime(year, 1, 1)
        end = (
            datetime(year, 7, 18) if year == REFERENCE_NOW.year else datetime(year, 12, 31, 23, 59)
        )
        span = int((end - start).total_seconds())
        return start + timedelta(seconds=self.rng.randint(0, span))

    # -- main build ----------------------------------------------------------

    def build(self) -> Dataset:
        cases, occ, comps, victims, accuseds, assoc = [], [], [], [], [], []
        arrests, junction, chargesheets = [], [], []

        for _ in range(self.n):
            self._build_case(
                cases, occ, comps, victims, accuseds, assoc, arrests, junction, chargesheets
            )

        ds = Dataset()
        self._add_reference(ds)
        ds.add("ksp.case_master", CASE_COLS, cases)
        ds.add("ksp.inv_occurance_time", OCC_COLS, occ)
        ds.add("ksp.complainant_details", COMP_COLS, comps)
        ds.add("ksp.victim", VICTIM_COLS, victims)
        ds.add("ksp.accused", ACCUSED_COLS, accuseds)
        ds.add("ksp.act_section_association", ASSOC_COLS, assoc)
        ds.add("ksp.arrest_surrender", ARREST_COLS, arrests)
        ds.add("ksp.inv_arrest_surrender_accused", JUNCTION_COLS, junction)
        ds.add("ksp.chargesheet_details", CS_COLS, chargesheets)
        ds.ground_truth = self.registry.ground_truth()
        # MO signatures are generator-level (derived from BriefFacts), not person-level;
        # attach them so P15's MO clustering has an answer key to be scored against.
        ds.ground_truth["mo_by_case"] = self._mo_truth
        ds.ground_truth["n_mo_signatures"] = len(set(self._mo_truth.values()))
        return ds

    def _build_case(
        self, cases, occ, comps, victims, accuseds, assoc, arrests, junction, chargesheets
    ) -> None:
        ct = self.rng.choices(nv.CRIME_TYPES, weights=[_crime_weight(c) for c in nv.CRIME_TYPES])[0]
        station = self.rng.choice(self.stations)
        district = station.district
        year = self._year()

        # ~4% of FIRs are Zero FIRs — registered at a station outside where it happened.
        is_zero_fir = ct.category_id == 1 and self.rng.random() < 0.04
        category_id = 8 if is_zero_fir else ct.category_id

        case_id = self._next("_case_id")
        crime_no, case_no = self._crime_no(category_id, district.district_id, station.unit_id, year)

        incident = self._incident_dt(year)
        info_delay = self.rng.choices([0, 1, 2, 7, 30], weights=[45, 30, 12, 8, 5])[0]
        info_received = incident + timedelta(days=info_delay, hours=self.rng.randint(0, 12))
        # Registration lag — usually same/next day, sometimes the pathological delay
        # that the registration-integrity metric (P4.6) is meant to surface.
        reg_lag = self.rng.choices([0, 1, 3, 10, 45], weights=[55, 28, 9, 5, 3])[0]
        registered = min((info_received + timedelta(days=reg_lag)).date(), REFERENCE_NOW)
        # Keep the chain monotonic under the REFERENCE_NOW cap: a recent incident's
        # info-received timestamp can otherwise overshoot the capped registration date.
        if info_received.date() > registered:
            info_received = datetime.combine(registered, time(hour=self.rng.randint(8, 20)))
        if incident > info_received:
            incident = info_received - timedelta(hours=self.rng.randint(1, 6))
        incident_to = min(incident + timedelta(hours=self.rng.randint(0, 6)), info_received)

        lat, lon = self._coords(district)
        io_id = self.rng.choice(self._station_ios.get(station.unit_id, [1]))
        court_id = district.district_id  # one court per district, id == district_id
        brief, mo_sig = nv.render_brief_facts(ct, self.rng)
        self._mo_truth[case_id] = mo_sig

        # outcome decided first; it drives arrests and chargesheet below
        outcome = self._outcome(ct, registered)

        status_id = {"A": 2, "C": 3, "B": 4, "OPEN": 1}[outcome]
        cases.append(
            (
                case_id,
                crime_no,
                case_no,
                registered,
                io_id,
                station.unit_id,
                category_id,
                ct.gravity_id,
                ct.crime_head_id,
                ct.sub_head_id,
                status_id,
                court_id,
                incident,
                incident_to,
                info_received,
                lat,
                lon,
                brief,
            )
        )

        # occurrence-time record for a subset of cases
        if self.rng.random() < 0.5:
            occ.append(
                (
                    case_id,
                    incident,
                    incident_to,
                    f"Near {self.rng.choice(district.taluks)}",
                    lat,
                    lon,
                    self.rng.randint(1, 40),
                    round(self.rng.uniform(0.2, 12.0), 2),
                )
            )

        # ---- parties --------------------------------------------------------
        comp_person = self.registry.draw_complainant()
        comp_id = self._next("_complainant_id")
        comp_age = _age(comp_person, year, self.rng)
        comp_person.record("complainant", comp_id, case_id, comp_age)
        comps.append(
            (
                comp_id,
                case_id,
                render_variant(comp_person.parts, self.rng),
                comp_age,
                self.rng.randint(1, 9),
                self.rng.randint(1, 5),
                self.rng.randint(1, 5),
                comp_person.gender_id,
            )
        )

        n_victims = _victim_count(ct, self.rng)
        for _ in range(n_victims):
            vp = self.registry.draw_victim()
            vid = self._next("_victim_id")
            vage = _age(vp, year, self.rng)
            vp.record("victim", vid, case_id, vage)
            victims.append(
                (vid, case_id, render_variant(vp.parts, self.rng), vage, vp.gender_id, False)
            )

        n_accused = _accused_count(ct, outcome, self.rng)
        case_accused_ids: list[int] = []
        if n_accused:
            group = self.registry.draw_accused_group(n_accused)
            for i, ap in enumerate(group, start=1):
                aid = self._next("_accused_id")
                aage = _age(ap, year, self.rng)
                ap.record("accused", aid, case_id, aage)
                accuseds.append(
                    (aid, case_id, render_variant(ap.parts, self.rng), aage, ap.gender_id, f"A{i}")
                )
                case_accused_ids.append(aid)

        # ---- act/section ----------------------------------------------------
        for a_order, (act_code, section_code) in enumerate(ct.sections, start=1):
            assoc.append((case_id, act_code, section_code, a_order, a_order))

        # ---- arrest + junction ---------------------------------------------
        arrested = self._maybe_arrest(
            outcome, registered, case_id, case_accused_ids, station, district, io_id, court_id
        )
        if arrested is not None:
            arrest_row, arrested_ids = arrested
            arrests.append(arrest_row)
            arrest_id = arrest_row[0]
            for aid in arrested_ids:
                junction.append((arrest_id, aid))
            arrest_date = arrest_row[3]
        else:
            arrest_date = None

        # ---- chargesheet ----------------------------------------------------
        if outcome in ("A", "B", "C"):
            cs_id = self._next("_cs_id")
            base = arrest_date or registered
            cs_date = datetime.combine(base, datetime.min.time()) + timedelta(
                days=self.rng.randint(20, 120), hours=self.rng.randint(0, 23)
            )
            cs_date = min(cs_date, datetime.combine(REFERENCE_NOW, datetime.min.time()))
            chargesheets.append((cs_id, case_id, cs_date, outcome, io_id))

    # -- helpers -------------------------------------------------------------

    def _coords(self, district: ka.District) -> tuple[float | None, float | None]:
        # ~58% of rows have no precise GPS — the heavy-null reality the plan warns of.
        if self.rng.random() < 0.58:
            return None, None
        lat = round(district.lat + self.rng.uniform(-0.18, 0.18), 7)
        lon = round(district.lon + self.rng.uniform(-0.18, 0.18), 7)
        return lat, lon

    def _outcome(self, ct: nv.CrimeType, registered: date) -> str:
        # Recent cases are more likely still open; older ones have closed.
        age_days = (REFERENCE_NOW - registered).days
        open_prob = 0.55 if age_days < 120 else (0.30 if age_days < 400 else 0.12)
        if self.rng.random() < open_prob:
            return "OPEN"
        return self.rng.choices(("A", "B", "C"), weights=ct.cstype_weights)[0]

    def _maybe_arrest(
        self, outcome, registered, case_id, accused_ids, station, district, io_id, court_id
    ):
        if not accused_ids:
            return None
        arrest_prob = {"A": 0.9, "B": 0.2, "C": 0.15, "OPEN": 0.32}[outcome]
        if self.rng.random() > arrest_prob:
            return None

        if outcome == "OPEN" and self.rng.random() < 0.5:
            # danger-band cohort: arrested recently, chargesheet still pending
            days_ago = self.rng.randint(55, 95)
            arrest_date = REFERENCE_NOW - timedelta(days=days_ago)
            if arrest_date < registered:
                arrest_date = registered + timedelta(days=self.rng.randint(1, 10))
        else:
            arrest_date = registered + timedelta(days=self.rng.randint(1, 60))
        arrest_date = min(arrest_date, REFERENCE_NOW)

        # arrest a subset (often all) of the accused, sharing one event
        k = len(accused_ids) if self.rng.random() < 0.7 else self.rng.randint(1, len(accused_ids))
        arrested_ids = self.rng.sample(accused_ids, k)
        arrest_id = self._next("_arrest_id")
        row = (
            arrest_id,
            case_id,
            1,
            arrest_date,
            ka.KARNATAKA_STATE_ID,
            district.district_id,
            station.unit_id,
            io_id,
            court_id,
            arrested_ids[0],
            True,
            False,
        )
        return row, arrested_ids

    # -- reference tables ----------------------------------------------------

    def _add_reference(self, ds: Dataset) -> None:
        ds.add(
            "ksp.state",
            ("state_id", "state_name", "nationality_id", "active"),
            [(ka.KARNATAKA_STATE_ID, "Karnataka", 1, True)],
        )
        ds.add(
            "ksp.district",
            ("district_id", "district_name", "state_id", "active"),
            [(d.district_id, d.name, ka.KARNATAKA_STATE_ID, True) for d in ka.DISTRICTS],
        )
        ds.add(
            "ksp.unit_type",
            ("unit_type_id", "unit_type_name", "city_dist_state", "hierarchy", "active"),
            [(u[0], u[1], u[2], u[3], True) for u in ka.UNIT_TYPES],
        )
        ds.add(
            "ksp.unit",
            (
                "unit_id",
                "unit_name",
                "type_id",
                "parent_unit",
                "nationality_id",
                "state_id",
                "district_id",
            ),
            self.ref.units,
        )
        ds.add(
            "ksp.rank",
            ("rank_id", "rank_name", "hierarchy", "active"),
            [(r[0], r[1], r[2], True) for r in ka.RANKS],
        )
        ds.add(
            "ksp.designation",
            ("designation_id", "designation_name", "sort_order", "active"),
            [(d[0], d[1], d[2], True) for d in ka.DESIGNATIONS],
        )
        ds.add(
            "ksp.employee",
            (
                "employee_id",
                "district_id",
                "unit_id",
                "rank_id",
                "designation_id",
                "kgid",
                "first_name",
                "gender_id",
            ),
            self.ref.employees,
        )
        ds.add("ksp.court", ("court_id", "court_name", "district_id", "state_id"), self.ref.courts)
        ds.add("ksp.act", ("act_code", "act_description", "short_name"), list(ka.ACTS))
        ds.add(
            "ksp.section", ("act_code", "section_code", "section_description"), list(ka.SECTIONS)
        )
        ds.add("ksp.crime_head", ("crime_head_id", "crime_group_name"), list(ka.CRIME_HEADS))
        ds.add(
            "ksp.crime_sub_head",
            ("crime_sub_head_id", "crime_head_id", "crime_head_name", "seq_id"),
            [
                (c.sub_head_id, c.crime_head_id, c.sub_head_name, i)
                for i, c in enumerate(nv.CRIME_TYPES, 1)
            ],
        )
        chas = sorted({(c.crime_head_id, a, s) for c in nv.CRIME_TYPES for (a, s) in c.sections})
        ds.add("ksp.crime_head_act_section", ("crime_head_id", "act_code", "section_code"), chas)
        ds.add("ksp.gravity_offence", ("gravity_offence_id", "lookup_value"), list(ka.GRAVITY))
        ds.add(
            "ksp.case_status_master", ("case_status_id", "case_status_name"), list(ka.CASE_STATUSES)
        )
        ds.add("ksp.caste_master", ("caste_master_id", "caste_master_name"), list(ka.CASTES))
        ds.add("ksp.religion_master", ("religion_id", "religion_name"), list(ka.RELIGIONS))
        ds.add("ksp.occupation_master", ("occupation_id", "occupation_name"), list(ka.OCCUPATIONS))


# --- module-level column definitions and small helpers -----------------------

CASE_COLS = (
    "case_master_id",
    "crime_no",
    "case_no",
    "crime_registered_date",
    "police_person_id",
    "police_station_id",
    "case_category_id",
    "gravity_offence_id",
    "crime_major_head_id",
    "crime_minor_head_id",
    "case_status_id",
    "court_id",
    "incident_from_date",
    "incident_to_date",
    "info_received_ps_date",
    "latitude",
    "longitude",
    "brief_facts",
)
OCC_COLS = (
    "case_master_id",
    "occurrence_from",
    "occurrence_to",
    "place_of_offence",
    "latitude",
    "longitude",
    "beat_id",
    "distance_from_ps",
)
COMP_COLS = (
    "complainant_id",
    "case_master_id",
    "complainant_name",
    "age_year",
    "occupation_id",
    "religion_id",
    "caste_id",
    "gender_id",
)
VICTIM_COLS = (
    "victim_master_id",
    "case_master_id",
    "victim_name",
    "age_year",
    "gender_id",
    "victim_police",
)
ACCUSED_COLS = (
    "accused_master_id",
    "case_master_id",
    "accused_name",
    "age_year",
    "gender_id",
    "person_id",
)
ASSOC_COLS = ("case_master_id", "act_code", "section_code", "act_order_id", "section_order_id")
ARREST_COLS = (
    "arrest_surrender_id",
    "case_master_id",
    "arrest_surrender_type_id",
    "arrest_surrender_date",
    "arrest_surrender_state_id",
    "arrest_surrender_district_id",
    "police_station_id",
    "io_id",
    "court_id",
    "accused_master_id",
    "is_accused",
    "is_complainant_accused",
)
JUNCTION_COLS = ("arrest_surrender_id", "accused_master_id")
CS_COLS = ("cs_id", "case_master_id", "cs_date", "cs_type", "police_person_id")


def _crime_weight(c: nv.CrimeType) -> float:
    # property/body crimes dominate the volume; murder and NDPS are rarer.
    heavy = {101: 3.0, 102: 2.5, 103: 2.2, 106: 2.0, 108: 1.8, 107: 1.3, 104: 1.1, 109: 0.9}
    return heavy.get(c.sub_head_id, 0.6)


def _victim_count(ct: nv.CrimeType, rng) -> int:
    if ct.crime_head_id in (2, 4):  # property / economic — often no distinct victim row
        return rng.choices([0, 1], weights=[55, 45])[0]
    if ct.sub_head_id == 111:  # UDR: the deceased
        return 1
    return rng.choices([1, 2, 3], weights=[75, 18, 7])[0]


def _accused_count(ct: nv.CrimeType, outcome: str, rng) -> int:
    if ct.sub_head_id == 111:  # UDR usually has no accused
        return rng.choices([0, 1], weights=[85, 15])[0]
    if outcome == "C":  # undetected — accused unknown
        return rng.choices([0, 1], weights=[70, 30])[0]
    return rng.choices([1, 2, 3, 4], weights=[52, 28, 14, 6])[0]


def _age(person, case_year: int, rng) -> int:
    true_age = case_year - person.birth_year
    return max(15, true_age + rng.randint(-2, 2))  # ±2y drift, the AgeYear noise
