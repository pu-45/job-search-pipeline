"""Score a single WTTJ job listing against Paul's criteria using Claude."""
import re
from pathlib import Path

import yaml
from anthropic import Anthropic
from bs4 import BeautifulSoup

from config import CRITERIA_PATH, EFFORT, MODEL

SUBMIT_ASSESSMENT_TOOL = {
    "name": "submit_job_assessment",
    "description": (
        "Submit the structured fit assessment for this job listing against Paul's scoring criteria."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "hard_skip": {
                "type": "boolean",
                "description": (
                    "True if this job triggers any hard_skips rule from the criteria "
                    "(contract/FTC, salary below hard floor, >4 office days, excluded "
                    "location, excluded role type, clearance required, excluded domain)."
                ),
            },
            "hard_skip_reason": {
                "type": "string",
                "description": (
                    "If hard_skip is true, name the specific rule and why it applies. "
                    "Empty string if hard_skip is false."
                ),
            },
            "fit_score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": (
                    "Weighted score (0-100) across the six scoring_dimensions in the "
                    "criteria, using their stated weights. Set to 0 if hard_skip is true."
                ),
            },
            "why_it_works": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "3-5 bullet points on genuine strengths, referencing Paul's "
                    "proof_points where relevant."
                ),
            },
            "hard_gaps": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "2-4 bullet points on structural gaps or blockers, drawing honestly "
                    "on known_gaps where relevant. Do not paper over them."
                ),
            },
            "trajectory_check": {
                "type": "string",
                "description": (
                    "One sentence: does this role move Paul toward or away from product "
                    "ops / AI delivery at a tech company, and eventually product design."
                ),
            },
            "recommendation": {
                "type": "string",
                "description": (
                    "One clear sentence: apply / borderline (Paul's call) / skip, with "
                    "the single most important reason."
                ),
            },
            "role_summary": {
                "type": "string",
                "description": (
                    "A terse (under 80 chars) factual tag for the company/role, in the "
                    "style of a tracker note. E.g. 'B2B food delivery marketplace, ops "
                    "lead reporting to COO' or 'SaaS Discounts module rollout PM, reports "
                    "to PM Team Lead'. Company type + what the role actually does + who "
                    "it reports to, no fluff, no adjectives."
                ),
            },
            "caveats": {
                "type": "string",
                "description": (
                    "Optional short phrase (under 80 chars) flagging anything notable a "
                    "human should weigh before applying — e.g. 'below salary target, no "
                    "AI trajectory, mid-level seniority' or office-day/commute specifics. "
                    "Empty string if there's nothing worth flagging beyond hard_gaps."
                ),
            },
        },
        "required": [
            "hard_skip",
            "hard_skip_reason",
            "fit_score",
            "why_it_works",
            "hard_gaps",
            "trajectory_check",
            "recommendation",
            "role_summary",
            "caveats",
        ],
    },
}


def load_criteria() -> tuple[str, dict]:
    text = Path(CRITERIA_PATH).read_text(encoding="utf-8")
    parsed = yaml.safe_load(text)
    return text, parsed


def _strip_html(html: str, max_chars: int = 6000) -> str:
    if not html:
        return ""
    text = BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def _stringify_list(items) -> list[str]:
    """Normalize list fields that may contain plain strings or objects like
    {"name": "..."} / {"name": {"en": "...", "fr": "...", ...}}."""
    out = []
    for item in items or []:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            name = item.get("name", item)
            if isinstance(name, dict):
                name = name.get("en") or next(iter(name.values()), "")
            out.append(str(name))
        else:
            out.append(str(item))
    return out


def _location_str(job: dict) -> str:
    offices = job.get("offices") or []
    return ", ".join(
        f"{o.get('city', '')}, {o.get('country', '')}".strip(", ") for o in offices
    ) or "Not specified"


_CURRENCY_SYMBOLS = {"GBP": "£", "EUR": "€", "USD": "$"}


def _format_amount_k(amount: float) -> str:
    if amount >= 1000:
        k = amount / 1000
        return f"{k:.0f}k" if k == int(k) else f"{k:.1f}k"
    return str(int(amount))


