# causes-of-cyberattacks

Country-year analysis of factors **associated** with the volume and type of publicly reported
cyberattacks, integrating 5 sources (cyber events, economy, digital infrastructure,
cyber exposure, national cybersecurity readiness). Associations only — no causal claims.

- Folders & pipeline steps: [docs/architecture.md](docs/architecture.md)

## Quick start (filled in as phases complete)
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Phase 9: docker compose -f docker/docker-compose.yaml up
```

## Phase status
| # | Phase | Status |
|---|---|---|
| 1 | Repository inspection & setup | done (awaiting source confirmation) |
| 2 | Data acquisition | todo |
| 3–8 | Ingestion → Cleaning → Transform → Integration → DQ → Storage | todo |
| 9 | Airflow orchestration | todo |
| 10–15 | EDA → Hypotheses → Features → Baseline → Models → Interpretation | todo |
| 16–17 | Web app, report, presentation | todo |
