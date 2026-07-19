"""Karnataka reference data: geography, police organisation, and the legal framework.

This is the fixed backdrop the synthetic FIRs are generated against. Districts and
their approximate centroids are real; police-station names are plausible rather than
official. The legal framework covers only the acts/sections the crime catalogue in
``narratives`` actually invokes — it is not the full IPC/BNS.

IDs are assigned here so the generator and the CrimeNo builder agree on them. District
IDs and unit (station) IDs are what the 4-digit CrimeNo segments encode.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# -----------------------------------------------------------------------------
# Geography — real Karnataka districts with approximate centroids (lat, lon).
# The centroid is the fallback location a case gets when it has no precise GPS,
# and the jitter radius keeps generated points inside a believable district box.
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class District:
    district_id: int
    name: str
    lat: float
    lon: float
    taluks: tuple[str, ...]


DISTRICTS: tuple[District, ...] = (
    District(
        1,
        "Bengaluru Urban",
        12.9716,
        77.5946,
        ("Bengaluru North", "Bengaluru South", "Anekal", "Yelahanka"),
    ),
    District(
        2,
        "Bengaluru Rural",
        13.2846,
        77.6200,
        ("Devanahalli", "Doddaballapura", "Hoskote", "Nelamangala"),
    ),
    District(3, "Mysuru", 12.2958, 76.6394, ("Mysuru", "Nanjangud", "T Narasipura", "Hunsur")),
    District(4, "Mandya", 12.5223, 76.8954, ("Mandya", "Maddur", "Malavalli", "Srirangapatna")),
    District(
        5, "Ramanagara", 12.7217, 77.2807, ("Ramanagara", "Channapatna", "Kanakapura", "Magadi")
    ),
    District(6, "Tumakuru", 13.3379, 77.1173, ("Tumakuru", "Tiptur", "Sira", "Madhugiri")),
    District(
        7, "Hassan", 13.0057, 76.0962, ("Hassan", "Arsikere", "Channarayapatna", "Sakleshpura")
    ),
    District(8, "Kolar", 13.1367, 78.1292, ("Kolar", "Malur", "Bangarpet", "Mulbagal")),
    District(
        9,
        "Chikkaballapura",
        13.4355,
        77.7315,
        ("Chikkaballapura", "Sidlaghatta", "Chintamani", "Gauribidanur"),
    ),
    District(
        10, "Davanagere", 14.4644, 75.9218, ("Davanagere", "Harihara", "Channagiri", "Honnali")
    ),
    District(11, "Ballari", 15.1394, 76.9214, ("Ballari", "Hospet", "Siruguppa", "Sandur")),
    District(12, "Belagavi", 15.8497, 74.4977, ("Belagavi", "Gokak", "Chikkodi", "Bailhongal")),
    District(13, "Dharwad", 15.4589, 75.0078, ("Dharwad", "Hubballi", "Kalghatgi", "Kundgol")),
    District(14, "Kalaburagi", 17.3297, 76.8343, ("Kalaburagi", "Sedam", "Aland", "Chittapur")),
    District(
        15, "Vijayapura", 16.8302, 75.7100, ("Vijayapura", "Indi", "Sindagi", "Basavana Bagevadi")
    ),
    District(
        16, "Shivamogga", 13.9299, 75.5681, ("Shivamogga", "Bhadravati", "Sagar", "Shikaripura")
    ),
    District(17, "Udupi", 13.3409, 74.7421, ("Udupi", "Kundapura", "Karkala", "Byndoor")),
    District(
        18, "Dakshina Kannada", 12.9141, 74.8560, ("Mangaluru", "Bantwal", "Puttur", "Sullia")
    ),
    District(
        19, "Chitradurga", 14.2251, 76.3980, ("Chitradurga", "Hiriyur", "Challakere", "Molakalmuru")
    ),
    District(20, "Raichur", 16.2076, 77.3463, ("Raichur", "Sindhanur", "Manvi", "Devadurga")),
    District(21, "Koppal", 15.3547, 76.1548, ("Koppal", "Gangavathi", "Yelburga", "Kushtagi")),
    District(22, "Bagalkote", 16.1691, 75.6615, ("Bagalkote", "Jamkhandi", "Mudhol", "Badami")),
    District(
        23, "Chikkamagaluru", 13.3161, 75.7720, ("Chikkamagaluru", "Kadur", "Tarikere", "Mudigere")
    ),
    District(24, "Kodagu", 12.4244, 75.7382, ("Madikeri", "Virajpet", "Somwarpet", "Kushalnagar")),
    District(25, "Uttara Kannada", 14.8183, 74.1300, ("Karwar", "Sirsi", "Kumta", "Bhatkal")),
    District(26, "Haveri", 14.7935, 75.4044, ("Haveri", "Ranebennur", "Byadgi", "Hangal")),
    District(27, "Gadag", 15.4290, 75.6296, ("Gadag", "Ron", "Nargund", "Shirahatti")),
    District(28, "Yadgir", 16.7690, 77.1370, ("Yadgir", "Shahapur", "Surapura", "Gurmitkal")),
    District(29, "Bidar", 17.9104, 77.5199, ("Bidar", "Basavakalyan", "Humnabad", "Bhalki")),
    District(
        30,
        "Chamarajanagar",
        11.9261,
        76.9438,
        ("Chamarajanagar", "Gundlupet", "Kollegal", "Yelandur"),
    ),
    District(
        31,
        "Vijayanagara",
        15.2730,
        76.3860,
        ("Hospet", "Hagaribommanahalli", "Kudligi", "Harapanahalli"),
    ),
)

KARNATAKA_STATE_ID = 29  # KA's real state code; arbitrary but stable here.

# Rough bounding box of Karnataka, used to place the occasional out-of-jurisdiction
# Zero FIR and to validate that generated coordinates land inside the state.
KA_BBOX = {"min_lat": 11.5, "max_lat": 18.5, "min_lon": 74.0, "max_lon": 78.6}


# -----------------------------------------------------------------------------
# Police organisation — rank and designation ladders drive RBAC scope later (P9).
# -----------------------------------------------------------------------------

UNIT_TYPES: tuple[tuple[int, str, str, int], ...] = (
    (1, "State Police Headquarters", "State", 1),
    (2, "Range Office", "State", 2),
    (3, "District Police Office", "District", 3),
    (4, "Sub-Division", "District", 4),
    (5, "Police Station", "City", 5),
)

# (rank_id, name, hierarchy) — lower hierarchy number = higher authority.
RANKS: tuple[tuple[int, str, int], ...] = (
    (1, "Director General of Police", 1),
    (2, "Inspector General of Police", 2),
    (3, "Superintendent of Police", 3),
    (4, "Deputy Superintendent of Police", 4),
    (5, "Police Inspector", 5),
    (6, "Sub-Inspector", 6),
    (7, "Head Constable", 7),
    (8, "Police Constable", 8),
)

DESIGNATIONS: tuple[tuple[int, str, int], ...] = (
    (1, "SHO", 1),
    (2, "Investigating Officer", 2),
    (3, "Beat Officer", 3),
)


# -----------------------------------------------------------------------------
# Legal framework — only the acts/sections the crime catalogue references.
# -----------------------------------------------------------------------------

ACTS: tuple[tuple[str, str, str], ...] = (
    ("IPC", "Indian Penal Code, 1860", "IPC"),
    ("BNS", "Bharatiya Nyaya Sanhita, 2023", "BNS"),
    ("NDPS", "Narcotic Drugs and Psychotropic Substances Act, 1985", "NDPS"),
    ("ITA", "Information Technology Act, 2000", "IT Act"),
    ("POCSO", "Protection of Children from Sexual Offences Act, 2012", "POCSO"),
)

# (act_code, section_code, description)
SECTIONS: tuple[tuple[str, str, str], ...] = (
    ("IPC", "302", "Punishment for murder"),
    ("IPC", "307", "Attempt to murder"),
    ("IPC", "323", "Voluntarily causing hurt"),
    ("IPC", "324", "Voluntarily causing hurt by dangerous weapons"),
    ("IPC", "354", "Assault on woman with intent to outrage modesty"),
    ("IPC", "356", "Assault in attempt to commit theft of property carried by a person"),
    ("IPC", "379", "Punishment for theft"),
    ("IPC", "380", "Theft in dwelling house"),
    ("IPC", "392", "Punishment for robbery"),
    ("IPC", "420", "Cheating and dishonestly inducing delivery of property"),
    ("IPC", "457", "Lurking house-trespass or house-breaking by night"),
    ("IPC", "498A", "Husband or relative subjecting a woman to cruelty"),
    ("IPC", "147", "Punishment for rioting"),
    ("IPC", "174", "Unnatural death — inquest (UDR)"),
    ("NDPS", "20", "Contravention in relation to cannabis"),
    ("NDPS", "22", "Contravention in relation to psychotropic substances"),
    ("ITA", "66C", "Identity theft"),
    ("ITA", "66D", "Cheating by personation using computer resource"),
    ("POCSO", "8", "Punishment for sexual assault"),
)

CRIME_HEADS: tuple[tuple[int, str], ...] = (
    (1, "Crimes Against Body"),
    (2, "Crimes Against Property"),
    (3, "Crimes Against Women"),
    (4, "Economic Offences"),
    (5, "Crimes Against Children"),
    (6, "Public Order"),
    (7, "Narcotics"),
    (8, "Miscellaneous"),
)

GRAVITY: tuple[tuple[int, str], ...] = ((1, "Heinous"), (2, "Non-Heinous"))

CASE_STATUSES: tuple[tuple[int, str], ...] = (
    (1, "Under Investigation"),
    (2, "Chargesheeted"),
    (3, "Closed - Undetected"),
    (4, "Closed - False"),
)

# Complainant-side demographics (the only place caste/religion/occupation exist).
CASTES: tuple[tuple[int, str], ...] = (
    (1, "General"),
    (2, "OBC"),
    (3, "SC"),
    (4, "ST"),
    (5, "Not Stated"),
)
RELIGIONS: tuple[tuple[int, str], ...] = (
    (1, "Hindu"),
    (2, "Muslim"),
    (3, "Christian"),
    (4, "Jain"),
    (5, "Other"),
)
OCCUPATIONS: tuple[tuple[int, str], ...] = (
    (1, "Agriculture"),
    (2, "Daily Wage Labour"),
    (3, "Business"),
    (4, "Government Service"),
    (5, "Private Employee"),
    (6, "Homemaker"),
    (7, "Student"),
    (8, "Unemployed"),
    (9, "Driver"),
)


@dataclass
class Station:
    unit_id: int
    name: str
    district: District
    parent_unit: int


@dataclass
class ReferenceData:
    """Everything seeded before cases. Stations and employees are generated so
    the counts scale with the district list rather than being hand-listed."""

    stations: list[Station] = field(default_factory=list)
    # unit rows include the higher formations, not just stations
    units: list[tuple] = field(default_factory=list)
    employees: list[tuple] = field(default_factory=list)
    courts: list[tuple] = field(default_factory=list)


def build_reference(rng) -> ReferenceData:
    """Construct stations, higher units, employees and courts for every district.

    Unit IDs are laid out so a station's ID is stable and 4-digit-encodable for the
    CrimeNo. State HQ = 1, one range office per district block is skipped for
    simplicity; each district gets a District Police Office and a handful of stations.
    """
    ref = ReferenceData()
    # State HQ
    ref.units.append((1, "Karnataka State Police HQ", 1, None, None, KARNATAKA_STATE_ID, None))

    next_unit_id = 100  # leave 2..99 free; stations start well clear of HQ
    next_emp_id = 1
    next_court_id = 1

    for d in DISTRICTS:
        dpo_id = next_unit_id
        next_unit_id += 1
        ref.units.append(
            (
                dpo_id,
                f"{d.name} District Police Office",
                3,
                1,
                None,
                KARNATAKA_STATE_ID,
                d.district_id,
            )
        )
        # One court per district.
        ref.courts.append(
            (
                next_court_id,
                f"{d.name} District & Sessions Court",
                d.district_id,
                KARNATAKA_STATE_ID,
            )
        )
        next_court_id += 1

        for taluk in d.taluks:
            for kind in ("Town", "Rural"):
                sid = next_unit_id
                next_unit_id += 1
                name = f"{taluk} {kind} PS"
                ref.units.append((sid, name, 5, dpo_id, None, KARNATAKA_STATE_ID, d.district_id))
                ref.stations.append(Station(sid, name, d, dpo_id))
                # Staff: one SHO (Inspector) + a couple of SIs per station act as IOs.
                for rank_id, desig_id in ((5, 1), (6, 2), (6, 2)):
                    ref.employees.append(
                        (
                            next_emp_id,
                            d.district_id,
                            sid,
                            rank_id,
                            desig_id,
                            f"KGID{next_emp_id:06d}",
                            _officer_name(rng),
                            1,
                        )
                    )
                    next_emp_id += 1

    return ref


_OFFICER_GIVEN = (
    "Manjunath",
    "Basavaraj",
    "Srinivas",
    "Venkatesh",
    "Nagaraj",
    "Prakash",
    "Shivakumar",
    "Ramesh",
    "Girish",
    "Harish",
    "Lokesh",
    "Chandrashekar",
    "Mahadev",
    "Ravi",
    "Umesh",
)


def _officer_name(rng) -> str:
    return rng.choice(_OFFICER_GIVEN)
