"""Single source of truth for data folder paths.

data/raw/         original files exactly as downloaded (never edited)
data/cleaned/     each source cleaned on its own (types, missing, duplicates, country codes)
data/integrated/  all sources joined into one table
data/analytical/  final dataset used by EDA, models and the web app
"""
from pathlib import Path
import os

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", Path(__file__).resolve().parents[3]))
DATA = PROJECT_ROOT / "data"
RAW, CLEANED, INTEGRATED, ANALYTICAL = (DATA / x for x in ("raw", "cleaned", "integrated", "analytical"))
REPORTS = PROJECT_ROOT / "reports"


def raw_path(source: str, ingest_date: str) -> Path:
    """Raw files are immutable snapshots: data/raw/<source>/ingest_date=YYYY-MM-DD/"""
    p = RAW / source / f"ingest_date={ingest_date}"
    p.mkdir(parents=True, exist_ok=True)
    return p
