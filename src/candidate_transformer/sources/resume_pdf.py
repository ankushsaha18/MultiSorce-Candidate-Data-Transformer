"""Resume PDF source adapter.

The parser is intentionally deterministic: it uses pdfplumber for text
extraction and regex/section heuristics for field extraction. It does not use
AI and does not perform final normalization or merge decisions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import logging
import re

import pdfplumber

from candidate_transformer.models import SourceRecord
from candidate_transformer.normalization import (
    normalize_country_to_alpha2,
    normalize_date_range,
    normalize_date_to_year_month,
    normalize_skill_name,
)

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
_URL_RE = re.compile(
    r"\b(?:https?://)?(?:www\.)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:/[^\s|,;)]*)?",
    re.IGNORECASE,
)
_DATE_RANGE_RE = re.compile(
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)?\.?\s*"
    r"(?:\d{4}|'?\d{2})\s*(?:-|–|to)\s*"
    r"(?:present|current|(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)?\.?\s*(?:\d{4}|'?\d{2}))\b",
    re.IGNORECASE,
)


class ResumePdfParser:
    """Parse a resume PDF into a single intermediate source record."""

    source_type = "resume_pdf"

    SECTION_ALIASES: dict[str, str] = {
        "skills": "skills",
        "technical skills": "skills",
        "core skills": "skills",
        "education": "education",
        "academic background": "education",
        "experience": "experience",
        "work experience": "experience",
        "professional experience": "experience",
        "employment": "experience",
        "projects": "_ignore",
        "achievements": "_ignore",
        "certifications": "_ignore",
        "awards": "_ignore",
    }

    def parse(self, path: str | Path) -> list[SourceRecord]:
        pdf_path = Path(path)
        source_id = pdf_path.name

        text, page_texts = self._extract_text(pdf_path)
        if text is None:
            return []

        warnings: list[str] = []
        canonical = self._extract_canonical(text, warnings)
        if not canonical:
            warning = "resume PDF has no usable candidate values"
            warnings.append(warning)
            logger.warning("Resume PDF %s %s", pdf_path, warning)

        return [
            SourceRecord(
                source_type=self.source_type,
                source_id=source_id,
                record_id=f"{source_id}:document",
                canonical=canonical,
                raw={
                    "text": text,
                    "pages": page_texts,
                },
                warnings=warnings,
            )
        ]

    def _extract_text(self, path: Path) -> tuple[str, list[str]] | tuple[None, None]:
        if not path.exists():
            logger.warning("Resume PDF file does not exist: %s", path)
            return None, None

        try:
            page_texts: list[str] = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    page_texts.append(page_text)
        except Exception as exc:
            logger.warning("Resume PDF file is malformed or unreadable: %s: %s", path, exc)
            return None, None

        text = "\n".join(page_texts).strip()
        if not text:
            logger.warning("Resume PDF file contains no extractable text: %s", path)
            return "", page_texts
        return text, page_texts

    def _extract_canonical(self, text: str, warnings: list[str]) -> dict[str, Any]:
        lines = self._clean_lines(text)
        sections = self._sections_by_name(lines)
        canonical: dict[str, Any] = {}

        name = self._extract_name(lines)
        if name:
            canonical["full_name"] = name
        else:
            warnings.append("missing full_name")

        email = self._extract_email(text)
        if email:
            canonical["emails"] = [email]
        else:
            warnings.append("missing email")

        phone = self._extract_phone(text)
        if phone:
            canonical["phones"] = [phone]

        links = self._extract_links(text)
        if links:
            canonical["links"] = links

        location = self._extract_location(lines)
        if location:
            canonical["location"] = location

        headline = self._extract_headline(lines, name)
        if headline:
            canonical["headline"] = headline

        skills = self._extract_skills(sections.get("skills", []))
        if skills:
            canonical["skills"] = [
                {
                    "name": skill,
                    "confidence": 0.0,
                    "sources": [],
                }
                for skill in skills
            ]

        education = self._extract_education(sections.get("education", []))
        if education:
            canonical["education"] = education

        experience = self._extract_experience(sections.get("experience", []))
        if experience:
            canonical["experience"] = experience
            years_experience = self._calculate_years_experience(experience)
            if years_experience is not None:
                canonical["years_experience"] = years_experience

        return canonical

    def _clean_lines(self, text: str) -> list[str]:
        return [line.strip() for line in text.splitlines() if line.strip()]

    def _sections_by_name(self, lines: list[str]) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {}
        current_section: str | None = None

        for line in lines:
            section = self._heading_to_section(line)
            if section:
                current_section = None if section == "_ignore" else section
                if current_section:
                    sections.setdefault(current_section, [])
                continue
            if current_section:
                sections[current_section].append(line)

        return sections

    def _heading_to_section(self, line: str) -> str | None:
        normalized = line.strip().lower().rstrip(":")
        return self.SECTION_ALIASES.get(normalized)

    def _extract_name(self, lines: list[str]) -> str | None:
        for line in lines[:8]:
            if self._is_heading(line):
                return None
            if self._contains_contact_info(line):
                continue
            if len(line.split()) > 5:
                continue
            return line
        return None

    def _extract_email(self, text: str) -> str | None:
        match = _EMAIL_RE.search(text)
        return match.group(0) if match else None

    def _extract_phone(self, text: str) -> str | None:
        match = _PHONE_RE.search(text)
        if not match:
            return None
        return re.sub(r"\s+", " ", match.group(0)).strip()

    def _extract_headline(self, lines: list[str], name: str | None) -> str | None:
        start_index = 0
        if name and name in lines:
            start_index = lines.index(name) + 1

        for line in lines[start_index : start_index + 6]:
            if self._is_heading(line):
                break
            if self._contains_contact_info(line):
                continue
            if self._looks_like_location(line):
                continue
            if len(line) > 120:
                continue
            return line
        return self._headline_from_education(lines)

    def _extract_skills(self, lines: list[str]) -> list[str]:
        skills: list[str] = []
        seen: set[str] = set()
        for line in lines:
            parts = re.split(r"[,;|•\n]", line)
            for part in parts:
                skill = normalize_skill_name(part)
                if not skill or len(skill) > 60:
                    continue
                key = skill.casefold()
                if key not in seen:
                    skills.append(skill)
                    seen.add(key)
        return skills

    def _extract_education(self, lines: list[str]) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None

        for line in lines:
            parsed_inline = self._parse_inline_education(line)
            if parsed_inline:
                if current:
                    entries.append(current)
                    current = None
                entries.append(parsed_inline)
                continue

            if self._looks_like_institution(line):
                if current:
                    entries.append(current)
                current = {
                    "institution": line,
                    "degree": None,
                    "field": None,
                    "end_year": self._extract_year(line),
                }
                continue

            if current is None:
                current = {
                    "institution": None,
                    "degree": None,
                    "field": None,
                    "end_year": None,
                }

            if current["degree"] is None and self._looks_like_degree(line):
                degree, field = self._split_degree_and_field(line)
                current["degree"] = degree
                if field and current["field"] is None:
                    current["field"] = field
            elif current["field"] is None and not _DATE_RANGE_RE.search(line):
                current["field"] = line

            year = self._extract_year(line)
            if year and current["end_year"] is None:
                current["end_year"] = year

        if current:
            entries.append(current)

        return [entry for entry in entries if any(value is not None for value in entry.values())]

    def _extract_experience(self, lines: list[str]) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        index = 0

        while index < len(lines):
            company = lines[index]
            if self._is_noise_line(company):
                index += 1
                continue

            title = lines[index + 1] if index + 1 < len(lines) else None
            date_line = lines[index + 2] if index + 2 < len(lines) else None
            summary_lines: list[str] = []

            inline = self._parse_inline_experience(company)
            if inline:
                cursor = index + 1
                while cursor < len(lines):
                    next_line = lines[cursor]
                    if self._parse_inline_experience(next_line):
                        break
                    summary_lines.append(next_line.strip(" -•"))
                    cursor += 1
                inline["summary"] = " ".join(summary_lines) or None
                entries.append(inline)
                index = max(cursor, index + 1)
                continue

            if title and _DATE_RANGE_RE.search(title):
                date_line = title
                title = None

            start: str | None = None
            end: str | None = None
            if date_line and _DATE_RANGE_RE.search(date_line):
                start, end = self._normalize_resume_date_range(date_line)

            cursor = index + 3 if date_line and _DATE_RANGE_RE.search(date_line) else index + 2
            while cursor < len(lines):
                next_line = lines[cursor]
                if cursor + 2 < len(lines) and _DATE_RANGE_RE.search(lines[cursor + 2]):
                    break
                summary_lines.append(next_line.strip(" -•"))
                cursor += 1

            entries.append(
                {
                    "company": company,
                    "title": None if title and _DATE_RANGE_RE.search(title) else title,
                    "start": start,
                    "end": end,
                    "summary": " ".join(summary_lines) or None,
                }
            )
            index = max(cursor, index + 1)

        return entries

    def _is_heading(self, line: str) -> bool:
        return self._heading_to_section(line) is not None

    def _contains_contact_info(self, line: str) -> bool:
        return bool(_EMAIL_RE.search(line) or _PHONE_RE.search(line) or _URL_RE.search(line))

    def _looks_like_institution(self, line: str) -> bool:
        lowered = line.lower()
        tokens = ("university", "college", "institute", "school", "academy", "anusandhan", "iter")
        return any(token in lowered for token in tokens)

    def _looks_like_degree(self, line: str) -> bool:
        lowered = line.lower()
        tokens = ("bachelor", "master", "phd", "b.tech", "btech", "b.e", "b.s", "m.s", "ba", "bs", "ms", "mba")
        return any(token in lowered for token in tokens)

    def _extract_year(self, line: str) -> int | None:
        matches = re.findall(r"\b(19\d{2}|20\d{2}|21\d{2})\b", line)
        return int(matches[-1]) if matches else None

    def _is_noise_line(self, line: str) -> bool:
        return self._is_heading(line) or self._contains_contact_info(line)

    def _extract_links(self, text: str) -> dict[str, Any] | None:
        links: dict[str, Any] = {"linkedin": None, "github": None, "portfolio": None, "other": []}
        for match in _URL_RE.finditer(text):
            url = self._normalize_url(match.group(0))
            lowered = url.lower()
            if any(domain in lowered for domain in ("gmail.com", "yahoo.com", "outlook.com", "hotmail.com")):
                continue
            if lowered.endswith(".js") or lowered.rstrip("/").endswith((".py", ".java")):
                continue
            if "github.com" in lowered and links["github"] is None:
                links["github"] = url
            elif "linkedin.com" in lowered and links["linkedin"] is None:
                links["linkedin"] = url
            elif self._looks_like_portfolio_url(url) and links["portfolio"] is None:
                links["portfolio"] = url
            elif url not in links["other"] and url not in {links["github"], links["linkedin"], links["portfolio"]}:
                links["other"].append(url)
        return links if any((links["github"], links["linkedin"], links["portfolio"], links["other"])) else None

    def _extract_location(self, lines: list[str]) -> dict[str, str | None] | None:
        for line in lines[:8]:
            if not self._looks_like_location(line):
                continue
            cleaned = re.sub(_EMAIL_RE, "", line)
            cleaned = re.sub(_PHONE_RE, "", cleaned)
            cleaned = re.sub(_URL_RE, "", cleaned)
            parts = [part.strip() for part in re.split(r"[|,]", cleaned) if part.strip()]
            for part in parts:
                if not self._looks_like_location(part):
                    continue
                tokens = [token.strip() for token in part.split(",") if token.strip()]
                country = normalize_country_to_alpha2(tokens[-1]) if tokens else None
                return {
                    "city": tokens[0] if tokens and not country else None,
                    "region": tokens[1] if len(tokens) > 2 else None,
                    "country": country,
                }
        return None

    def _parse_inline_education(self, line: str) -> dict[str, Any] | None:
        if "|" not in line:
            return None
        cleaned = line.lstrip("❖•*- ").strip()
        parts = [part.strip() for part in cleaned.split("|") if part.strip()]
        if len(parts) < 2:
            return None
        field_or_degree = parts[0]
        institution = re.sub(r"\s+CGPA:.*$", "", parts[1], flags=re.IGNORECASE).strip()
        if not (self._looks_like_institution(institution) or self._looks_like_degree(field_or_degree)):
            return None
        end_year = self._extract_year(line)
        if end_year is None:
            range_match = _DATE_RANGE_RE.search(line)
            if range_match:
                _, end = self._normalize_resume_date_range(range_match.group(0))
                if end:
                    end_year = int(end.split("-")[0])
        degree, field = self._split_degree_and_field(field_or_degree)
        if field is None and "engineering" in field_or_degree.lower():
            field = field_or_degree
            degree = "B.Tech"
        return {
            "institution": institution or None,
            "degree": degree,
            "field": field,
            "end_year": end_year,
        }

    def _parse_inline_experience(self, line: str) -> dict[str, Any] | None:
        range_match = _DATE_RANGE_RE.search(line)
        if not range_match or "|" not in line:
            return None
        prefix = line[: range_match.start()].lstrip("❖•*- ").strip().rstrip(" (")
        parts = [part.strip() for part in prefix.split("|") if part.strip()]
        if len(parts) < 2:
            return None
        start, end = self._normalize_resume_date_range(range_match.group(0))
        return {
            "company": parts[1],
            "title": parts[0],
            "start": start,
            "end": end,
            "summary": None,
        }

    def _split_degree_and_field(self, line: str) -> tuple[str, str | None]:
        cleaned = re.sub(r"\b(19\d{2}|20\d{2}|21\d{2})\b", "", line).strip(" ,-")
        patterns = (
            r"(?P<degree>B\.?\s?Tech|BTech|Bachelor of Technology)\s*(?:in\s+)?(?P<field>.+)?",
            r"(?P<degree>Bachelor of Science|Bachelor of Arts|Bachelor)\s+(?:in\s+)?(?P<field>.+)",
            r"(?P<degree>Master of Science|Master of Arts|Master)\s+(?:in\s+)?(?P<field>.+)",
        )
        for pattern in patterns:
            match = re.match(pattern, cleaned, flags=re.IGNORECASE)
            if match:
                field = (match.group("field") or "").strip(" ,-") or None
                return self._canonical_degree(match.group("degree")), field
        return self._canonical_degree(cleaned), None

    def _canonical_degree(self, degree: str) -> str:
        compact = re.sub(r"[\s.]+", "", degree).lower()
        if compact in {"btech", "bacheloroftechnology"}:
            return "B.Tech"
        return degree.strip()

    def _headline_from_education(self, lines: list[str]) -> str | None:
        for line in lines[:30]:
            parsed = self._parse_inline_education(line)
            if parsed and parsed.get("field"):
                return f"{parsed['field']} Student"
            if self._looks_like_degree(line):
                _, field = self._split_degree_and_field(line)
                if field:
                    return f"{field} Student"
        return None

    def _normalize_resume_date_range(self, value: str) -> tuple[str | None, str | None]:
        normalized = re.sub(r"(?i)(jan|feb|mar|apr|may|jun|june|jul|aug|sep|sept|oct|nov|dec)[a-z]*'(\d{2})", r"\1 20\2", value)
        normalized = re.sub(r"'(\d{2})", r"20\1", normalized)
        start, end = normalize_date_range(normalized)
        if re.search(r"\b(present|current)\b", value, re.IGNORECASE):
            end = "present"
        return start, end

    def _calculate_years_experience(self, experience: list[dict[str, Any]]) -> float | None:
        total_months = 0
        for item in experience:
            start = normalize_date_to_year_month(item.get("start"))
            end_value = item.get("end")
            if end_value == "present":
                return None
            end = normalize_date_to_year_month(end_value, default_month=12)
            if not start or not end:
                continue
            start_year, start_month = (int(part) for part in start.split("-"))
            end_year, end_month = (int(part) for part in end.split("-"))
            months = (end_year - start_year) * 12 + (end_month - start_month) + 1
            if months > 0:
                total_months += months
        return round(total_months / 12, 2) if total_months else None

    def _normalize_url(self, value: str) -> str:
        url = value.strip().rstrip(".,;)")
        if not url.lower().startswith(("http://", "https://")):
            url = "https://" + url
        return url

    def _looks_like_portfolio_url(self, url: str) -> bool:
        lowered = url.lower()
        return not any(domain in lowered for domain in ("github.com", "linkedin.com", "gmail.com", "google.com"))

    def _looks_like_location(self, line: str) -> bool:
        lowered = line.lower()
        tokens = ("india", "usa", "united states", "bhubaneswar", "odisha", "bangalore", "bengaluru", "delhi", "mumbai")
        return any(re.search(rf"\b{re.escape(token)}\b", lowered) for token in tokens)


def parse_resume_pdf(path: str | Path) -> list[SourceRecord]:
    """Convenience function for parsing a resume PDF file."""
    return ResumePdfParser().parse(path)
