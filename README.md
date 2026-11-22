# causes-of-cyberattacks

Country-year analysis of factors **associated** with the volume and type of publicly reported
cyberattacks, integrating 5 sources (cyber events, economy, digital infrastructure,
cyber exposure, national cybersecurity readiness). Associations only — no causal claims.

- Folders & pipeline steps: [docs/architecture.md](docs/architecture.md)
- Step-by-step Airflow guide (Thai): [docs/airflow_guide.md](docs/airflow_guide.md)

## Run the pipeline

**With Airflow (Docker):**
```bash
docker compose up --build          # first time takes a few minutes
# open http://localhost:8080, user "admin"
# password: docker exec cyberattacks-airflow cat /opt/airflow/standalone_admin_password.txt
# then trigger the DAG "cyber_pipeline"
```

**Without Docker (same steps, run by hand):**
```bash
pip install -r requirements.txt
export PYTHONPATH=src            # PowerShell: $env:PYTHONPATH="src"
python -m cyber_pipeline.cleaning.run_cleaning
python -m cyber_pipeline.transform.join
python -m cyber_pipeline.quality.data_dictionary
python -m cyber_pipeline.quality.dq_checks
python -m cyber_pipeline.storage.load_sqlite
```

| Output | Where |
|---|---|
| Cleaned tables | `data/cleaned/` |
| Joined country × year table | `data/integrated/country_year.csv` |
| Database (for analysis & web) | `data/warehouse/cyberattacks.db` |
| Data quality report | `reports/dq/dq_summary.md` |
| Data dictionary | `docs/data_dictionary.md` |

## Phase status
| # | Phase | Status |
|---|---|---|
| 1 | Repository inspection & setup | done |
| 2 | Data acquisition | done (fetch scripts in `data/data_API/`) |
| 3–8 | Cleaning → Integration → DQ → Data dictionary → SQLite | done (pandas; PySpark port todo) |
| 9 | Airflow orchestration | DAG written, needs a Docker test run |
| 10–15 | EDA → Hypotheses → Features → Baseline → Models → Interpretation | todo |
| 16–17 | Web app, report, presentation | todo |