def _format_salary_note(job: dict) -> str:
    """Compact salary string like '£50-60k', computed from raw job data
    rather than left to the model, since these are exact figures."""
    min_ = job.get("salaryMin")
    max_ = job.get("salaryMax")
    currency = job.get("salaryCurrency") or ""
    symbol = _CURRENCY_SYMBOLS.get(currency, f"{currency} " if currency else "")

    if min_ and max_:
        return f"{symbol}{_format_amount_k(min_)}-{_format_amount_k(max_)}"
    if min_:
        return f"{symbol}{_format_amount_k(min_)}+"
    if max_:
        return f"Up to {symbol}{_format_amount_k(max_)}"
    return "Not disclosed"


def _job_to_prompt(job: dict) -> str:
    location = _location_str(job)

    salary_min = job.get("salaryMin")
    salary_max = job.get("salaryMax")
    currency = job.get("salaryCurrency") or ""
    salary = f"{salary_min}-{salary_max} {currency}" if salary_min or salary_max else "Not disclosed"

    return f"""
Job title: {job.get('name', 'Unknown')}
Company: {job.get('organizationName', 'Unknown')}
Company industry: {job.get('organizationIndustry', 'Unknown')}
Company employees: {job.get('organizationEmployees', 'Unknown')}
Location(s): {location}
Remote: {job.get('remote', 'Unknown')}
Contract type: {job.get('contractType', 'Unknown')}
Experience level required (years): {job.get('experienceLevel', 'Unknown')}
Salary: {salary}
Category: {job.get('category', '')} / {job.get('subcategory', '')}
Sectors: {', '.join(_stringify_list(job.get('sectors')))}
Published: {job.get('publishedAt', 'Unknown')}
URL: {job.get('url', '')}

Summary: {job.get('summary', '')}

Key missions:
{chr(10).join('- ' + m for m in _stringify_list(job.get('keyMissions')))}

Skills required: {', '.join(_stringify_list(job.get('skills')))}
Tools: {', '.join(_stringify_list(job.get('tools')))}

Team / reporting: {job.get('team', '')}

Full description:
{_strip_html(job.get('description', ''))}

Ideal profile:
{_strip_html(job.get('profile', ''))}

Company summary:
{_strip_html(job.get('companySummary', ''))}
""".strip()


def score_job(job: dict, client: Anthropic, criteria_text: str, criteria: dict) -> dict:
    system_prompt = f"""You are scoring job listings for Paul Ugoh's automated job search pipeline. Below is his complete scoring criteria in YAML. Apply it exactly:

1. Check hard_skips first. If any hard skip rule applies, set hard_skip=true, explain which rule, and set fit_score=0.
2. Otherwise, compute fit_score (0-100) as a weighted sum across scoring_dimensions using their stated weights.
3. Ground why_it_works and hard_gaps in the proof_points and known_gaps listed below where relevant. Be honest about gaps — do not paper over them.
4. Fill in trajectory_check and recommendation per the output_format guidance.

Submit your assessment via the submit_job_assessment tool only.

--- SCORING CRITERIA (YAML) ---
{criteria_text}
--- END CRITERIA ---"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        thinking={"type": "adaptive"},
        output_config={"effort": EFFORT},
        system=system_prompt,
        tools=[SUBMIT_ASSESSMENT_TOOL],
        tool_choice={"type": "tool", "name": "submit_job_assessment"},
        messages=[{"role": "user", "content": _job_to_prompt(job)}],
    )

    tool_use = next(b for b in response.content if b.type == "tool_use")
    assessment = tool_use.input

    thresholds = criteria["thresholds"]
    if assessment["hard_skip"]:
        label = "skip"
    elif assessment["fit_score"] >= thresholds["apply"]:
        label = "apply"
    elif assessment["fit_score"] >= thresholds["borderline"]:
        label = "borderline"
    else:
        label = "skip"

    return {
        "job_title": job.get("name"),
        "company": job.get("organizationName"),
        "location": _location_str(job),
        "salary_note": _format_salary_note(job),
        "url": job.get("url"),
        "threshold": label,
        **assessment,
    }
