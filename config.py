"""Shared config for the job pipeline: Apify actor, search runs, Claude model.

The actor's `query` field does an AND-match across every word in the string —
a long "X OR Y OR Z" phrase matches nothing because no job title/description
contains all those words together. So instead of one combined query per
location, we run one actor call per (keyword, location profile) pair.

The `remote` filter also collapses results to near-zero when combined with
`datePosted` (confirmed: each works alone, 0-1 results together, even at a
30-day window) — this looks like a quirk in how the actor intersects those
two filters. We don't filter on `remote` here; Paul's scoring rubric already
penalizes poor location/remote fit via the salary_and_location dimension, so
that filtering happens at the scoring step instead of the search step.
"""
from pathlib import Path

ACTOR_ID = "clearpath/welcome-to-the-jungle-jobs-api"

CRITERIA_PATH = Path(__file__).parent / "scoring_criteria.yaml"
RESULTS_PATH = Path(__file__).parent / "results.json"

MODEL = "claude-opus-5"
EFFORT = "medium"  # low | medium | high | xhigh | max — raise if scoring feels shallow

MAX_ITEMS_PER_KEYWORD = 8  # jobs fetched per (keyword, location) call — raise for wider coverage

KEYWORDS = [
    "Operations Manager",
    "Delivery Manager",
    "Product Operations",
    "Business Operations",
    "AI Delivery",
    "Programme Manager",
    "Project Manager",
    "Delivery Lead",
]

LOCATION_PROFILES = [
    # London hybrid/remote
    {
        "websiteCountry": "en",
        "location": "London",
        "locationRadius": "20",
        "contractType": ["full_time"],
        "language": "en",
        "includeDetails": True,
        "sortBy": "date",
        "datePosted": "14",
        "searchOnlyInJobTitle": True,
    },
    # Brighton and South East
    {
        "websiteCountry": "en",
        "location": "Brighton",
        "locationRadius": "50",
        "contractType": ["full_time"],
        "language": "en",
        "includeDetails": True,
        "sortBy": "date",
        "datePosted": "14",
        "searchOnlyInJobTitle": True,
    },
    # Remote UK-wide
    {
        "websiteCountry": "en",
        "countryCode": "GB",
        "contractType": ["full_time"],
        "language": "en",
        "includeDetails": True,
        "sortBy": "date",
        "datePosted": "14",
        "searchOnlyInJobTitle": True,
    },
]

SEARCH_RUNS = [
    {**profile, "query": keyword, "maxItems": MAX_ITEMS_PER_KEYWORD}
    for profile in LOCATION_PROFILES
    for keyword in KEYWORDS
]
