"""Log apply/borderline job matches to Paul's Google Sheet via the Apps Script webhook.

Sends one POST per job as a JSON body — this endpoint's doPost(e) does
JSON.parse(e.postData.contents), confirmed live (a form-encoded body returns
HTTP 200 with {"success": false, "error": "... is not valid JSON"}).
"""
import json
import os
import time
from datetime import date

import requests
from dotenv import load_dotenv

from config import RESULTS_PATH

load_dotenv()

STATUS_MAP = {"apply": "Flagged", "borderline": "Borderline"}
RECOMMENDATION_LABEL = {"apply": "Apply", "borderline": "Borderline", "skip": "Skip"}

REQUEST_TIMEOUT = 30
DELAY_BETWEEN_REQUESTS = 1.0  # seconds — be polite to the Apps Script quota


def _bullet_list(items) -> str:
    """One '- ' bullet per line, no truncation — each item is already a
    complete thought from the scorer."""
    return "\n".join(f"- {item}" for item in (items or []))


def _build_notes(result: dict) -> str:
    label = RECOMMENDATION_LABEL.get(result.get("threshold"), "Borderline")
    parts = [
        result.get("role_summary", ""),
        f"Salary: {result.get('salary_note', 'Not disclosed')}",
        f"Fit: {result.get('fit_score')}/100 — {label}",
    ]
    caveats = (result.get("caveats") or "").strip()
    if caveats:
        parts.append(caveats)
    return " | ".join(p for p in parts if p)


def build_payload(result: dict) -> dict:
    today = date.today().strftime("%d/%m/%y")

    return {
        "applicationDate": today,
        "lastUpdate": today,
        "company": result.get("company", ""),
        "jobTitle": result.get("job_title", ""),
        "location": result.get("location", ""),
        "status": STATUS_MAP.get(result.get("threshold"), "Flagged"),
        "jobSource": "Welcome to the Jungle",
        "platform": "Welcome to the Jungle",
        "jobUrl": result.get("url", ""),
        "strengths": _bullet_list(result.get("why_it_works")),
        "weaknesses": _bullet_list(result.get("hard_gaps")),
        "notes": _build_notes(result),
    }


def log_result(result: dict, webhook_url: str) -> bool:
    payload = build_payload(result)
    try:
        response = requests.post(webhook_url, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        try:
            body = response.json()
        except ValueError:
            print(f"[webhook]   ERROR: non-JSON response ({response.status_code}) {response.text[:200]!r}")
            return False
        if body.get("success") is False:
            print(f"[webhook]   ERROR: {body.get('error', body)}")
            return False
        print(f"[webhook]   -> logged ({response.status_code}) {body}")
        return True
    except requests.RequestException as exc:
        print(f"[webhook]   ERROR logging {result.get('job_title')}: {exc}")
        return False


def log_results(results: list[dict]) -> None:
    webhook_url = os.environ.get("GOOGLE_SHEETS_WEBHOOK_URL")
    if not webhook_url:
        raise RuntimeError(
            "GOOGLE_SHEETS_WEBHOOK_URL not set. Copy .env.example to .env and fill it in."
        )

    to_log = [r for r in results if r.get("threshold") in ("apply", "borderline")]
    print(f"[webhook] Logging {len(to_log)} apply/borderline jobs to Google Sheet...")

    logged = 0
    for i, result in enumerate(to_log, start=1):
        print(f"[webhook] {i}/{len(to_log)}: {result.get('job_title')} @ {result.get('company')}")
        if log_result(result, webhook_url):
            logged += 1
        if i < len(to_log):
            time.sleep(DELAY_BETWEEN_REQUESTS)

    print(f"[webhook] Done: {logged}/{len(to_log)} logged successfully")


if __name__ == "__main__":
    with open(RESULTS_PATH, encoding="utf-8") as f:
        all_results = json.load(f)
    log_results(all_results)
