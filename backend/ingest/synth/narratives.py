"""The crime catalogue and BriefFacts narrative generator.

Two jobs:

1. **Crime catalogue** — maps each crime sub-head to its head, gravity, the
   acts/sections it invokes, a realistic cstype (outcome) distribution, and the
   set of modus-operandi templates it can draw from. This is what makes the
   generated cases internally consistent (a chain-snatching gets IPC 379/356,
   not IPC 302).

2. **MO signatures** — there is no modus-operandi field in the KSP schema; MO
   has to be *derived* from BriefFacts free text later (P15). So the narratives
   carry recognisable, repeated MO phrasing. Each MO template keeps its signature
   words stable across English, Kannada-script, and transliterated renderings so
   that an embedding model has real, clusterable signal to find — and the hidden
   ``mo_signature`` we tag each case with is the ground truth P15 can be scored on.
"""

from __future__ import annotations

from dataclasses import dataclass

# Language mix seen in real Karnataka FIR BriefFacts.
LANG_WEIGHTS = {"en": 0.45, "translit": 0.30, "kn": 0.25}


@dataclass(frozen=True)
class MoTemplate:
    signature: str  # hidden ground-truth MO id (never written to ksp)
    en: str
    translit: str
    kn: str


@dataclass(frozen=True)
class CrimeType:
    sub_head_id: int
    sub_head_name: str
    crime_head_id: int
    gravity_id: int  # 1 heinous, 2 non-heinous
    sections: tuple[tuple[str, str], ...]
    # outcome weights over cstype A (chargesheet), B (false), C (undetected)
    cstype_weights: tuple[float, float, float]
    mo: tuple[MoTemplate, ...]
    # category digit for CrimeNo: 1 FIR, 3 UDR. Zero-FIR (8) is applied separately.
    category_id: int = 1


_SLOTS = {
    "place": (
        "Majestic",
        "the market road",
        "the bus stand",
        "an isolated lane",
        "the highway",
        "the temple street",
        "the layout",
        "the industrial area",
    ),
    "vehicle": ("motorcycle", "Pulsar bike", "scooter", "auto-rickshaw", "white car"),
    "weapon": ("machete", "iron rod", "wooden club", "knife", "sickle"),
    "item": ("gold chain", "mangalsutra", "gold bangles", "mobile phone", "cash"),
    "drug": ("ganja", "MDMA tablets", "brown sugar"),
}


