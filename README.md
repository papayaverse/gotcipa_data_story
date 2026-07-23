# GotCIPA data story

Public aggregate report from [gotcipa.com](https://gotcipa.com) audit activity — regenerated locally from private CSV exports.

**Published results:** [`output/data_story.md`](output/data_story.md) · [`output/charts/`](output/charts/) · [`output/aggregates.json`](output/aggregates.json)

Raw audit data (emails, URLs) stays on your machine and is **not** committed.

## Quick start (local regen)

1. Drop fresh Supabase exports into `data/` (gitignored):
   - `data/audit_leads.csv`
   - `data/audit_requests.csv`
2. Install deps (once):

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

3. Build:

   ```bash
   .venv/bin/python scripts/build_story.py
   ```

4. **Public repo:** commit `output/data_story.md`, `output/charts/*.png`, and `output/aggregates.json`
5. **Local preview:** open `output/liz_data_story.html` in a browser (gitignored), or view the markdown on GitHub

   ```bash
   cd output && python3 -m http.server 8765
   # → http://127.0.0.1:8765/liz_data_story.html
   ```

## What gets committed vs ignored

| Path | In git? |
|------|---------|
| `data/*.csv` | No — PII |
| `output/data_story.md` | Yes — aggregate narrative |
| `output/charts/*.png` | Yes — seaborn charts embedded in markdown |
| `output/aggregates.json` | Yes — machine-readable metrics |
| `output/liz_data_story.html` | No — optional local HTML preview |
| `*.docx`, root `*.csv` exports | No |

## CSV format

- Delimiter: semicolon (`;`) or comma (`,`) — auto-detected.
- **Leads:** `id`, `email`, `audit_url`, `verdict`, `created_at`
- **Requests:** `id`, `audit_id`, `url`, `accept_session_id`, `reject_session_id`, `gpc_session_id`, `created_at`

Optional future columns (used when present): `sector`, `employee_band`, `tracker_vendors`.

## What is measured vs inferred

| Metric | Basis |
|--------|--------|
| Weekly audit runs, leads, 14-day windows | Direct from `created_at` |
| Unique domains / emails | Direct from URLs and emails |
| Repeat testers (≥5 runs) | Direct from request counts |
| Org type, size proxy, sector | **Inferred** from email/URL TLDs and domain keywords |
| Geography / IP | **Not collected** |

Internal Papaya, founder `.edu`, and disposable test emails are excluded from “user” lead counts.

## Narrative context

Built to support CIPA reform advocacy (e.g. [stopshakedowns.com](https://stopshakedowns.com)): aggregate proof of rising GotCIPA usage alongside demand-letter pressure, with small business / nonprofit / public-agency framing.
