import time
from pathlib import Path
import requests
import pandas as pd


# Mapping สำหรับรหัส GovData360 -> รหัสมาตรฐานบน World Bank Indicators API v2 (WGI)
WB_V2_FALLBACK_CODES = {
    "GOV_WGI_GE_EST": "GE.EST",
    "GOV_WGI_RL_EST": "RL.EST",
}


def fetch_wb_indicator(
    indicator_code: str,
    indicator_name: str,
    start_year: int = 2018,
    end_year: int = 2024,
) -> pd.DataFrame:
    base_url = f"https://api.worldbank.org/v2/country/all/indicator/{indicator_code}"
    params = {
        "date": f"{start_year}:{end_year}",
        "format": "json",
        "per_page": 2000,
        "page": 1,
    }

    records = []

    while True:
        max_retries = 5
        data = None
        for attempt in range(max_retries):
            try:
                response = requests.get(base_url, params=params, timeout=60)
                if response.status_code == 429:
                    print("    Rate limit hit. Waiting 3 seconds before retrying...")
                    time.sleep(3)
                    continue
                response.raise_for_status()
                data = response.json()
                break
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    print(f"    Failed after {max_retries} attempts: {e}")
                    return pd.DataFrame(records)
                time.sleep(3)

        # ตรวจสอบว่าได้ข้อมูลที่ถูกต้องหรือไม่
        if not isinstance(data, list) or len(data) < 2 or not isinstance(data[1], list):
            break

        for item in data[1]:
            if not isinstance(item, dict):
                continue
            # กรองเอาเฉพาะรายการที่มีรหัสประเทศ ISO 3 ตัวอักษร
            country_iso3 = item.get("countryiso3code")
            if country_iso3:
                country_info = item.get("country") if isinstance(item.get("country"), dict) else {}
                country_name = country_info.get("value", "")
                try:
                    year = int(item.get("date", 0))
                except (ValueError, TypeError):
                    continue

                records.append(
                    {
                        "country_code": country_iso3,
                        "country_name": country_name,
                        "year": year,
                        indicator_name: item.get("value"),
                    }
                )

        # ตรวจสอบว่าดึงครบทุกหน้า (Pagination) หรือยัง
        metadata = data[0] if isinstance(data[0], dict) else {}
        try:
            total_pages = int(metadata.get("pages", 1))
        except (ValueError, TypeError):
            total_pages = 1

        if params["page"] >= total_pages:
            break

        params["page"] += 1
        time.sleep(1)  # หน่วงเวลาเล็กน้อยเพื่อป้องกัน Rate Limit

    return pd.DataFrame(records)


def main():
    indicators = {
        "GOV_WGI_GE_EST": "gov_effectiveness",
        "GOV_WGI_RL_EST": "rule_of_law",
    }

    country_names = {}
    df_merged = None

    # ดึงข้อมูลแต่ละตัวและนำมา Merge เข้าด้วยกันด้วย (country_code, year)
    for code, col_name in indicators.items():
        print(f"Fetching {col_name} ({code})...")
        df_ind = fetch_wb_indicator(code, col_name, start_year=2018, end_year=2024)

        if df_ind.empty and code in WB_V2_FALLBACK_CODES:
            fallback_code = WB_V2_FALLBACK_CODES[code]
            print(f"  No data for {code} on v2 endpoint, retrying with WGI v2 code ({fallback_code})...")
            df_ind = fetch_wb_indicator(fallback_code, col_name, start_year=2018, end_year=2024)

        if df_ind.empty:
            print(f"  Warning: No data found for {col_name} ({code})")
            continue

        # เก็บ mapping ของรหัสประเทศ -> ชื่อประเทศ
        country_names.update(dict(zip(df_ind["country_code"], df_ind["country_name"])))

        # แยกคอลัมน์ country_name ออกก่อน merge เพื่อหลีกเลี่ยงชื่อคอลัมน์ซ้ำซ้อน
        df_ind_data = df_ind.drop(columns=["country_name"])

        if df_merged is None:
            df_merged = df_ind_data
        else:
            df_merged = pd.merge(
                df_merged,
                df_ind_data,
                on=["country_code", "year"],
                how="outer",
            )

    if df_merged is not None and not df_merged.empty:
        # เติมชื่อประเทศจาก country_names mapping
        df_merged["country_name"] = df_merged["country_code"].map(country_names)

        # จัดลำดับคอลัมน์: country_code, country_name, year, ตามด้วย indicators
        indicator_cols = [c for c in indicators.values() if c in df_merged.columns]
        df_merged = df_merged[["country_code", "country_name", "year"] + indicator_cols]

        # เรียงลำดับแถวตามประเทศและปี
        df_merged = df_merged.sort_values(by=["country_code", "year"]).reset_index(drop=True)

        # กำหนดตำแหน่งบันทึกไฟล์ CSV (บันทึกลง data/raw/world_bank_gov_wgi.csv)
        output_dir = Path(__file__).resolve().parent.parent / "raw"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "world_bank_gov_wgi.csv"

        # บันทึกเป็นไฟล์ CSV
        df_merged.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"\n[สำเร็จ] บันทึกไฟล์ CSV เรียบร้อยแล้วที่: {output_file}")
        print(f"ขนาดข้อมูล: {df_merged.shape[0]} แถว, {df_merged.shape[1]} คอลัมน์")
        print("\nตัวอย่างข้อมูล (5 แถวแรก):")
        print(df_merged.head())
    else:
        print("ไม่พบข้อมูลที่จะนำมาประมวลผล")


if __name__ == "__main__":
    main()
