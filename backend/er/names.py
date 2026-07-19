"""Name parsing and normalization — stage 1 and 2 of entity resolution.

Indian FIR name fields are free text that carries structure *inside* the string:
a patronymic (``S/o Krishnappa``), an alias (``Ramesh @ Rami``), honorifics, and
a given name that is spelled a dozen different ways across FIRs. This module pulls
that structure back out and produces the two keys the rest of ER depends on:

  * a **normalized given name** for Jaro-Winkler similarity (P6), and
  * a **phonetic key** for blocking (P6) — Double Metaphone over the transliterated
    name, pre-processed with a Dravidian rule set so that Kannada spelling and
    transliteration variance (Ramesh / Ramesha / Rameshu, th↔t, sh↔s, v↔w, doubled
    consonants, -appa/-anna kinship suffixes) collapses to one key.

Why not plain Soundex: it is tuned for English surnames and keeps Ramesh and Ramya
apart while merging things that sound nothing alike in Kannada. The Dravidian
pre-normalization below is what makes the phonetic key usable on these names.

This module reads only the raw name string. It never touches the ground truth.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate
from metaphone import doublemetaphone

# -----------------------------------------------------------------------------
# Lexicons
# -----------------------------------------------------------------------------

# Honorifics stripped from the front of a name (case-insensitive, trailing dot ok).
HONORIFICS = {
    "sri", "shri", "smt", "smti", "kum", "kumari", "mr", "mrs", "ms", "dr",
    "s",  # occasional bare "S." abbreviation of Sri
    "thiru", "selvi", "late",
}

# Relation markers introducing a patronymic, longest-first so "son of" wins over "s".
_RELATION_PATTERNS = [
    (r"s\s*/\s*o", "S/o"),
    (r"d\s*/\s*o", "D/o"),
    (r"w\s*/\s*o", "W/o"),
    (r"c\s*/\s*o", "C/o"),
    (r"son\s+of", "S/o"),
    (r"daughter\s+of", "D/o"),
    (r"wife\s+of", "W/o"),
    (r"care\s+of", "C/o"),
    (r"bin", "S/o"),      # Islamic patronymic conventions seen in KA FIRs
    (r"binte", "D/o"),
]
_RELATION_RE = re.compile(r"\b(" + "|".join(p for p, _ in _RELATION_PATTERNS) + r")\b\.?", re.I)
_RELATION_CANON = [(re.compile(p, re.I), canon) for p, canon in _RELATION_PATTERNS]

# "Late" / "L/o" prefixes that sometimes lead a patronymic ("S/o Late Krishnappa").
_LATE_RE = re.compile(r"^\s*(late|l\s*/\s*o|lt\.?)\s+", re.I)

_KANNADA_RANGE = (0x0C80, 0x0CFF)


# -----------------------------------------------------------------------------
# Result type
# -----------------------------------------------------------------------------


@dataclass
class ParsedName:
    raw: str
    given: str
    alias: str | None
    patronymic: str | None
    relation: str | None                 # canonicalised S/o, D/o, W/o, C/o
    honorifics: list[str] = field(default_factory=list)
    script: str = "roman"                # 'kannada' | 'roman' | 'mixed'
    normalized_given: str = ""           # transliterated, casefolded (for Jaro-Winkler)
    normalized_patronymic: str | None = None
    phonetic_key: str = ""               # blocking key over the first given token
    patronymic_key: str | None = None    # phonetic key of the patronymic

    def as_dict(self) -> dict:
        return {
            "raw": self.raw,
            "given": self.given,
            "alias": self.alias,
            "patronymic": self.patronymic,
            "relation": self.relation,
            "honorifics": self.honorifics,
            "script": self.script,
            "normalized_given": self.normalized_given,
            "normalized_patronymic": self.normalized_patronymic,
            "phonetic_key": self.phonetic_key,
            "patronymic_key": self.patronymic_key,
        }


# -----------------------------------------------------------------------------
# Script detection + transliteration
# -----------------------------------------------------------------------------


def detect_script(text: str) -> str:
    has_kannada = any(_KANNADA_RANGE[0] <= ord(c) <= _KANNADA_RANGE[1] for c in text)
    has_latin = any("a" <= c.lower() <= "z" for c in text)
    if has_kannada and has_latin:
        return "mixed"
    if has_kannada:
        return "kannada"
    return "roman"


def to_roman(text: str) -> str:
    """Transliterate any Kannada spans to Roman (ITRANS), leaving Latin text alone.

    Done token-wise so a code-mixed name like ``ರಮೇಶ Kumar`` transliterates only the
    Kannada part. ITRANS output is lower-cased downstream, so its capital-letter
    retroflex markers don't matter for matching.
    """
    if detect_script(text) == "roman":
        return text
    out = []
    for token in text.split():
        if any(_KANNADA_RANGE[0] <= ord(c) <= _KANNADA_RANGE[1] for c in token):
            out.append(transliterate(token, sanscript.KANNADA, sanscript.ITRANS))
        else:
            out.append(token)
    return " ".join(out)


# -----------------------------------------------------------------------------
# Parsing
# -----------------------------------------------------------------------------


def _clean(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    # normalise the '@' alias marker and whitespace; keep '/' for relation markers
    text = text.replace("@", " @ ")
    text = re.sub(r"[^\w@/ಀ-೿\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _canon_relation(marker: str) -> str:
    norm = re.sub(r"\s+", " ", marker).strip()
    for rx, canon in _RELATION_CANON:
        if rx.fullmatch(norm):
            return canon
    return marker.upper()


def _strip_honorifics(tokens: list[str]) -> tuple[list[str], list[str]]:
    honorifics: list[str] = []
    i = 0
    while i < len(tokens) and tokens[i].lower().strip(".") in HONORIFICS:
        honorifics.append(tokens[i].strip("."))
        i += 1
    return honorifics, tokens[i:]


def parse(name: str | None) -> ParsedName:
    """Parse a raw FIR name field into its components (stage 1)."""
    raw = name or ""
    script = detect_script(raw)
    cleaned = _clean(raw)
    if not cleaned:
        return ParsedName(
            raw=raw, given="", alias=None, patronymic=None, relation=None, script=script
        )

    # 1. split off the patronymic at the first relation marker
    relation = patronymic = None
    m = _RELATION_RE.search(cleaned)
    if m:
        head = cleaned[: m.start()].strip()
        patronymic = cleaned[m.end():].strip()
        patronymic = _LATE_RE.sub("", patronymic).strip() or None
        relation = _canon_relation(m.group(1))
    else:
        head = cleaned

    # 2. strip leading honorifics from the given portion
    honorifics, tokens = _strip_honorifics(head.split())
    head = " ".join(tokens)

    # 3. split alias on '@'
    alias = None
    if "@" in head:
        left, _, right = head.partition("@")
        head = left.strip()
        # the alias may itself carry an honorific; drop it
        _, alias_tokens = _strip_honorifics(right.split())
        alias = " ".join(alias_tokens).strip() or None

    given = head.strip()

    parsed = ParsedName(
        raw=raw,
        given=given,
        alias=alias,
        patronymic=patronymic,
        relation=relation,
        honorifics=honorifics,
        script=script,
    )
    _normalize(parsed)
    return parsed


# -----------------------------------------------------------------------------
# Normalization (stage 2)
# -----------------------------------------------------------------------------

# Applied before Double Metaphone. Order matters: multi-char rules first.
_DRAVIDIAN_SUBS = [
    ("chh", "ch"), ("ksh", "k"), ("jn", "gn"), ("zh", "l"),
    ("bh", "b"), ("dh", "d"), ("gh", "g"), ("jh", "j"), ("kh", "k"),
    ("ph", "p"), ("th", "t"), ("sh", "s"), ("ch", "c"),
    ("w", "v"),                        # v/w interchange -> v
]
# Kinship suffixes that vary freely (-appa/-anna/-amma/-aiah/-ayya/-gowda): collapse
# to root. The consonant class is written a[pnm]a so it still matches AFTER the double
# -consonant collapse has turned "appa"->"apa" / "anna"->"ana" / "amma"->"ama".
_KINSHIP_SUFFIX_RE = re.compile(r"(a[pnm]a|ayya|aiah|aiya|e?gowda)$")
_MIN_STEM_AFTER_SUFFIX = 3  # don't strip a kinship suffix off a short name (Rama -> R)
_TRAILING_VOWELS_RE = re.compile(r"[aeiou]+$")
_DOUBLE_CONSONANT_RE = re.compile(r"([bcdfghjklmnpqrstvxz])\1+")


def dravidian_stem(token: str) -> str:
    """Collapse Kannada phonetic-equivalence classes to a canonical consonant stem.

    Aggressive on purpose: this feeds the *blocking* key, where recall matters more
    than precision — the pairwise scorer (P6) draws the fine distinctions.
    """
    t = to_roman(token).lower()
    t = re.sub(r"[^a-z]", "", t)
    if not t:
        return ""
    for a, b in _DRAVIDIAN_SUBS:
        t = t.replace(a, b)
    t = _DOUBLE_CONSONANT_RE.sub(r"\1", t)
    stripped = _KINSHIP_SUFFIX_RE.sub("", t)   # drop varying kinship suffix...
    if len(stripped) >= _MIN_STEM_AFTER_SUFFIX:  # ...but not off a short name
        t = stripped
    t = _TRAILING_VOWELS_RE.sub("", t)         # terminal-vowel variation
    return t or re.sub(r"[^a-z]", "", to_roman(token).lower())


def normalize_token(token: str) -> str:
    """Transliterated, casefolded, punctuation-free form for string similarity."""
    return re.sub(r"[^a-z]", "", to_roman(token).lower())


def phonetic_key(token: str) -> str:
    """Double Metaphone over the Dravidian-normalised transliteration."""
    stem = dravidian_stem(token)
    if not stem:
        return ""
    primary, _ = doublemetaphone(stem)
    return primary or stem


def _first_token(text: str) -> str:
    return text.split()[0] if text.split() else ""


def _normalize(p: ParsedName) -> None:
    p.normalized_given = normalize_token(p.given) if p.given else ""
    p.phonetic_key = phonetic_key(_first_token(p.given)) if p.given else ""
    if p.patronymic:
        p.normalized_patronymic = normalize_token(p.patronymic)
        p.patronymic_key = phonetic_key(_first_token(p.patronymic))
