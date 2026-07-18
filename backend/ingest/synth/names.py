"""Kannada-origin name pools and the corruption machinery.

The whole point of the synthetic data is that a single real person recurs across
FIRs written *differently each time*. This module owns both halves: a pool of
canonical names to build the ground-truth registry from, and the deliberate
corruption that turns one canonical identity into the messy variants the entity
resolution pipeline has to see through.

Corruption types injected (each independently, so a variant may stack several):
  - terminal-vowel drift:      Ramesh / Ramesha / Rameshu
  - Dravidian suffix swap:     -appa / -anna / -amma, -gowda variants
  - transliteration variance:  sh<->s, th<->t, v<->w, doubled letters, oo/u, ee/i
  - "@" alias:                 "Ramesh @ Rami"
  - patronymic present/absent: "S/o Krishnappa" sometimes dropped entirely
  - honorific noise:           "Sri", "Smt", "Mr" prefixes

Nothing here reads the ground truth back; it only writes variants. The registry
records which source rows belong to which canonical person.
"""

from __future__ import annotations

from dataclasses import dataclass

MALE_GIVEN = (
    "Ramesh",
    "Suresh",
    "Mahesh",
    "Ganesh",
    "Naveen",
    "Manjunath",
    "Shivakumar",
    "Basavaraj",
    "Prakash",
    "Ravi",
    "Nagaraj",
    "Srinivas",
    "Venkatesh",
    "Krishna",
    "Chandru",
    "Lokesh",
    "Girish",
    "Harish",
    "Santosh",
    "Vinod",
    "Anand",
    "Umesh",
    "Prashanth",
    "Kiran",
    "Gopal",
    "Mallesh",
    "Chetan",
    "Darshan",
    "Yogesh",
    "Raju",
    "Mahadev",
    "Nagendra",
    "Shankar",
    "Vijay",
    "Ashok",
    "Rajesh",
    "Praveen",
    "Kumar",
)

FEMALE_GIVEN = (
    "Lakshmi",
    "Geetha",
    "Savitha",
    "Manjula",
    "Roopa",
    "Divya",
    "Pooja",
    "Nagaratna",
    "Shobha",
    "Bhavya",
    "Kavya",
    "Ashwini",
    "Sowmya",
    "Deepa",
    "Rekha",
    "Vidya",
    "Sunitha",
    "Anitha",
    "Jyothi",
    "Ramya",
    "Chaitra",
    "Meena",
    "Padma",
    "Sushma",
    "Vani",
    "Nethra",
    "Bhagya",
    "Yashoda",
    "Sridevi",
    "Mamatha",
)

# Patronymics skew toward the -appa / -anna / -gowda forms common in the state.
PATRONYMICS = (
    "Krishnappa",
    "Nanjappa",
    "Basavanna",
    "Siddappa",
    "Mallappa",
    "Hanumantha",
    "Ramegowda",
    "Kempegowda",
    "Thimmappa",
    "Ninganna",
    "Gangadhar",
    "Shivappa",
    "Doddappa",
    "Chikkanna",
    "Muniyappa",
    "Boraiah",
    "Rangappa",
    "Venkatappa",
    "Honnappa",
    "Lingappa",
    "Marappa",
    "Chennappa",
    "Gundappa",
    "Puttaswamy",
)

HONORIFICS = ("Sri", "Smt", "Mr", "Kum")

RELATIONS = ("S/o", "D/o", "W/o", "C/o")


@dataclass
class NameParts:
    """The canonical, uncorrupted identity of a ground-truth person."""

    given: str
    patronymic: str
    relation: str
    alias: str | None


def make_alias(given: str, rng) -> str:
    """A short informal handle, the thing the '@' convention records."""
    stem = given[: max(3, len(given) // 2)]
    return rng.choice([stem, stem + "u", stem + "i", given[:4]])


def canonical_name(gender_id: int, rng) -> NameParts:
    """Draw a fresh canonical identity."""
    given = rng.choice(MALE_GIVEN if gender_id == 1 else FEMALE_GIVEN)
    relation = (
        "W/o" if (gender_id == 2 and rng.random() < 0.4) else ("D/o" if gender_id == 2 else "S/o")
    )
    alias = make_alias(given, rng) if rng.random() < 0.35 else None
    return NameParts(
        given=given, patronymic=rng.choice(PATRONYMICS), relation=relation, alias=alias
    )


# --- corruption primitives ---------------------------------------------------

_VOWEL_TAILS = ("", "a", "u", "appa", "anna")
_TRANSLIT_SUBS = (
    ("sh", "s"),
    ("th", "t"),
    ("dh", "d"),
    ("v", "w"),
    ("ph", "f"),
    ("ee", "i"),
    ("oo", "u"),
    ("ksh", "x"),
)


def _drift_terminal(token: str, rng) -> str:
    """Kannada terminal-vowel variation: Ramesh -> Ramesha / Rameshu."""
    if token.endswith(("appa", "anna", "amma")):
        # swap the kinship suffix occasionally
        base = token[:-4]
        return base + rng.choice(("appa", "anna"))
    return token + rng.choice(_VOWEL_TAILS)


def _translit_variant(token: str, rng) -> str:
    out = token
    for a, b in _TRANSLIT_SUBS:
        if a in out.lower() and rng.random() < 0.5:
            # preserve leading capital
            lowered = out.lower().replace(a, b, 1)
            out = lowered[0].upper() + lowered[1:]
    if rng.random() < 0.2 and len(out) > 3:  # occasional doubled consonant
        i = rng.randrange(1, len(out) - 1)
        out = out[:i] + out[i] + out[i:]
    return out


def corrupt_token(token: str, rng, strength: float = 0.6) -> str:
    """Apply 0-3 spelling corruptions to a single name token."""
    out = token
    if rng.random() < strength:
        out = _drift_terminal(out, rng)
    if rng.random() < strength:
        out = _translit_variant(out, rng)
    return out


def render_variant(
    parts: NameParts,
    rng,
    *,
    strength: float = 0.6,
    drop_patronymic_prob: float = 0.45,
    alias_prob: float = 0.4,
    honorific_prob: float = 0.15,
) -> str:
    """Produce one corrupted surface form of a canonical identity — the string
    that actually lands in accused_name / victim_name / complainant_name."""
    given = corrupt_token(parts.given, rng, strength)
    chunks: list[str] = []

    if rng.random() < honorific_prob:
        chunks.append(rng.choice(HONORIFICS))

    if parts.alias and rng.random() < alias_prob:
        alias = corrupt_token(parts.alias, rng, strength * 0.5)
        chunks.append(f"{given} @ {alias}")
    else:
        chunks.append(given)

    if rng.random() > drop_patronymic_prob:
        patro = corrupt_token(parts.patronymic, rng, strength)
        chunks.append(f"{parts.relation} {patro}")

    return " ".join(chunks)
