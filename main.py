"""Job pipeline: fetch WTTJ listings from Apify, score them against Paul's
criteria, and log apply/borderline matches to his Google Sheet."""
import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv

from config import RESULTS_PATH
from fetch_jobs import fetch_jobs
from score_job import load_criteria, score_job
from webhook import log_results

load_dotenv()


def main() -> None:
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set. Copy .env.example to .env and fill it in.")

    client = Anthropic(api_key=anthropic_key)
    criteria_text, criteria = load_criteria()

    jobs = fetch_jobs()

    results = []
    for i, job in enumerate(jobs, start=1):
        title = job.get("name", "Unknown")
        company = job.get("organizationName", "Unknown")
        print(f"[score] {i}/{len(jobs)}: {title} @ {company}")
        try:
            result = score_job(job, client, criteria_text, criteria)
        except Exception as exc:
            print(f"[score]   ERROR scoring job: {exc}")
            continue
        results.append(result)
        print(f"[score]   -> {result['fit_score']}/100 ({result['threshold']})")

    results.sort(key=lambda r: r["fit_score"], reverse=True)

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    apply_count = sum(1 for r in results if r["threshold"] == "apply")
    borderline_count = sum(1 for r in results if r["threshold"] == "borderline")
    skip_count = sum(1 for r in results if r["threshold"] == "skip")

    print(f"\n=== Summary: {len(results)} jobs scored ===")
    print(f"Apply: {apply_count} | Borderline: {borderline_count} | Skip: {skip_count}")
    print(f"Results saved to {RESULTS_PATH}")

    print("\n--- Apply / Borderline ---")
    for r in results:
        if r["threshold"] in ("apply", "borderline"):
            print(
                f"[{r['threshold'].upper():>10}] {r['fit_score']:>3}/100  "
                f"{r['job_title']} @ {r['company']}\n           {r['url']}"
            )

    print()
    log_results(results)


if __name__ == "__main__":
    main()
