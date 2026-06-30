"""Skill normalization helpers."""

from __future__ import annotations

import re

_ALIASES = {
    "js": "JavaScript",
    "javascript": "JavaScript",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "py": "Python",
    "python": "Python",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "sql": "SQL",
    "aws": "AWS",
    "amazon web services": "AWS",
    "gcp": "Google Cloud Platform",
    "google cloud": "Google Cloud Platform",
    "git": "Git",
    "github": "GitHub",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "distributed systems": "Distributed Systems",
    "tensorflow": "TensorFlow",
}


def normalize_skill_name(value: str | None) -> str | None:
    """Normalize a skill alias to a canonical display name."""
    if value is None:
        return None

    text = _collapse_whitespace(str(value).strip(" \t\n\r,;|•-"))
    text = re.sub(
        r"^(technical|tools?|languages?|frameworks?|libraries?)\s*:\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    if not text:
        return None

    alias_key = _alias_key(text)
    if alias_key in _ALIASES:
        return _ALIASES[alias_key]

    return _title_preserving_known_acronyms(text)


def normalize_skill_names(values: list[str] | tuple[str, ...]) -> list[str]:
    """Normalize and de-duplicate skill names while preserving first-seen order."""
    normalized: list[str] = []
    seen: set[str] = set()

    for value in values:
        skill = normalize_skill_name(value)
        if not skill:
            continue
        key = skill.casefold()
        if key not in seen:
            normalized.append(skill)
            seen.add(key)

    return normalized


def split_and_normalize_skills(value: str | None) -> list[str]:
    """Split a delimited skill string and normalize each skill."""
    if value is None:
        return []
    parts = re.split(r"[,;|•\n]", value)
    return normalize_skill_names([part for part in parts if part.strip()])


def _alias_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold().replace("_", " ").replace("-", " ")).strip()


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _title_preserving_known_acronyms(value: str) -> str:
    words = []
    for word in value.split(" "):
        if word.upper() in {"AI", "API", "AWS", "CSS", "GCP", "HTML", "SQL"}:
            words.append(word.upper())
        elif word.lower() in {"ios"}:
            words.append("iOS")
        else:
            words.append(word[:1].upper() + word[1:].lower())
    return " ".join(words)
