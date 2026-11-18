"""Data dictionary: docs/data_dictionary.yaml (written by people) + live statistics
from the actual files -> docs/data_dictionary.md (for the report).

Also checks that the YAML and the data agree, which the DQ step reports as a rule:
a column in the data with no description, or a described column that no longer exists.

    PYTHONPATH=src python -m cyber_pipeline.quality.data_dictionary
"""
from __future__ import annotations

import pandas as pd
import yaml

from cyber_pipeline.utils.logging_utils import get_logger
from cyber_pipeline.utils.paths import CLEANED, INTEGRATED, PROJECT_ROOT

log = get_logger("dictionary")
YAML_PATH = PROJECT_ROOT / "docs" / "data_dictionary.yaml"
MD_PATH = PROJECT_ROOT / "docs" / "data_dictionary.md"
LAYER_DIR = {"cleaned": CLEANED, "integrated": INTEGRATED}


# อ่านไฟล์คำอธิบายคอลัมน์ (data_dictionary.yaml)
def load() -> dict:
    with open(YAML_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


# อ่านตารางจริงที่ต้องการอธิบาย (ถ้ายังไม่มีไฟล์ จะคืนค่าว่าง)
def read_table(meta: dict, name: str) -> pd.DataFrame | None:
    path = LAYER_DIR[meta["layer"]] / f"{name}.csv"
    if not path.exists():
        return None
    return pd.read_csv(path, keep_default_na=False, na_values=[""])


# หาคำอธิบายของทุกคอลัมน์ในตาราง รวมถึงคอลัมน์ที่ยกมาจากตารางอื่น
def column_docs(spec: dict, name: str) -> dict:
    """Own columns, plus columns documented in the tables this one inherits from."""
    meta = spec["tables"][name]
    docs = {}
    for parent in meta.get("inherits", []):
        docs.update(spec["tables"][parent]["columns"])
    docs.update(meta["columns"])
    return docs


# เช็กว่าทุกคอลัมน์มีคำอธิบายครบ และไม่มีคำอธิบายของคอลัมน์ที่ไม่มีอยู่จริง
def coverage(spec: dict) -> list[dict]:
    """Per table: columns in data but not documented, and documented but not in data."""
    out = []
    for name, meta in spec["tables"].items():
        df = read_table(meta, name)
        if df is None:
            out.append({"table": name, "undocumented": [], "missing_in_data": ["<file missing>"]})
            continue
        docs = column_docs(spec, name)
        out.append({"table": name,
                    "undocumented": [c for c in df.columns if c not in docs],
                    "missing_in_data": [c for c in meta["columns"] if c not in df.columns]})
    return out


# คำนวณข้อมูลสรุปของคอลัมน์: เป็นตัวเลขหรือข้อความ มีค่ากี่ % ค่าต่ำสุด-สูงสุด
def _stats(s: pd.Series) -> tuple[str, str, str]:
    nn = f"{s.notna().mean() * 100:.0f}%"
    if pd.api.types.is_bool_dtype(s):
        return "bool", nn, f"true {s.mean() * 100:.0f}%"
    if pd.api.types.is_numeric_dtype(s):
        if s.notna().any():
            if pd.api.types.is_integer_dtype(s):
                return "int", nn, f"{s.min()} – {s.max()}"
            return "float", nn, f"{s.min():,.4g} – {s.max():,.4g}"
        return "float", nn, "–"
    vals = s.dropna().astype(str).unique()
    shown = ", ".join(sorted(vals)[:4]) + (" …" if len(vals) > 4 else "")
    return "text", nn, f"{len(vals)} values: {shown}"


# จัดข้อความให้ใส่ในตารางได้ไม่พัง
def _cell(x) -> str:
    return str(x).replace("|", "/").replace("\n", " ") if x is not None else ""


# สร้างเนื้อหาไฟล์ data_dictionary.md จากคำอธิบาย + ตัวเลขจริงของข้อมูล
def render(spec: dict) -> str:
    L = ["# Data dictionary", "",
         "สร้างอัตโนมัติจาก `docs/data_dictionary.yaml` + ข้อมูลจริง ห้ามแก้ไฟล์นี้ตรงๆ "
         "ให้แก้ที่ YAML แล้วรันใหม่ (`python -m cyber_pipeline.quality.data_dictionary`)", "",
         "⚠ = ความหมายต้องตรวจกับ codebook / เอกสารทางการอีกครั้ง", "", "## Sources", "",
         "| Source | Provider | License | Period | Fetched | Raw files |", "|---|---|---|---|---|---|"]
    for k, s in spec["sources"].items():
        flag = " ⚠" if s.get("verify") else ""
        L.append(f"| {k} | {_cell(s['provider'])} ([link]({s['url'].split(' ')[0]})) | "
                 f"{_cell(s['license'])}{flag} | {_cell(s['period'])} | {_cell(s.get('fetched', ''))} | `{_cell(s['raw'])}` |")
    for name, meta in spec["tables"].items():
        df = read_table(meta, name)
        docs = column_docs(spec, name)
        L += ["", f"## `{name}`", "",
              f"- **Layer:** {meta['layer']}  ·  **Grain:** {meta['grain']}  ·  **Key:** "
              f"`{', '.join(meta['key'])}`  ·  **Source:** {meta['source']}"]
        if df is None:
            L.append("- ไฟล์ยังไม่ถูกสร้าง"); continue
        L += [f"- **Rows:** {len(df):,}  ·  **Columns:** {df.shape[1]}", "",
              "| Column | Type | Non-null | Range / values | Unit | Description | NaN means |",
              "|---|---|---|---|---|---|---|"]
        for c in df.columns:
            d = docs.get(c, {})
            typ, nn, rng = _stats(df[c])
            desc = _cell(d.get("description", "**ยังไม่มีคำอธิบาย**")) + (" ⚠" if d.get("verify") else "")
            L.append(f"| `{c}` | {typ} | {nn} | {_cell(rng)} | {_cell(d.get('unit', ''))} | "
                     f"{desc} | {_cell(d.get('missing', ''))} |")
    return "\n".join(L) + "\n"


# บันทึกไฟล์ data_dictionary.md และเตือนถ้ามีคอลัมน์ที่ยังไม่มีคำอธิบาย
def main() -> list[dict]:
    spec = load()
    MD_PATH.write_text(render(spec), encoding="utf-8")
    cov = coverage(spec)
    for c in cov:
        if c["undocumented"] or c["missing_in_data"]:
            log.warning("%s: undocumented=%s missing_in_data=%s", c["table"], c["undocumented"], c["missing_in_data"])
    log.info("wrote %s", MD_PATH.name)
    return cov


if __name__ == "__main__":
    main()
