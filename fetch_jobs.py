"""Fetch WTTJ job listings from Apify (clearpath/welcome-to-the-jungle-jobs-api)."""
import os

from apify_client import ApifyClient
from dotenv import load_dotenv

from config import ACTOR_ID, SEARCH_RUNS

load_dotenv()


def fetch_jobs() -> list[dict]:
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        raise RuntimeError("APIFY_TOKEN not set. Copy .env.example to .env and fill it in.")

    client = ApifyClient(token)
    seen_ids = set()
    jobs = []

    for i, run_input in enumerate(SEARCH_RUNS, start=1):
        place = run_input.get("location") or run_input.get("countryCode") or "remote"
        keyword = run_input.get("query", "")
        print(f"[fetch] Run {i}/{len(SEARCH_RUNS)}: {keyword!r} in {place}")
        run = client.actor(ACTOR_ID).call(run_input=run_input)
        dataset_id = run.default_dataset_id
        items = client.dataset(dataset_id).list_items().items
        print(f"[fetch]   -> {len(items)} jobs")

        for job in items:
            job_id = job.get("id") or job.get("url")
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)
            jobs.append(job)

    print(f"[fetch] Total unique jobs: {len(jobs)}")
    return jobs


if __name__ == "__main__":
    result = fetch_jobs()
    print(f"Fetched {len(result)} unique jobs.")
