# Job Search Pipeline

A fully automated job discovery and scoring system. Every morning at 8am it fetches fresh listings from Welcome to the Jungle, scores each one against a structured YAML criteria file using Claude, and logs anything worth applying to directly into a Google Sheet — without touching a keyboard.

---

## What it does

Manual job hunting is slow. You open five tabs, read the same boilerplate twelve times, and still miss roles because you checked on Tuesday but the good one posted Wednesday. This pipeline runs daily and does the filtering work automatically.

**The full flow:**

```
GitHub Actions (8am daily)
    → Apify scrapes Welcome to the Jungle
        → Claude scores each role against scoring_criteria.yaml
            → Google Sheets logs every apply/borderline match
```

Each scored result includes:

- A fit score (0–100) across six weighted dimensions
- 3–5 genuine strengths, grounded in real proof points
- 2–4 honest hard gaps — no papering over them
- A trajectory check: does this role move toward the target, or away from it?
- A one-sentence recommendation: apply / borderline / skip

Anything that scores 70+ gets logged to the tracker as `Flagged`. Anything 60–69 goes in as `Borderline`. Below 60 is skipped silently.

---

## Architecture

```
.github/
  workflows/
    job-pipeline.yml     # Cron schedule + manual trigger

config.py                # Keywords, location profiles, model settings
fetch_jobs.py            # Apify client — calls clearpath/welcome-to-the-jungle-jobs-api
score_job.py             # Claude scoring — structured tool use, YAML criteria
webhook.py               # Google Apps Script POST — one request per match
main.py                  # Entry point — orchestrates the full pipeline

scoring_criteria.yaml    # Edit this to change what gets surfaced
requirements.txt
.env.example
```

---

## Scoring criteria

Everything that drives the model's decisions lives in `scoring_criteria.yaml`. No code changes needed to update the scoring logic.

**Six weighted dimensions (total = 100):**

| Dimension | Weight | What it measures |
|---|---|---|
| Role type match | 25 | Does the function match product ops / AI delivery / programme management? |
| AI + automation relevance | 20 | Is AI genuinely central to the role, or a bullet point in a list of 20? |
| Seniority and scope | 20 | Right level for 4 years' experience — not too junior, not Director-level |
| Salary and location | 15 | London hybrid (max 3 days), £60–70k target range |
| Company type and trajectory | 10 | AI-native, Series A–C, inside a product team |
| Structural blockers | 10 | SQL gap, no formal PM background, no SaaS implementation experience |

**Hard skips** (rejected before scoring):
- Contract or FTC roles
- Below £50k
- 5 days in office
- Excluded locations (Manchester, Glasgow, Edinburgh)
- Excluded domains (private equity, investment banking, legal services)

**Thresholds:**
- `70+` → Apply
- `60–69` → Borderline (flagged for manual review)
- `<60` → Skip

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/pu-45/job-search-pipeline
cd job-search-pipeline
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Fill in `.env`:

```
APIFY_TOKEN=your_apify_token_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
GOOGLE_SHEETS_WEBHOOK_URL=your_apps_script_web_app_exec_url_here
```

### 3. Set up the Google Sheet

The pipeline posts directly to a Google Apps Script web app endpoint. The Apps Script reads `e.postData.contents` as JSON and writes a row to the tracker sheet.

Columns expected (A–R): Application Date, Last Update, Company, Job Title, Location, Application Status, Networking Count, Job Source, Applied Platform, Link to Job Posting, Strengths, Weakness, First Stage, Second Stage, Third Stage, Fourth Stage, Resume, Notes.

### 4. Run locally

```bash
python main.py
```

Output:

```
[fetch] Run 1/24: "Operations Manager" in London
[fetch]   -> 8 jobs
...
[fetch] Total unique jobs: 67

[score] 1/67: Product Operations Lead @ Metaview
[score]   -> 78/100 (apply)
[score] 2/67: Business Operations Manager @ Notion
[score]   -> 72/100 (apply)
...

=== Summary: 67 jobs scored ===
Apply: 4 | Borderline: 6 | Skip: 57

[webhook] Logging 10 apply/borderline jobs to Google Sheet...
[webhook] Done: 10/10 logged successfully
```

### 5. Schedule it (GitHub Actions)

Add three secrets to the repo (`Settings → Secrets and variables → Actions`):

- `APIFY_TOKEN`
- `ANTHROPIC_API_KEY`
- `GOOGLE_SHEETS_WEBHOOK_URL`

The workflow in `.github/workflows/job-pipeline.yml` fires at 8am UK time every day. It handles BST/GMT automatically — two cron triggers with a time-check step that lets only one through.

To trigger manually: `Actions → Job Pipeline → Run workflow`.

---

## Customising the search

**Change what roles get fetched** — edit `KEYWORDS` in `config.py`:

```python
KEYWORDS = [
    "Operations Manager",
    "Product Operations",
    "AI Delivery",
    # add or remove as needed
]
```

**Change how roles are scored** — edit `scoring_criteria.yaml`. No code changes needed. The scoring dimensions, weights, hard skips, proof points, and known gaps are all defined there and passed to the model verbatim.

**Change the model or effort level** — edit `config.py`:

```python
MODEL = "claude-opus-5"
EFFORT = "medium"  # low | medium | high | xhigh | max
```

Raising `EFFORT` to `high` or `xhigh` produces more careful scoring at higher API cost.

---

## How the scoring works

Each job is converted to a structured prompt (`score_job.py`) and sent to Claude with:

- The full `scoring_criteria.yaml` as system context
- A `submit_job_assessment` tool with a strict JSON schema
- `tool_choice` forced — the model must use the tool (no free-text workarounds)

The tool schema defines every output field: `hard_skip`, `fit_score`, `why_it_works`, `hard_gaps`, `trajectory_check`, `recommendation`, `role_summary`, `caveats`. Structured outputs mean the results are always parseable and consistent.

Proof points from the YAML (Python AE script, five-market acceleration, 66% completion rate improvement) are passed to the model as context, so strengths are grounded in real examples rather than generic observations.

---

## Proof points referenced in scoring

| ID | What it is |
|---|---|
| `python_ae_script` | Automated adverse event detection, pharmacovigilance review — hours to seconds |
| `job_search_automation` | This pipeline. Built it to solve the problem it's solving |
| `completion_rate_66` | Data analysis → process redesign → 66% improvement in completion rates |
| `five_market_acceleration` | Rebuilt stalled cross-functional programme across 5 markets, 50% acceleration |
| `retention_200k` | Retained £200k programme at risk through governance rebuild |
| `supplier_negotiation_30` | 30% supplier cost reduction via structured business case |

---

## Production considerations

The pipeline currently runs on GitHub Actions with secrets stored as encrypted environment variables. For a shared team dependency the natural next step would be: move to a shared organisation repo, route logs to an observability platform (Datadog or equivalent), and add a Slack alert for pipeline failures.

---

## Requirements

```
anthropic
apify-client
beautifulsoup4
python-dotenv
pyyaml
requests
```

Python 3.12+
