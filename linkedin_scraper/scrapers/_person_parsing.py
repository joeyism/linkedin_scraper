"""Internal, fixture-testable parsers for LinkedIn person sections."""

import re
from typing import Any, List, Optional, Sequence, Set, Tuple

from ..models import Education, Experience

YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
DATE_RANGE_RE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4})\b"
    r".*(?:\s[-\u2013\u2014]\s|\s-\s)"
)
DEGREE_KEYWORDS = (
    "bachelor",
    "master",
    "doctor",
    "phd",
    "ph.d",
    "mba",
    "b.tech",
    "btech",
    "m.tech",
    "mtech",
    "b.s",
    "b.a",
    "m.s",
    "m.sc",
    "degree",
    "diploma",
)
EDUCATION_METADATA_PREFIXES = (
    "grade:",
    "skills:",
    "activities:",
    "activities and societies:",
)
UI_LINES = {
    "Show all experiences",
    "Show all education",
    "Show more",
    "See more",
}
EMPLOYMENT_TYPE_MARKERS = (
    "full-time",
    "part-time",
    "internship",
    "contract",
    "self-employed",
    "freelance",
    "apprenticeship",
    "seasonal",
    "temporary",
)
JOB_TITLE_HINTS = (
    "ceo",
    "chairman",
    "chair",
    "president",
    "founder",
    "co-founder",
    "director",
    "manager",
    "engineer",
    "developer",
    "intern",
    "officer",
    "lead",
    "head of",
    "vice president",
    "vp ",
    "consultant",
    "analyst",
    "scientist",
    "architect",
    "specialist",
    "researcher",
)


