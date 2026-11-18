"""Source C (part): CAIDA RouteViews prefix-to-AS + AS-to-organisation, one snapshot per year (1 July).

Output: per country-year counts of routed ASNs, prefixes and IPv4 address space.
Country = registration country of the organisation that owns the ASN (not where IPs are used).
"""
from __future__ import annotations

import gzip
from collections import defaultdict

import pandas as pd

from .common import YEAR_MAX, YEAR_MIN, CleanLog, write_cleaned
from .common import RAW

SRC = "bgp"
DIR = RAW / "sourceC"


# เช็กว่าหมายเลขเครือข่าย (ASN) นี้เป็นของจริงบนอินเทอร์เน็ต ไม่ใช่เลขที่สงวนไว้ใช้ภายใน
def is_public_asn(a: int) -> bool:
    """Drop reserved / private / documentation ASNs (RFC 6996, 5398, 7300, 6793)."""
    return not (a == 0 or a == 23456 or 64496 <= a <= 131071 or a >= 4200000000)


# อ่านไฟล์ CAIDA แล้วได้คำตอบว่า เครือข่ายแต่ละหมายเลขเป็นขององค์กรในประเทศอะไร
def load_as_country(path) -> dict[int, str]:
    """as-org2info has two tables in one file: org_id->country and asn->org_id."""
    org_cc, asn_org, mode = {}, {}, None
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("# format:org_id"):
                mode = "org"; continue
            if line.startswith("# format:aut"):
                mode = "aut"; continue
            if line.startswith("#") or not mode:
                continue
            p = line.rstrip("\n").split("|")
            if mode == "org" and len(p) >= 4:
                org_cc[p[0]] = p[3].strip()
            elif mode == "aut" and len(p) >= 4 and p[0].isdigit():
                asn_org[int(p[0])] = p[3]
    return {a: org_cc.get(o, "") for a, o in asn_org.items()}


# อ่านช่องเจ้าของ IP block ซึ่งบางแถวมีหลายเจ้าของ เช่น "24151_24409"
# แยกออกมาเป็นรายการ และตัดเลขเครือข่ายที่ไม่ใช่ของจริงทิ้ง
def parse_origins(field: str) -> list[int]:
    """'13335' -> [13335]; MOAS '24151_24409' -> both; AS-set '1,2' -> both. Private ASNs removed."""
    out = []
    for part in field.replace(",", "_").replace("{", "").replace("}", "").split("_"):
        if part.isdigit() and is_public_asn(int(part)):
            out.append(int(part))
    return sorted(set(out))


# นับขนาด IP ของแต่ละ block โดยไม่นับซ้ำ
# เช่น ถ้ามี block ใหญ่ และ block เล็กที่อยู่ข้างใน IP ส่วนที่ซ้อนกันจะนับให้ block เล็กเท่านั้น
def exclusive_slash24(prefixes: list[tuple[int, int]]) -> list[int]:
    """For CIDR blocks given as (start_/24_index, size_in_/24s), return each block's /24s
    NOT covered by a more specific block. CIDR blocks are either nested or disjoint, so a
    stack over blocks sorted by (start, -size) finds each block's direct children.
    This stops a /16 and the /24s announced inside it being counted twice."""
    order = sorted(range(len(prefixes)), key=lambda i: (prefixes[i][0], -prefixes[i][1]))
    excl = [s for _, s in prefixes]
    stack: list[int] = []
    for i in order:
        start, size = prefixes[i]
        while stack and prefixes[stack[-1]][0] + prefixes[stack[-1]][1] <= start:
            stack.pop()
        if stack:
            excl[stack[-1]] -= size  # direct parent loses the space of this child
        stack.append(i)
    return excl


# ประมวลผลข้อมูลเครือข่ายของ 1 ปี
# สรุปออกมาว่าแต่ละประเทศมีเครือข่ายกี่เครือข่าย และมี IP เท่าไหร่
def one_year(year: int, pfx_path, org_path, clog: CleanLog) -> pd.DataFrame:
    as_cc = load_as_country(org_path)
    blocks, origins = [], []
    n_total = n_bad_len = n_no_asn = n_moas = 0
    with gzip.open(pfx_path, "rt") as f:
        for line in f:
            n_total += 1
            ip, plen, asf = line.split()
            plen = int(plen)
            if not 8 <= plen <= 24:  # /25+ is not globally routed; </8 is a leak
                n_bad_len += 1; continue
            asns = parse_origins(asf)
            if not asns:
                n_no_asn += 1; continue
            n_moas += len(asns) > 1
            a, b, c, _ = (int(x) for x in ip.split("."))
            blocks.append(((a << 16) | (b << 8) | c, 1 << (24 - plen)))
            origins.append(asns)
    excl = exclusive_slash24(blocks)

    s24, npfx, asn_set = defaultdict(float), defaultdict(float), defaultdict(set)
    unmapped = 0.0
    for (_, _), ex, asns in zip(blocks, excl, origins):
        w = 1 / len(asns)  # MOAS: split the prefix equally between its origin ASNs
        for a in asns:
            cc = as_cc.get(a, "")
            if not cc:
                unmapped += ex * w; continue
            s24[cc] += ex * w
            npfx[cc] += w
            asn_set[cc].add(a)
    clog.add(SRC, f"{year}: parse pfx2as", n_total, len(blocks),
             f"{n_bad_len} bad prefix length, {n_no_asn} only private ASNs, {n_moas} MOAS split; "
             f"{unmapped / max(sum(excl), 1):.2%} of /24s have no AS-org country")
    return pd.DataFrame({"iso2": list(s24), "year": year,
                         "routed_asn_count": [len(asn_set[c]) for c in s24],
                         "routed_prefix_count": [npfx[c] for c in s24],
                         "ipv4_slash24_count": [s24[c] for c in s24]})


# ประมวลผลข้อมูลเครือข่ายทุกปี แล้วแปลงรหัสประเทศเป็นรหัส 3 ตัว
def run(clog: CleanLog, iso2_to_3: dict[str, str]) -> None:
    frames = []
    for y in range(YEAR_MIN, YEAR_MAX + 1):
        pfx = sorted((DIR / "BGP").glob(f"routeviews-rv2-{y}0701-*.pfx2as.gz"))
        org = sorted((DIR / "ip24prefix").glob(f"{y}070*.as-org2info.txt.gz"))
        if not pfx or not org:
            clog.add(SRC, f"{y}: missing snapshot", 0, 0, "skipped"); continue
        frames.append(one_year(y, pfx[0], org[0], clog))
    df = pd.concat(frames, ignore_index=True)
    # One CAIDA snapshot has the country written as a name instead of a code.
    df["iso2"] = df["iso2"].replace({"Sweden": "SE"})
    df = df.groupby(["iso2", "year"], as_index=False).agg(
        {"routed_asn_count": "sum", "routed_prefix_count": "sum", "ipv4_slash24_count": "sum"})
    df["iso3"] = df["iso2"].map(iso2_to_3)
    bad = df[df["iso3"].isna()]
    clog.add(SRC, "map ISO2 -> ISO3", len(df), len(df) - len(bad),
             "dropped codes: " + ",".join(sorted(set(bad.iso2))) +
             f" ({bad.ipv4_slash24_count.sum() / df.ipv4_slash24_count.sum():.2%} of /24s, EU = orgs registered as 'Europe')")
    out = df[df["iso3"].notna()][["iso3", "iso2", "year", "routed_asn_count",
                                  "routed_prefix_count", "ipv4_slash24_count"]]
    write_cleaned(out, "bgp_country_year", ["iso3", "year"])
