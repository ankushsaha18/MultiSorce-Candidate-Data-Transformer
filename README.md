# Multi-Source Candidate Data Transformer

This project reads candidate data from a structured Recruiter CSV and an unstructured Resume PDF, normalizes the data, merges it into one canonical candidate profile, adds provenance/confidence, validates the result, and writes JSON output.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"
```

## Run Default Output

```bash
python3 main.py \
  --csv samples/recruiter_csv/ankush_saha.csv \
  --resume samples/resume_pdf/ankush_saha.pdf \
  --config configs/default_projection.json \
  --output outputs/result.json
```

The default config outputs the canonical-style profile:

- `candidate_id`
- `full_name`
- `emails`
- `phones`
- `location`
- `links`
- `headline`
- `years_experience`
- `skills`
- `experience`
- `education`
- `confidence`
- `provenance`
- `overall_confidence`

## Run Custom Config Output

```bash
python3 main.py \
  --csv samples/recruiter_csv/ankush_saha.csv \
  --resume samples/resume_pdf/ankush_saha.pdf \
  --config configs/custom_projection.json \
  --output outputs/custom_result.json
```

The custom config demonstrates runtime projection. It renames/select s fields such as:

- `name`
- `title`
- `primary_email`
- `primary_phone`
- `top_skills`
- `confidence`
- `overall_confidence`

It also omits missing values because `on_missing` is set to `omit`.

## Run Tests

```bash
pytest -q
```

## Notes

- Phones are normalized to E.164.
- Dates are normalized to `YYYY-MM`.
- Skills are canonicalized.
- Resume values take priority over CSV values during conflicts.
- Missing or malformed inputs log warnings instead of crashing.