CRIME_TYPES: tuple[CrimeType, ...] = (
    CrimeType(
        101,
        "Chain Snatching",
        2,
        2,
        (("IPC", "379"), ("IPC", "356")),
        (0.35, 0.10, 0.55),
        (
            MoTemplate(
                "mo_chain_snatch_bike",
                "Two unknown persons came on a {vehicle}, snatched the {item} from the "
                "complainant near {place} and fled towards the main road.",
                "Ibbaru identify aagada persons {vehicle} nalli bandu {place} hattira "
                "complainant-na {item} kittkondu paar aadru.",
                "ಇಬ್ಬರು ಅಪರಿಚಿತ ವ್ಯಕ್ತಿಗಳು ದ್ವಿಚಕ್ರ ವಾಹನದಲ್ಲಿ ಬಂದು ಫಿರ್ಯಾದಿಯ ಚಿನ್ನದ ಸರವನ್ನು ಕಿತ್ತುಕೊಂಡು ಪರಾರಿಯಾದರು.",
            ),
        ),
    ),
    CrimeType(
        102,
        "House Burglary",
        2,
        2,
        (("IPC", "457"), ("IPC", "380")),
        (0.30, 0.08, 0.62),
        (
            MoTemplate(
                "mo_burglary_ventilator",
                "The accused broke open the rear ventilator during night hours, entered "
                "the locked house at {place} and decamped with {item} and household articles.",
                "Accused rathri hottu manege rear ventilator odedu, {place} inda lock "
                "maadida manege nuggi {item} mattu manege saamanu kalavu maadidaru.",
                "ಆರೋಪಿಗಳು ರಾತ್ರಿ ವೇಳೆ ಮನೆಯ ಹಿಂಬಾಗದ ಗವಾಕ್ಷಿಯನ್ನು ಒಡೆದು, ಬೀಗ ಹಾಕಿದ ಮನೆಯೊಳಗೆ "
                "ಪ್ರವೇಶಿಸಿ ಚಿನ್ನಾಭರಣ ಮತ್ತು ಸಾಮಗ್ರಿಗಳನ್ನು ಕಳವು ಮಾಡಿದ್ದಾರೆ.",
            ),
        ),
    ),
    CrimeType(
        103,
        "Motor Vehicle Theft",
        2,
        2,
        (("IPC", "379"),),
        (0.20, 0.05, 0.75),
        (
            MoTemplate(
                "mo_vehicle_theft_parked",
                "The complainant parked the {vehicle} near {place} and on returning found "
                "it missing. Unknown accused committed the theft.",
                "Complainant {vehicle}-annu {place} hattira park maadi, vaapas bandaga "
                "adu illa antha gottaytu. Identify aagada accused kalavu maadiddare.",
                "ಫಿರ್ಯಾದಿ ತಮ್ಮ ವಾಹನವನ್ನು ನಿಲ್ಲಿಸಿ ಹಿಂತಿರುಗಿ ಬಂದಾಗ ಅದು ಕಾಣೆಯಾಗಿತ್ತು. ಅಪರಿಚಿತ ಆರೋಪಿಗಳು ಕಳವು ಮಾಡಿದ್ದಾರೆ.",
            ),
        ),
    ),
    CrimeType(
        104,
        "Robbery",
        2,
        1,
        (("IPC", "392"), ("IPC", "324")),
        (0.45, 0.08, 0.47),
        (
            MoTemplate(
                "mo_robbery_threat",
                "The accused waylaid the complainant at {place}, threatened with a {weapon} "
                "and forcibly robbed {item}.",
                "Accused {place} nalli complainant-na taddu {weapon} torisi hedarisi "
                "{item} kittkondu hogiddare.",
                "ಆರೋಪಿಗಳು ಫಿರ್ಯಾದಿಯನ್ನು ತಡೆದು ಮಾರಕಾಸ್ತ್ರ ತೋರಿಸಿ ಬೆದರಿಸಿ ಬಲವಂತವಾಗಿ ದೋಚಿಕೊಂಡು ಹೋಗಿದ್ದಾರೆ.",
            ),
        ),
    ),
    CrimeType(
        105,
        "Murder",
        1,
        1,
        (("IPC", "302"),),
        (0.62, 0.03, 0.35),
        (
            MoTemplate(
                "mo_murder_landdispute",
                "Over a long-standing land dispute the accused attacked the deceased with a "
                "{weapon} at {place}, causing fatal injuries.",
                "Bahala dinada jaga vivaadadinda accused deceased-na {weapon} inda "
                "{place} nalli hodedu sayisiddare.",
                "ದೀರ್ಘಕಾಲದ ಜಮೀನು ವಿವಾದದ ಹಿನ್ನೆಲೆಯಲ್ಲಿ ಆರೋಪಿಗಳು ಮೃತನಿಗೆ ಮಾರಕಾಸ್ತ್ರದಿಂದ ಹಲ್ಲೆ ಮಾಡಿ ಕೊಲೆ ಮಾಡಿದ್ದಾರೆ.",
            ),
        ),
    ),
    CrimeType(
        106,
        "Drunken Assault",
        1,
        2,
        (("IPC", "323"), ("IPC", "324")),
        (0.55, 0.15, 0.30),
        (
            MoTemplate(
                "mo_assault_drunken",
                "Under the influence of alcohol the accused picked a quarrel at {place} and "
                "assaulted the complainant with a {weapon}.",
                "Kudididdu accused {place} nalli jagala tegedu complainant-na {weapon} "
                "inda hodedidaare.",
                "ಮದ್ಯಪಾನ ಮಾಡಿದ್ದ ಆರೋಪಿ ಜಗಳ ತೆಗೆದು ಫಿರ್ಯಾದಿಗೆ ಮಾರಕಾಸ್ತ್ರದಿಂದ ಹಲ್ಲೆ ಮಾಡಿದ್ದಾನೆ.",
            ),
        ),
    ),
    CrimeType(
        107,
        "Dowry Harassment",
        3,
        2,
        (("IPC", "498A"),),
        (0.50, 0.20, 0.30),
        (
            MoTemplate(
                "mo_dowry_harassment",
                "The accused husband and in-laws subjected the complainant to cruelty and "
                "harassed her for additional dowry of cash and gold.",
                "Accused ganda mattu manedavaru complainant-ge cruelty maadi hechina "
                "varadakshine cash mattu chinnakkagi harass maadiddare.",
                "ಆರೋಪಿ ಗಂಡ ಮತ್ತು ಅತ್ತೆ ಮನೆಯವರು ಹೆಚ್ಚಿನ ವರದಕ್ಷಿಣೆಗಾಗಿ ಫಿರ್ಯಾದಿಗೆ ಕಿರುಕುಳ ನೀಡಿದ್ದಾರೆ.",
            ),
        ),
    ),
    CrimeType(
        108,
        "Online Fraud",
        4,
        2,
        (("IPC", "420"), ("ITA", "66D")),
        (0.18, 0.07, 0.75),
        (
            MoTemplate(
                "mo_fraud_otp",
                "The complainant received a call from an unknown number, was induced to "
                "share the OTP, and a sum was fraudulently debited from the bank account.",
                "Complainant-ge unknown number inda call bandu, OTP share maadsi, bank "
                "account inda hana fraud aagi debit aaytu.",
                "ಫಿರ್ಯಾದಿಗೆ ಅಪರಿಚಿತ ಸಂಖ್ಯೆಯಿಂದ ಕರೆ ಬಂದು, OTP ಹಂಚಿಕೊಳ್ಳುವಂತೆ ಮಾಡಿ, ಬ್ಯಾಂಕ್ "
                "ಖಾತೆಯಿಂದ ಹಣವನ್ನು ವಂಚನೆಯಿಂದ ಕಡಿತ ಮಾಡಲಾಗಿದೆ.",
            ),
        ),
    ),
    CrimeType(
        109,
        "Rioting",
        6,
        2,
        (("IPC", "147"),),
        (0.40, 0.18, 0.42),
        (
            MoTemplate(
                "mo_rioting_unlawful",
                "An unlawful assembly at {place} armed with {weapon}s indulged in rioting "
                "and damaged public property.",
                "{place} nalli {weapon} hididu unlawful assembly serida gumpu galata maadi "
                "public property hana maadidaru.",
                "ಕಾನೂನುಬಾಹಿರ ಗುಂಪು ಮಾರಕಾಸ್ತ್ರಗಳೊಂದಿಗೆ ಸೇರಿ ಗಲಭೆ ನಡೆಸಿ ಸಾರ್ವಜನಿಕ ಆಸ್ತಿಗೆ ಹಾನಿ ಮಾಡಿದ್ದಾರೆ.",
            ),
        ),
    ),
    CrimeType(
        110,
        "NDPS - Ganja",
        7,
        1,
        (("NDPS", "20"),),
        (0.70, 0.05, 0.25),
        (
            MoTemplate(
                "mo_ndps_possession",
                "During a routine check at {place} the accused was found in possession of "
                "{drug} concealed in a bag, without any valid permit.",
                "{place} nalli routine check maadidaga accused bag nalli {drug} conceal "
                "maadi valid permit illade siktvidaare.",
                "ವಾಡಿಕೆ ತಪಾಸಣೆ ವೇಳೆ ಆರೋಪಿಯು ಚೀಲದಲ್ಲಿ ಅಡಗಿಸಿಟ್ಟ ಗಾಂಜಾವನ್ನು ಯಾವುದೇ ಪರವಾನಗಿ ಇಲ್ಲದೆ ಹೊಂದಿದ್ದು ಕಂಡುಬಂದಿದೆ.",
            ),
        ),
    ),
    CrimeType(
        111,
        "Unnatural Death",
        8,
        2,
        (("IPC", "174"),),
        (0.10, 0.05, 0.85),
        (
            MoTemplate(
                "mo_udr_found",
                "The deceased was found dead under unnatural circumstances at {place}. "
                "Cause of death to be ascertained after post-mortem. UDR registered.",
                "Deceased-annu {place} nalli unnatural circumstances alli sattaddu "
                "sikkide. Post-mortem nantara cause of death gottaguttade.",
                "ಮೃತ ವ್ಯಕ್ತಿಯು ಅಸಹಜ ಸಂದರ್ಭದಲ್ಲಿ ಮೃತಪಟ್ಟಿರುವುದು ಕಂಡುಬಂದಿದೆ. ಮರಣೋತ್ತರ ಪರೀಕ್ಷೆಯ "
                "ನಂತರ ಸಾವಿನ ಕಾರಣ ತಿಳಿಯಲಿದೆ.",
            ),
        ),
        category_id=3,  # UDR
    ),
)


def render_brief_facts(ct: CrimeType, rng) -> tuple[str, str]:
    """Return (brief_facts_text, mo_signature). The signature is ground truth for
    P15 and is written only to the ground-truth file, never to ksp.case_master."""
    mo = rng.choice(ct.mo)
    lang = rng.choices(list(LANG_WEIGHTS), weights=list(LANG_WEIGHTS.values()))[0]
    template = {"en": mo.en, "translit": mo.translit, "kn": mo.kn}[lang]
    filled = _fill_slots(template, rng)
    return filled, mo.signature


def _fill_slots(template: str, rng) -> str:
    out = template
    for slot, options in _SLOTS.items():
        token = "{" + slot + "}"
        while token in out:
            out = out.replace(token, rng.choice(options), 1)
    return out
