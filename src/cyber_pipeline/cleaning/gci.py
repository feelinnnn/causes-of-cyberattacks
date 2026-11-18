"""Source E (part): ITU Global Cybersecurity Index, editions 2018, 2020, 2024.

Output is one row per country per EDITION, not per year: ITU did not publish in
2019, 2021-2023, and filling those years is a modelling choice for later.
"""
from __future__ import annotations

import pandas as pd

from .common import CleanLog, read_raw_csv, write_cleaned
from .countries import build_reference, name_lookup, normalize_name

SRC = "gci"
PILLARS = ["Legal Measures", "Technical Measures", "Organizational Measures",
           "Capacity Development Measures", "Cooperation Measures"]


# clean ข้อมูล GCI 3 ฉบับ (2018, 2020, 2024) ที่หน้าตาไม่เหมือนกัน
# ปรับคะแนนให้เต็ม 100 เหมือนกันทุกฉบับ และเปลี่ยนชื่อประเทศเป็นรหัส
def run(clog: CleanLog) -> None:
    ref = build_reference()
    lut = name_lookup(ref)
    iso2_to_3 = dict(zip(ref["iso2"], ref["iso3"]))

    # 2018: score 0-1 with ISO2 codes -> x100 so all editions share a 0-100 scale.
    g18 = read_raw_csv("sourceE/GCI_2018_Raw.csv")
    g18 = pd.DataFrame({"edition": 2018, "name_raw": g18["country_name"],
                        "iso3": g18["country_code"].map(iso2_to_3),
                        "gci_score_100": g18["gci_score"] * 100, "gci_rank": g18["gci_global_rank"],
                        "gci_tier": pd.NA, "gci_flag": ""})

    # 2020: 0-100 score, names only, some names end in * or ** (ITU footnote marks).
    # The marks are kept as gci_flag; their meaning must be checked in the ITU report.
    g20 = read_raw_csv("sourceE/GCI_2020_Raw.csv")
    g20 = pd.DataFrame({"edition": 2020, "name_raw": g20["Country Name"],
                        "iso3": g20["Country Name"].map(lambda n: lut.get(normalize_name(n))),
                        "gci_score_100": g20["Score"], "gci_rank": g20["Rank"], "gci_tier": pd.NA,
                        "gci_flag": g20["Country Name"].str.extract(r"(\*+)$")[0].fillna("")})

    # 2024: no total score or rank, only 5 pillars (max 20 each) and a tier.
    # Sum of pillars = total on the same 0-100 scale. Pillars are kept as columns too.
    g24r = read_raw_csv("sourceE/GCI_2024_Raw.csv")
    g24 = pd.DataFrame({"edition": 2024, "name_raw": g24r["Country Name"],
                        "iso3": g24r["Country Name"].map(lambda n: lut.get(normalize_name(n))),
                        "gci_score_100": g24r[PILLARS].sum(axis=1, min_count=5), "gci_rank": pd.NA,
                        "gci_tier": g24r["Tier"], "gci_flag": ""})
    for p in PILLARS:
        g24["pillar_" + p.split()[0].lower()] = g24r[p]

    df = pd.concat([g18, g20, g24], ignore_index=True)
    unmatched = df[df["iso3"].isna()]
    clog.add(SRC, "map names/ISO2 to ISO3", len(df), len(df) - len(unmatched),
             "unmatched: " + "; ".join(f"{e}:{n}" for e, n in zip(unmatched.edition, unmatched.name_raw)))
    df = df[df["iso3"].notna()]

    bad = ~df["gci_score_100"].between(0, 100)
    clog.add(SRC, "range check gci_score_100 in [0,100]", len(df), len(df), f"{int(bad.sum())} bad")
    write_cleaned(df, "gci_country_edition", ["iso3", "edition"])