def clean_lines(text: str) -> List[str]:
    """Return stripped, non-empty lines without adjacent duplicates."""
    result: List[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line and (not result or result[-1] != line):
            result.append(line)
    return result


def section_lines(text: str, header: str, stop_headers: Set[str]) -> List[str]:
    """Return section lines, or an empty list when the heading is absent."""
    lines = clean_lines(text)
    try:
        start = lines.index(header) + 1
    except ValueError:
        return []

    result = []
    for line in lines[start:]:
        if line in stop_headers or line.startswith("LinkedIn Corporation"):
            break
        if line not in UI_LINES:
            result.append(line)
    return result


def parse_work_times(
    work_times: str,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Split a LinkedIn work date range and duration."""
    if not work_times:
        return None, None, None
    parts = work_times.split("·")
    times = parts[0].strip()
    duration = parts[1].strip() if len(parts) > 1 else None
    normalized = re.sub(r"\s*[-\u2013\u2014]\s*", " - ", times)
    date_parts = normalized.split(" - ", 1)
    return (
        date_parts[0].strip() or None,
        date_parts[1].strip() if len(date_parts) > 1 else None,
        duration,
    )


def parse_education_times(times: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract one or two years from an education date line."""
    years = YEAR_RE.findall(times or "")
    if len(years) >= 2:
        return years[0], years[1]
    if len(years) == 1:
        return years[0], years[0]
    return None, None


def looks_like_date_line(line: str) -> bool:
    return bool(YEAR_RE.search(line)) and (
        any(separator in line for separator in ("-", "–", "—"))
        or line.strip().isdigit()
    )


def looks_like_degree(line: str) -> bool:
    lower = line.lower()
    return any(keyword in lower for keyword in DEGREE_KEYWORDS)


def is_education_metadata(line: str) -> bool:
    lower = line.lower()
    return any(lower.startswith(prefix) for prefix in EDUCATION_METADATA_PREFIXES)


def is_valid_institution(line: str) -> bool:
    return bool(
        line
        and not is_education_metadata(line)
        and not looks_like_date_line(line)
        and not (looks_like_degree(line) and len(line) < 120)
    )


def _is_duration_only(line: str) -> bool:
    lower = line.lower()
    return bool(re.search(r"\b\d+\s+(?:yr|yrs|mo|mos)\b", lower)) and not bool(
        YEAR_RE.search(line)
    )


def _has_employment_type(line: str) -> bool:
    lower = line.lower()
    return " · " in line or any(marker in lower for marker in EMPLOYMENT_TYPE_MARKERS)


def _looks_like_job_title(line: str) -> bool:
    lower = line.lower()
    return any(hint in lower for hint in JOB_TITLE_HINTS)


def _single_role_title_and_company(
    lines: Sequence[str], date_index: int
) -> Tuple[str, str]:
    """
    Resolve title/company for a single-role card.

    LinkedIn emits both:
    - Title, Company · type, Dates
    - Company, Title, Dates
    - Company, Title · type, Dates  (company logo/name first)
    """
    before = lines[date_index - 1] if date_index >= 1 else ""
    before2 = lines[date_index - 2] if date_index >= 2 else ""
    if not before:
        return before2, ""

    before_name = before.split(" · ", 1)[0]
    before2_name = before2.split(" · ", 1)[0] if before2 else ""

    if _has_employment_type(before) and before2:
        # Company-first with type on title: Microsoft / Chairman and CEO · Full-time
        if _looks_like_job_title(before_name) and not _looks_like_job_title(
            before2_name
        ):
            return before_name, before2_name
        # Classic: CEO / Acme Corp · Full-time
        return before2_name, before_name

    # Company-first without employment type: Microsoft / Chairman and CEO
    if (
        before2
        and _looks_like_job_title(before_name)
        and not _looks_like_job_title(before2_name)
    ):
        return before_name, before2_name

    if before2:
        return before2_name, before_name
    return before_name, ""


def parse_experience_lines(
    lines: Sequence[str], linkedin_url: Optional[str] = None
) -> List[Experience]:
    """Parse one experience card, including grouped roles."""
    lines = [line for line in lines if line not in UI_LINES]
    date_indexes = [
        index for index, line in enumerate(lines) if DATE_RANGE_RE.search(line)
    ]
    if not date_indexes:
        return []

    is_grouped = len(date_indexes) > 1 or (
        date_indexes[0] >= 3 and _is_duration_only(lines[1])
    )
    if is_grouped:
        title_indexes = [max(0, index - 1) for index in date_indexes]
    else:
        title_indexes = [max(0, date_indexes[0] - 2)]
    grouped_company = None
    if is_grouped and title_indexes[0] >= 2:
        candidate = lines[0]
        if not DATE_RANGE_RE.search(candidate) and not _is_duration_only(candidate):
            grouped_company = candidate.split(" · ", 1)[0]

    experiences = []
    for role_index, date_index in enumerate(date_indexes):
        title_index = title_indexes[role_index]
        if grouped_company:
            title = lines[title_index]
            company = grouped_company
        elif is_grouped:
            title = lines[title_index]
            company_line = lines[title_index - 1] if title_index > 0 else ""
            if company_line and not _is_duration_only(company_line):
                company = company_line.split(" · ", 1)[0]
            else:
                company = lines[0].split(" · ", 1)[0] if lines else ""
        else:
            title, company = _single_role_title_and_company(lines, date_index)

        next_title = (
            title_indexes[role_index + 1]
            if role_index + 1 < len(title_indexes)
            else len(lines)
        )
        trailing = list(lines[date_index + 1 : next_title])
        location = None
        if trailing and not _is_duration_only(trailing[0]):
            location = trailing.pop(0).split(" · ", 1)[0]
        description = "\n".join(trailing).strip() or None
        from_date, to_date, duration = parse_work_times(lines[date_index])

        if title:
            experiences.append(
                Experience(
                    position_title=title,
                    institution_name=company or None,
                    linkedin_url=linkedin_url,
                    from_date=from_date,
                    to_date=to_date,
                    duration=duration,
                    location=location,
                    description=description,
                )
            )
    return experiences


def parse_experiences_text(text: str) -> List[Experience]:
    """Fallback parser for captured detail-page text.

    The details page often has no list-item DOM cards, so the whole Experience
    section arrives as flat text. Split that text into one single-role window
    per date line instead of treating the section as one grouped company.
    """
    lines = section_lines(
        text,
        "Experience",
        {
            "Education",
            "More profiles for you",
            "People also viewed",
            "LinkedIn Corporation",
            "Footer",
        },
    )
    date_indexes = [
        index for index, line in enumerate(lines) if DATE_RANGE_RE.search(line)
    ]
    experiences: List[Experience] = []
    for index, date_index in enumerate(date_indexes):
        if date_index < 2:
            continue
        next_date = (
            date_indexes[index + 1] if index + 1 < len(date_indexes) else len(lines)
        )
        # Keep location/description, but stop before the next role's title/company.
        end = next_date - 2 if next_date - 2 > date_index else next_date
        end = max(end, date_index + 1)
        chunk = lines[date_index - 2 : end]
        experiences.extend(parse_experience_lines(chunk))
    return experiences


def parse_education_lines(
    lines: Sequence[str], linkedin_url: Optional[str] = None
) -> Optional[Education]:
    """Parse one education card while retaining metadata as description."""
    lines = [line for line in lines if line not in UI_LINES]
    if not lines:
        return None
    institution = lines[0]
    if not is_valid_institution(institution):
        return None

    degree = None
    from_date = to_date = None
    description_lines = []
    for line in lines[1:]:
        if looks_like_date_line(line) and from_date is None:
            from_date, to_date = parse_education_times(line)
        elif degree is None and looks_like_degree(line):
            degree = line
        else:
            description_lines.append(line)
    return Education(
        institution_name=institution,
        degree=degree,
        linkedin_url=linkedin_url,
        from_date=from_date,
        to_date=to_date,
        description="\n".join(description_lines).strip() or None,
    )


def parse_educations_text(text: str) -> List[Education]:
    """Fallback parser for captured detail-page text."""
    lines = section_lines(
        text,
        "Education",
        {
            "More profiles for you",
            "People also viewed",
            "LinkedIn Corporation",
            "Footer",
        },
    )
    educations = []
    index = 0
    while index < len(lines):
        if not is_valid_institution(lines[index]):
            index += 1
            continue
        end = index + 1
        while end < len(lines):
            if (
                is_valid_institution(lines[end])
                and not looks_like_degree(lines[end])
                and not is_education_metadata(lines[end])
            ):
                break
            end += 1
        education = parse_education_lines(lines[index:end])
        if education:
            educations.append(education)
        index = end
    return educations


async def item_text_and_url(
    item: Any, url_fragment: str
) -> Tuple[List[str], Optional[str]]:
    """Extract one card's visible lines and organization URL."""
    href = None
    link = item.locator('a[href*="{}"]'.format(url_fragment)).first
    if await link.count() > 0:
        href = await link.get_attribute("href")
        if href and href.startswith("/"):
            href = "https://www.linkedin.com{}".format(href)
    return clean_lines(await item.inner_text()), href
