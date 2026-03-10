from __future__ import annotations

from collections import OrderedDict, defaultdict
from dataclasses import dataclass
import re

from rapidfuzz import fuzz, process


KEYWORD_GROUPS: dict[str, tuple[str, ...]] = {
    "sling": (
        "lifting sling",
        "wire rope sling",
        "webbing sling",
        "chain sling",
        "endless sling",
        "flat woven sling",
    ),
    "wire rope sling": (
        "steel wire rope sling",
        "rope sling",
        "wire sling",
        "lifting sling",
    ),
    "webbing sling": (
        "flat woven sling",
        "polyester sling",
        "lifting belt",
        "soft sling",
    ),
    "chain sling": (
        "lifting chain",
        "alloy chain sling",
        "chain assembly",
    ),
    "wire rope": (
        "steel wire rope",
        "rope",
        "wire sling",
        "wire rope clip",
    ),
    "shackle": (
        "bow shackle",
        "anchor shackle",
        "d shackle",
        "dee shackle",
        "pin shackle",
    ),
    "hook": (
        "lifting hook",
        "eye hook",
        "clevis hook",
        "swivel hook",
        "grab hook",
    ),
    "turnbuckle": (
        "rigging screw",
        "tensioner",
        "adjuster",
    ),
    "pulley": (
        "pulley block",
        "snatch block",
        "sheave block",
    ),
    "clamp": (
        "wire rope clamp",
        "rope clip",
        "grip clamp",
    ),
    "thimble": (
        "wire rope thimble",
        "eye thimble",
    ),
    "chain": (
        "lifting chain",
        "alloy chain",
        "anchor chain",
        "load chain",
    ),
    "hoist": (
        "chain hoist",
        "lever hoist",
        "lifting hoist",
    ),
    "winch": (
        "pulling winch",
        "manual winch",
        "electric winch",
    ),
    "eyebolt": (
        "eye bolt",
        "lifting eye bolt",
        "hoist ring",
    ),
    "rigging": (
        "lifting",
        "lifting hardware",
        "lifting tackle",
        "material handling",
    ),
    "lashing": (
        "ratchet lashing",
        "cargo lashing",
        "tie down",
    ),
    "anchor": (
        "marine anchor",
        "anchoring hardware",
        "anchor chain",
    ),
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "in",
    "of",
    "on",
    "the",
    "to",
    "with",
}

DELIMITER_PATTERN = re.compile(r"[,;/|+\n]+")
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

FEATURED_KEYWORDS = [
    "sling",
    "wire rope sling",
    "webbing sling",
    "chain sling",
    "shackle",
    "hook",
    "turnbuckle",
    "pulley block",
]


def _normalize(value: str) -> str:
    return " ".join(value.lower().split())


GROUP_MEMBERS: dict[str, tuple[str, ...]] = {
    canonical: tuple(OrderedDict(((_normalize(item), None) for item in (canonical, *related))).keys())
    for canonical, related in KEYWORD_GROUPS.items()
}

RELATED_LOOKUP: dict[str, tuple[str, ...]] = defaultdict(tuple)
for members in GROUP_MEMBERS.values():
    for member in members:
        RELATED_LOOKUP[member] = members

KNOWN_KEYWORDS: tuple[str, ...] = tuple(
    OrderedDict((member, None) for members in GROUP_MEMBERS.values() for member in members).keys()
)


@dataclass(frozen=True)
class KeywordPlan:
    primary_terms: list[str]
    expanded_terms: list[str]
    suggested_keywords: list[str]


def featured_keywords(limit: int = 8) -> list[str]:
    return FEATURED_KEYWORDS[:limit]


def split_query_terms(query: str) -> list[str]:
    normalized = _normalize(query)
    if not normalized:
        return []

    ordered = OrderedDict[str, None]()
    ordered[normalized] = None

    explicit_parts = [_normalize(part) for part in DELIMITER_PATTERN.split(normalized)]
    for part in explicit_parts:
        if part:
            ordered[part] = None

    for part in list(ordered.keys()):
        tokens = [token for token in TOKEN_PATTERN.findall(part) if len(token) > 1 and token not in STOPWORDS]
        for token in tokens:
            ordered.setdefault(token, None)

    return list(ordered.keys())


def suggest_keywords(query: str, limit: int = 8) -> list[str]:
    normalized = _normalize(query)
    if not normalized:
        return featured_keywords(limit=limit)

    ordered = OrderedDict[str, None]()
    terms = split_query_terms(normalized)

    for term in terms:
        for candidate in KNOWN_KEYWORDS:
            if term == candidate or candidate.startswith(term) or term in candidate:
                ordered.setdefault(candidate, None)

        for candidate, score, _ in process.extract(term, KNOWN_KEYWORDS, scorer=fuzz.WRatio, limit=6):
            if score >= 68:
                ordered.setdefault(candidate, None)

        if term in RELATED_LOOKUP:
            for related in RELATED_LOOKUP[term]:
                ordered.setdefault(related, None)

    return list(ordered.keys())[:limit]


def build_keyword_plan(query: str, *, expanded_limit: int = 12, suggestion_limit: int = 8) -> KeywordPlan:
    normalized = _normalize(query)
    if not normalized:
        return KeywordPlan(primary_terms=[], expanded_terms=[], suggested_keywords=featured_keywords(suggestion_limit))

    primary_terms = split_query_terms(normalized)
    suggested_keywords = suggest_keywords(normalized, limit=suggestion_limit)

    expanded = OrderedDict[str, None]()
    for term in primary_terms:
        expanded.setdefault(term, None)
        if term in RELATED_LOOKUP:
            for related in RELATED_LOOKUP[term]:
                expanded.setdefault(related, None)

    for suggestion in suggested_keywords:
        expanded.setdefault(suggestion, None)
        if suggestion in RELATED_LOOKUP:
            for related in RELATED_LOOKUP[suggestion]:
                expanded.setdefault(related, None)

    return KeywordPlan(
        primary_terms=primary_terms,
        expanded_terms=list(expanded.keys())[:expanded_limit],
        suggested_keywords=suggested_keywords,
    )


def expand_terms(query: str) -> list[str]:
    return build_keyword_plan(query).expanded_terms
