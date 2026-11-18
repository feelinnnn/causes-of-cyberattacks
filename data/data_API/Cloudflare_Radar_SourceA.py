import json
import os
import time
from pathlib import Path
import requests
import pandas as pd


def load_dotenv_file():
    """โหลดค่าตัวแปรจากไฟล์ .env ที่อยู่ในโฟลเดอร์หลักของโปรเจกต์"""
    project_root = Path(__file__).resolve().parents[2]
    env_candidates = [
        project_root / ".env",
        Path(__file__).resolve().parent / ".env",
        Path.cwd() / ".env",
    ]
    for env_path in env_candidates:
        if env_path.is_file():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'").strip('"')
                    if key:
                        os.environ[key] = val
            break


load_dotenv_file()

API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "")
BASE_URL = "https://api.cloudflare.com/client/v4/radar"

# Mapping สำรองสำหรับประเทศหลัก
FALLBACK_COUNTRIES = {
    "TH": {"iso3": "THA", "name": "Thailand"},
    "US": {"iso3": "USA", "name": "United States"},
    "CN": {"iso3": "CHN", "name": "China"},
    "RU": {"iso3": "RUS", "name": "Russian Federation"},
    "GB": {"iso3": "GBR", "name": "United Kingdom"},
    "CA": {"iso3": "CAN", "name": "Canada"},
    "SG": {"iso3": "SGP", "name": "Singapore"},
    "JP": {"iso3": "JPN", "name": "Japan"},
    "DE": {"iso3": "DEU", "name": "Germany"},
    "AU": {"iso3": "AUS", "name": "Australia"},
    "FR": {"iso3": "FRA", "name": "France"},
    "IN": {"iso3": "IND", "name": "India"},
    "KR": {"iso3": "KOR", "name": "Korea, Rep."},
    "VN": {"iso3": "VNM", "name": "Viet Nam"},
    "ID": {"iso3": "IDN", "name": "Indonesia"},
    "MY": {"iso3": "MYS", "name": "Malaysia"},
    "NL": {"iso3": "NLD", "name": "Netherlands"},
    "BR": {"iso3": "BRA", "name": "Brazil"},
}


ISO2_TO_ISO3 = {'AD': {'iso3': 'AND', 'name': 'Andorra'},
 'AE': {'iso3': 'ARE', 'name': 'United Arab Emirates'},
 'AF': {'iso3': 'AFG', 'name': 'Afghanistan'},
 'AG': {'iso3': 'ATG', 'name': 'Antigua and Barbuda'},
 'AI': {'iso3': 'AIA', 'name': 'Anguilla'},
 'AL': {'iso3': 'ALB', 'name': 'Albania'},
 'AM': {'iso3': 'ARM', 'name': 'Armenia'},
 'AN': {'iso3': 'ANT', 'name': 'Netherlands Antilles'},
 'AO': {'iso3': 'AGO', 'name': 'Angola'},
 'AQ': {'iso3': 'ATA', 'name': 'Antarctica'},
 'AR': {'iso3': 'ARG', 'name': 'Argentina'},
 'AS': {'iso3': 'ASM', 'name': 'American Samoa'},
 'AT': {'iso3': 'AUT', 'name': 'Austria'},
 'AU': {'iso3': 'AUS', 'name': 'Australia'},
 'AW': {'iso3': 'ABW', 'name': 'Aruba'},
 'AX': {'iso3': 'ALA', 'name': 'Åland Islands'},
 'AZ': {'iso3': 'AZE', 'name': 'Azerbaijan'},
 'B1': {'iso3': 'BA1', 'name': 'British Antarctic Territories'},
 'BA': {'iso3': 'BIH', 'name': 'Bosnia and Herzegovina'},
 'BB': {'iso3': 'BRB', 'name': 'Barbados'},
 'BD': {'iso3': 'BGD', 'name': 'Bangladesh'},
 'BE': {'iso3': 'BEL', 'name': 'Belgium'},
 'BF': {'iso3': 'BFA', 'name': 'Burkina Faso'},
 'BG': {'iso3': 'BGR', 'name': 'Bulgaria'},
 'BH': {'iso3': 'BHR', 'name': 'Bahrain'},
 'BI': {'iso3': 'BDI', 'name': 'Burundi'},
 'BJ': {'iso3': 'BEN', 'name': 'Benin'},
 'BL': {'iso3': 'BLM', 'name': 'St. Barths'},
 'BM': {'iso3': 'BMU', 'name': 'Bermuda'},
 'BN': {'iso3': 'BRN', 'name': 'Brunei Darussalam'},
 'BO': {'iso3': 'BOL', 'name': 'Bolivia'},
 'BQ': {'iso3': 'BES', 'name': 'Bonaire, Saint Eustatius and Saba'},
 'BR': {'iso3': 'BRA', 'name': 'Brazil'},
 'BS': {'iso3': 'BHS', 'name': 'Bahamas'},
 'BT': {'iso3': 'BTN', 'name': 'Bhutan'},
 'BV': {'iso3': 'BVT', 'name': 'Bouvet Island'},
 'BW': {'iso3': 'BWA', 'name': 'Botswana'},
 'BY': {'iso3': 'BLR', 'name': 'Belarus'},
 'BZ': {'iso3': 'BLZ', 'name': 'Belize'},
 'CA': {'iso3': 'CAN', 'name': 'Canada'},
 'CC': {'iso3': 'CCK', 'name': 'Cocos (Keeling) Islands'},
 'CD': {'iso3': 'COD', 'name': 'DR Congo'},
 'CF': {'iso3': 'CAF', 'name': 'Central African Republic'},
 'CG': {'iso3': 'COG', 'name': 'Congo Republic'},
 'CH': {'iso3': 'CHE', 'name': 'Switzerland'},
 'CI': {'iso3': 'CIV', 'name': "Côte d'Ivoire"},
 'CK': {'iso3': 'COK', 'name': 'Cook Islands'},
 'CL': {'iso3': 'CHL', 'name': 'Chile'},
 'CM': {'iso3': 'CMR', 'name': 'Cameroon'},
 'CN': {'iso3': 'CHN', 'name': 'China'},
 'CO': {'iso3': 'COL', 'name': 'Colombia'},
 'CR': {'iso3': 'CRI', 'name': 'Costa Rica'},
 'CU': {'iso3': 'CUB', 'name': 'Cuba'},
 'CV': {'iso3': 'CPV', 'name': 'Cabo Verde'},
 'CW': {'iso3': 'CUW', 'name': 'Curaçao'},
 'CX': {'iso3': 'CXR', 'name': 'Christmas Island'},
 'CY': {'iso3': 'CYP', 'name': 'Cyprus'},
 'CZ': {'iso3': 'CZE', 'name': 'Czechia'},
 'DE': {'iso3': 'DEU', 'name': 'Germany'},
 'DJ': {'iso3': 'DJI', 'name': 'Djibouti'},
 'DK': {'iso3': 'DNK', 'name': 'Denmark'},
 'DM': {'iso3': 'DMA', 'name': 'Dominica'},
 'DO': {'iso3': 'DOM', 'name': 'Dominican Republic'},
 'DZ': {'iso3': 'DZA', 'name': 'Algeria'},
 'EC': {'iso3': 'ECU', 'name': 'Ecuador'},
 'EE': {'iso3': 'EST', 'name': 'Estonia'},
 'EG': {'iso3': 'EGY', 'name': 'Egypt'},
 'EH': {'iso3': 'ESH', 'name': 'Western Sahara'},
 'ER': {'iso3': 'ERI', 'name': 'Eritrea'},
 'ES': {'iso3': 'ESP', 'name': 'Spain'},
 'ET': {'iso3': 'ETH', 'name': 'Ethiopia'},
 'FI': {'iso3': 'FIN', 'name': 'Finland'},
 'FJ': {'iso3': 'FJI', 'name': 'Fiji'},
 'FK': {'iso3': 'FLK', 'name': 'Falkland Islands'},
 'FM': {'iso3': 'FSM', 'name': 'Micronesia, Fed. Sts.'},
 'FO': {'iso3': 'FRO', 'name': 'Faroe Islands'},
 'FR': {'iso3': 'FRA', 'name': 'France'},
 'GA': {'iso3': 'GAB', 'name': 'Gabon'},
 'GD': {'iso3': 'GRD', 'name': 'Grenada'},
 'GE': {'iso3': 'GEO', 'name': 'Georgia'},
 'GF': {'iso3': 'GUF', 'name': 'French Guiana'},
 'GG': {'iso3': 'GGY', 'name': 'Guernsey'},
 'GH': {'iso3': 'GHA', 'name': 'Ghana'},
 'GI': {'iso3': 'GIB', 'name': 'Gibraltar'},
 'GL': {'iso3': 'GRL', 'name': 'Greenland'},
 'GM': {'iso3': 'GMB', 'name': 'Gambia'},
 'GN': {'iso3': 'GIN', 'name': 'Guinea'},
 'GP': {'iso3': 'GLP', 'name': 'Guadeloupe'},
 'GQ': {'iso3': 'GNQ', 'name': 'Equatorial Guinea'},
 'GS': {'iso3': 'SGS', 'name': 'South Georgia and South Sandwich Is.'},
 'GT': {'iso3': 'GTM', 'name': 'Guatemala'},
 'GU': {'iso3': 'GUM', 'name': 'Guam'},
 'GW': {'iso3': 'GNB', 'name': 'Guinea-Bissau'},
 'GY': {'iso3': 'GUY', 'name': 'Guyana'},
 'HK': {'iso3': 'HKG', 'name': 'Hong Kong'},
 'HM': {'iso3': 'HMD', 'name': 'Heard and McDonald Islands'},
 'HN': {'iso3': 'HND', 'name': 'Honduras'},
 'HR': {'iso3': 'HRV', 'name': 'Croatia'},
 'HT': {'iso3': 'HTI', 'name': 'Haiti'},
 'HU': {'iso3': 'HUN', 'name': 'Hungary'},
 'ID': {'iso3': 'IDN', 'name': 'Indonesia'},
 'IE': {'iso3': 'IRL', 'name': 'Ireland'},
 'IL': {'iso3': 'ISR', 'name': 'Israel'},
 'IM': {'iso3': 'IMN', 'name': 'Isle of Man'},
 'IN': {'iso3': 'IND', 'name': 'India'},
 'IO': {'iso3': 'IOT', 'name': 'British Indian Ocean Territory'},
 'IQ': {'iso3': 'IRQ', 'name': 'Iraq'},
 'IR': {'iso3': 'IRN', 'name': 'Iran'},
 'IS': {'iso3': 'ISL', 'name': 'Iceland'},
 'IT': {'iso3': 'ITA', 'name': 'Italy'},
 'JE': {'iso3': 'JEY', 'name': 'Jersey'},
 'JM': {'iso3': 'JAM', 'name': 'Jamaica'},
 'JO': {'iso3': 'JOR', 'name': 'Jordan'},
 'JP': {'iso3': 'JPN', 'name': 'Japan'},
 'KE': {'iso3': 'KEN', 'name': 'Kenya'},
 'KG': {'iso3': 'KGZ', 'name': 'Kyrgyzstan'},
 'KH': {'iso3': 'KHM', 'name': 'Cambodia'},
 'KI': {'iso3': 'KIR', 'name': 'Kiribati'},
 'KM': {'iso3': 'COM', 'name': 'Comoros'},
 'KN': {'iso3': 'KNA', 'name': 'St. Kitts and Nevis'},
 'KP': {'iso3': 'PRK', 'name': 'North Korea'},
 'KR': {'iso3': 'KOR', 'name': 'South Korea'},
 'KW': {'iso3': 'KWT', 'name': 'Kuwait'},
 'KY': {'iso3': 'CYM', 'name': 'Cayman Islands'},
 'KZ': {'iso3': 'KAZ', 'name': 'Kazakhstan'},
 'LA': {'iso3': 'LAO', 'name': 'Laos'},
 'LB': {'iso3': 'LBN', 'name': 'Lebanon'},
 'LC': {'iso3': 'LCA', 'name': 'St. Lucia'},
 'LI': {'iso3': 'LIE', 'name': 'Liechtenstein'},
 'LK': {'iso3': 'LKA', 'name': 'Sri Lanka'},
 'LR': {'iso3': 'LBR', 'name': 'Liberia'},
 'LS': {'iso3': 'LSO', 'name': 'Lesotho'},
 'LT': {'iso3': 'LTU', 'name': 'Lithuania'},
 'LU': {'iso3': 'LUX', 'name': 'Luxembourg'},
 'LV': {'iso3': 'LVA', 'name': 'Latvia'},
 'LY': {'iso3': 'LBY', 'name': 'Libya'},
 'MA': {'iso3': 'MAR', 'name': 'Morocco'},
 'MC': {'iso3': 'MCO', 'name': 'Monaco'},
 'MD': {'iso3': 'MDA', 'name': 'Moldova'},
 'ME': {'iso3': 'MNE', 'name': 'Montenegro'},
 'MF': {'iso3': 'MAF', 'name': 'Saint-Martin'},
 'MG': {'iso3': 'MDG', 'name': 'Madagascar'},
 'MH': {'iso3': 'MHL', 'name': 'Marshall Islands'},
 'MK': {'iso3': 'MKD', 'name': 'North Macedonia'},
 'ML': {'iso3': 'MLI', 'name': 'Mali'},
 'MM': {'iso3': 'MMR', 'name': 'Myanmar'},
 'MN': {'iso3': 'MNG', 'name': 'Mongolia'},
 'MO': {'iso3': 'MAC', 'name': 'Macau'},
 'MP': {'iso3': 'MNP', 'name': 'Northern Mariana Islands'},
 'MQ': {'iso3': 'MTQ', 'name': 'Martinique'},
 'MR': {'iso3': 'MRT', 'name': 'Mauritania'},
 'MS': {'iso3': 'MSR', 'name': 'Montserrat'},
 'MT': {'iso3': 'MLT', 'name': 'Malta'},
 'MU': {'iso3': 'MUS', 'name': 'Mauritius'},
 'MV': {'iso3': 'MDV', 'name': 'Maldives'},
 'MW': {'iso3': 'MWI', 'name': 'Malawi'},
 'MX': {'iso3': 'MEX', 'name': 'Mexico'},
 'MY': {'iso3': 'MYS', 'name': 'Malaysia'},
 'MZ': {'iso3': 'MOZ', 'name': 'Mozambique'},
 'NA': {'iso3': 'NAM', 'name': 'Namibia'},
 'NC': {'iso3': 'NCL', 'name': 'New Caledonia'},
 'NE': {'iso3': 'NER', 'name': 'Niger'},
 'NF': {'iso3': 'NFK', 'name': 'Norfolk Island'},
 'NG': {'iso3': 'NGA', 'name': 'Nigeria'},
 'NI': {'iso3': 'NIC', 'name': 'Nicaragua'},
 'NL': {'iso3': 'NLD', 'name': 'Netherlands'},
 'NO': {'iso3': 'NOR', 'name': 'Norway'},
 'NP': {'iso3': 'NPL', 'name': 'Nepal'},
 'NR': {'iso3': 'NRU', 'name': 'Nauru'},
 'NU': {'iso3': 'NIU', 'name': 'Niue'},
 'NZ': {'iso3': 'NZL', 'name': 'New Zealand'},
 'OM': {'iso3': 'OMN', 'name': 'Oman'},
 'PA': {'iso3': 'PAN', 'name': 'Panama'},
 'PE': {'iso3': 'PER', 'name': 'Peru'},
 'PF': {'iso3': 'PYF', 'name': 'French Polynesia'},
 'PG': {'iso3': 'PNG', 'name': 'Papua New Guinea'},
 'PH': {'iso3': 'PHL', 'name': 'Philippines'},
 'PK': {'iso3': 'PAK', 'name': 'Pakistan'},
 'PL': {'iso3': 'POL', 'name': 'Poland'},
 'PM': {'iso3': 'SPM', 'name': 'St. Pierre and Miquelon'},
 'PN': {'iso3': 'PCN', 'name': 'Pitcairn'},
 'PR': {'iso3': 'PRI', 'name': 'Puerto Rico'},
 'PS': {'iso3': 'PSE', 'name': 'Palestine'},
 'PT': {'iso3': 'PRT', 'name': 'Portugal'},
 'PW': {'iso3': 'PLW', 'name': 'Palau'},
 'PY': {'iso3': 'PRY', 'name': 'Paraguay'},
 'QA': {'iso3': 'QAT', 'name': 'Qatar'},
 'RE': {'iso3': 'REU', 'name': 'Réunion'},
 'RO': {'iso3': 'ROU', 'name': 'Romania'},
 'RS': {'iso3': 'SRB', 'name': 'Serbia'},
 'RU': {'iso3': 'RUS', 'name': 'Russia'},
 'RW': {'iso3': 'RWA', 'name': 'Rwanda'},
 'SA': {'iso3': 'SAU', 'name': 'Saudi Arabia'},
 'SB': {'iso3': 'SLB', 'name': 'Solomon Islands'},
 'SC': {'iso3': 'SYC', 'name': 'Seychelles'},
 'SD': {'iso3': 'SDN', 'name': 'Sudan'},
 'SE': {'iso3': 'SWE', 'name': 'Sweden'},
 'SG': {'iso3': 'SGP', 'name': 'Singapore'},
 'SH': {'iso3': 'SHN', 'name': 'St. Helena'},
 'SI': {'iso3': 'SVN', 'name': 'Slovenia'},
 'SJ': {'iso3': 'SJM', 'name': 'Svalbard and Jan Mayen Islands'},
 'SK': {'iso3': 'SVK', 'name': 'Slovakia'},
 'SL': {'iso3': 'SLE', 'name': 'Sierra Leone'},
 'SM': {'iso3': 'SMR', 'name': 'San Marino'},
 'SN': {'iso3': 'SEN', 'name': 'Senegal'},
 'SO': {'iso3': 'SOM', 'name': 'Somalia'},
 'SR': {'iso3': 'SUR', 'name': 'Suriname'},
 'SS': {'iso3': 'SSD', 'name': 'South Sudan'},
 'ST': {'iso3': 'STP', 'name': 'Sao Tome and Principe'},
 'SU': {'iso3': 'SUN', 'name': 'Soviet Union (former)'},
 'SV': {'iso3': 'SLV', 'name': 'El Salvador'},
 'SX': {'iso3': 'SXM', 'name': 'Sint Maarten'},
 'SY': {'iso3': 'SYR', 'name': 'Syria'},
 'SZ': {'iso3': 'SWZ', 'name': 'Eswatini'},
 'TC': {'iso3': 'TCA', 'name': 'Turks and Caicos Islands'},
 'TD': {'iso3': 'TCD', 'name': 'Chad'},
 'TF': {'iso3': 'ATF', 'name': 'French Southern Territories'},
 'TG': {'iso3': 'TGO', 'name': 'Togo'},
 'TH': {'iso3': 'THA', 'name': 'Thailand'},
 'TJ': {'iso3': 'TJK', 'name': 'Tajikistan'},
 'TK': {'iso3': 'TKL', 'name': 'Tokelau'},
 'TL': {'iso3': 'TLS', 'name': 'Timor-Leste'},
 'TM': {'iso3': 'TKM', 'name': 'Turkmenistan'},
 'TN': {'iso3': 'TUN', 'name': 'Tunisia'},
 'TO': {'iso3': 'TON', 'name': 'Tonga'},
 'TR': {'iso3': 'TUR', 'name': 'Türkiye'},
 'TT': {'iso3': 'TTO', 'name': 'Trinidad and Tobago'},
 'TV': {'iso3': 'TUV', 'name': 'Tuvalu'},
 'TW': {'iso3': 'TWN', 'name': 'Taiwan'},
 'TZ': {'iso3': 'TZA', 'name': 'Tanzania'},
 'UA': {'iso3': 'UKR', 'name': 'Ukraine'},
 'UG': {'iso3': 'UGA', 'name': 'Uganda'},
 'UM': {'iso3': 'UMI', 'name': 'United States Minor Outlying Islands'},
 'US': {'iso3': 'USA', 'name': 'United States'},
 'UY': {'iso3': 'URY', 'name': 'Uruguay'},
 'UZ': {'iso3': 'UZB', 'name': 'Uzbekistan'},
 'VA': {'iso3': 'VAT', 'name': 'Vatican'},
 'VC': {'iso3': 'VCT', 'name': 'St. Vincent and the Grenadines'},
 'VE': {'iso3': 'VEN', 'name': 'Venezuela'},
 'VG': {'iso3': 'VGB', 'name': 'British Virgin Islands'},
 'VI': {'iso3': 'VIR', 'name': 'United States Virgin Islands'},
 'VN': {'iso3': 'VNM', 'name': 'Vietnam'},
 'VU': {'iso3': 'VUT', 'name': 'Vanuatu'},
 'WF': {'iso3': 'WLF', 'name': 'Wallis and Futuna Islands'},
 'WS': {'iso3': 'WSM', 'name': 'Samoa'},
 'XK': {'iso3': 'XKX', 'name': 'Kosovo'},
 'YE': {'iso3': 'YEM', 'name': 'Yemen'},
 'YT': {'iso3': 'MYT', 'name': 'Mayotte'},
 'ZA': {'iso3': 'ZAF', 'name': 'South Africa'},
 'ZM': {'iso3': 'ZMB', 'name': 'Zambia'},
 'ZW': {'iso3': 'ZWE', 'name': 'Zimbabwe'}}


def iso2_to_iso3_and_name(iso2: str, fallback_name: str = "") -> tuple[str, str]:
    """แปลงรหัสประเทศ ISO-2 (Cloudflare) เป็น ISO-3 (World Bank) และชื่อประเทศ"""
    iso2 = (iso2 or "").upper().strip()
    if iso2 == "GR":
        return "GRC", fallback_name or "Greece"
    if iso2 in FALLBACK_COUNTRIES:
        return FALLBACK_COUNTRIES[iso2]["iso3"], fallback_name or FALLBACK_COUNTRIES[iso2]["name"]
    if iso2 in ISO2_TO_ISO3:
        return ISO2_TO_ISO3[iso2]["iso3"], fallback_name or ISO2_TO_ISO3[iso2]["name"]
    return iso2, fallback_name or iso2


def get_headers() -> dict:
    token = os.getenv("CLOUDFLARE_API_TOKEN", API_TOKEN).strip()
    if not token or token == "YOUR_CLOUDFLARE_API_TOKEN_HERE":
        raise ValueError(
            "ไม่พบ CLOUDFLARE_API_TOKEN! กรุณาใส่ API Token ของคุณในไฟล์ .env ที่โฟลเดอร์หลักของโปรเจกต์"
        )
    return {"Authorization": f"Bearer {token}"}


def cf_request(endpoint: str, params: dict, max_retries: int = 4, quiet_400: bool = True) -> dict:
    """เรียก Cloudflare Radar API พร้อมจัดการ Rate Limit, Retry และกรณีปีที่ไม่มีข้อมูล (HTTP 400)"""
    url = f"{BASE_URL}/{endpoint}"
    headers = get_headers()

    for attempt in range(max_retries):
        try:
            res = requests.get(url, headers=headers, params=params, timeout=30)
            if res.status_code == 429:
                print(f"    [429] Rate limit hit on {endpoint}. Waiting 4 seconds...")
                time.sleep(4)
                continue
            if res.status_code == 401:
                raise RuntimeError(
                    "[401 Unauthorized] CLOUDFLARE_API_TOKEN ไม่ถูกต้อง หมดอายุ หรือติด IP Restriction กรุณาตรวจสอบในไฟล์ .env"
                )
            if res.status_code == 400 and quiet_400:
                return {}
            res.raise_for_status()
            data = res.json()
            return data.get("result") or {}
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                if not quiet_400:
                    print(f"    Failed after {max_retries} attempts ({endpoint}): {e}")
                return {}
            time.sleep(2)
    return {}


def year_date_params(year: int) -> dict:
    return {
        "dateStart": f"{year}-01-01T00:00:00Z",
        "dateEnd": f"{year}-12-31T23:45:00Z",
        "format": "json",
    }


def extract_meta_daterange(res: dict) -> tuple[str | None, str | None]:
    """ดึง startTime และ endTime จริงจาก result.meta.dateRange ของ Cloudflare Radar API"""
    if not isinstance(res, dict):
        return None, None
    meta = res.get("meta") or {}
    dr = meta.get("dateRange")
    if isinstance(dr, dict):
        return dr.get("startTime"), dr.get("endTime")
    if isinstance(dr, list) and dr and isinstance(dr[0], dict):
        return dr[0].get("startTime"), dr[0].get("endTime")
    return None, None


def fetch_top_location_With_adaptive_limit(
    endpoint: str, year: int, extra_params: dict | None = None
) -> tuple[dict[str, float], dict[str, str], tuple[str | None, str | None]]:
    """
    ดึงข้อมูลจาก top/locations โดยลอง limit สูงสุดที่ API รองรับอัตโนมัติ (200 -> 100)
    ป้องกันปัญหาส่ง limit=250 แล้วติด HTTP 400
    """
    extra = extra_params or {}
    val_map: dict[str, float] = {}
    name_map: dict[str, str] = {}
    meta_dr: tuple[str | None, str | None] = (None, None)

    for lim in (200, 100):
        params = {**year_date_params(year), **extra, "limit": lim}
        res = cf_request(endpoint, params)
        top_list = res.get("top_0", [])
        if top_list:
            meta_dr = extract_meta_daterange(res)
            for item in top_list:
                iso2 = (
                    item.get("targetCountryAlpha2")
                    or item.get("originCountryAlpha2")
                    or item.get("clientCountryAlpha2")
                    or item.get("location")
                    or ""
                ).upper()
                name = (
                    item.get("targetCountryName")
                    or item.get("originCountryName")
                    or item.get("clientCountryName")
                    or ""
                )
                if iso2:
                    val_map[iso2] = float(item.get("value", 0.0))
                    if name:
                        name_map[iso2] = name
            break

    return val_map, name_map, meta_dr


def fetch_all_radar_countries() -> dict[str, str]:
    """ดึงรายชื่อประเทศทั้งหมดที่รองรับจาก Cloudflare Radar (entities/locations)"""
    res = cf_request("entities/locations", {"limit": 300, "format": "json"})
    countries = {}
    for loc in res.get("locations", []):
        iso2 = (loc.get("alpha2") or "").upper().strip()
        name = loc.get("name") or ""
        if len(iso2) == 2:
            countries[iso2] = name
    return countries


def fetch_global_top_locations(year: int) -> dict:
    """
    ดึงข้อมูลระดับ Global ต่อปี แก้ไขปัญหาข้อที่ 1 และข้อที่ 3:
      1.1 target_ddos_percent (กรอง mitigationProduct=DDOS เฉพาะ DDoS จริง)
      1.2 origin_ddos_percent (กรอง mitigationProduct=DDOS เฉพาะ DDoS จริง)
      1.3 target_l7_mitigated_percent (ไม่กรอง = รวมทุกกลไก WAF + DDoS + Bot + IP Reputation)
      1.4 origin_l7_mitigated_percent (ไม่กรอง = รวมทุกกลไก WAF + DDoS + Bot + IP Reputation)
      2.1 http_traffic_percent จาก http/top/locations
    """
    target_ddos_map, n1, dr_t_ddos = fetch_top_location_With_adaptive_limit(
        "attacks/layer7/top/locations/target", year, {"mitigationProduct": "DDOS"}
    )
    origin_ddos_map, n2, dr_o_ddos = fetch_top_location_With_adaptive_limit(
        "attacks/layer7/top/locations/origin", year, {"mitigationProduct": "DDOS"}
    )
    target_l7_map, n3, dr_t_l7 = fetch_top_location_With_adaptive_limit(
        "attacks/layer7/top/locations/target", year
    )
    origin_l7_map, n4, dr_o_l7 = fetch_top_location_With_adaptive_limit(
        "attacks/layer7/top/locations/origin", year
    )
    http_map, n5, dr_http = fetch_top_location_With_adaptive_limit("http/top/locations", year)

    names_map = {**n5, **n4, **n3, **n2, **n1}
    meta_start, meta_end = dr_t_l7 if dr_t_l7[0] else (dr_http if dr_http[0] else dr_t_ddos)

    return {
        "target_ddos_map": target_ddos_map,
        "origin_ddos_map": origin_ddos_map,
        "target_l7_map": target_l7_map,
        "origin_l7_map": origin_l7_map,
        "http_map": http_map,
        "names_map": names_map,
        "meta_date_start": meta_start,
        "meta_date_end": meta_end,
    }


def fetch_outage_annotations(year: int, limit: int = 200) -> list[dict]:
    """
    ดึง Annotations เหตุการณ์ผิดปกติ/Outage จาก radar/annotations/outages
    เพื่อใช้มาร์กช่วงเวลาที่ข้อมูลทราฟฟิกอาจผิดปกติใน Data Quality Report
    """
    params = {**year_date_params(year), "limit": limit}
    res = cf_request("annotations/outages", params)
    annotations = res.get("annotations") or []
    rows = []
    for ann in annotations:
        locs = ann.get("locations") or []
        asns = ann.get("asns") or []
        rows.append(
            {
                "year": year,
                "id": ann.get("id"),
                "event_type": ann.get("eventType"),
                "outage_type": (ann.get("outage") or {}).get("outageType"),
                "outage_cause": (ann.get("outage") or {}).get("outageCause"),
                "start_date": ann.get("startDate"),
                "end_date": ann.get("endDate"),
                "locations_iso2": ",".join(str(x) for x in locs),
                "asns": ",".join(str(x) for x in asns),
                "description": ann.get("description"),
                "scope": ann.get("scope"),
            }
        )
    return rows


def fetch_attack_flow_pairs(year: int, limit: int = 200) -> list[dict]:
    """
    4.2 attack_flow_pair: ดึงคู่ประเทศต้นทาง -> ปลายทาง จาก attacks/layer7/top/attacks
    """
    rows = []
    for lim in (limit, 100):
        params = {**year_date_params(year), "limit": lim}
        res = cf_request("attacks/layer7/top/attacks", params)
        top_list = res.get("top_0", [])
        if top_list:
            for idx, item in enumerate(top_list, start=1):
                orig_iso2 = (item.get("originCountryAlpha2") or "").upper()
                orig_name = item.get("originCountryName") or ""
                targ_iso2 = (item.get("targetCountryAlpha2") or "").upper()
                targ_name = item.get("targetCountryName") or ""

                orig_iso3, orig_name = iso2_to_iso3_and_name(orig_iso2, orig_name)
                targ_iso3, targ_name = iso2_to_iso3_and_name(targ_iso2, targ_name)

                rows.append(
                    {
                        "year": year,
                        "rank": item.get("rank", idx),
                        "origin_country_iso2": orig_iso2,
                        "origin_country_code": orig_iso3,
                        "origin_country_name": orig_name,
                        "target_country_iso2": targ_iso2,
                        "target_country_code": targ_iso3,
                        "target_country_name": targ_name,
                        "attack_flow_pair": f"{orig_iso2} -> {targ_iso2}",
                        "attack_flow_pair_iso3": f"{orig_iso3} -> {targ_iso3}",
                        "attack_share_percent": float(item.get("value", 0.0)),
                    }
                )
            break
    return rows


def fetch_weekly_timeseries(year: int, location_iso2: str | None = None) -> list[dict]:
    """
    4.3 timeseries_weekly_trend: ดึงข้อมูลอนุกรมเวลารายสัปดาห์ จาก attacks/layer7/timeseries
    """
    params = {**year_date_params(year), "aggInterval": "1w"}
    if location_iso2:
        params["location"] = location_iso2

    res = cf_request("attacks/layer7/timeseries", params)
    serie = res.get("serie_0") or {}
    timestamps = serie.get("timestamps") or []
    values = serie.get("values") or []

    scope_iso2 = location_iso2 if location_iso2 else "GLOBAL"
    scope_iso3, scope_name = (
        iso2_to_iso3_and_name(location_iso2) if location_iso2 else ("GLOBAL", "Global")
    )

    rows = []
    for ts, val in zip(timestamps, values):
        try:
            num_val = float(val)
        except (TypeError, ValueError):
            num_val = None
        rows.append(
            {
                "year": year,
                "country_iso2": scope_iso2,
                "country_code": scope_iso3,
                "country_name": scope_name,
                "week_timestamp": ts,
                "timeseries_weekly_trend": num_val,
            }
        )
    return rows


def get_case_insensitive(d: dict, *keys: str, default: float | None = None) -> float | None:
    """ดึงค่าจาก dict โดยไม่สนตัวพิมพ์เล็ก-ใหญ่"""
    if not isinstance(d, dict) or not d:
        return default
    upper_map = {str(k).upper(): v for k, v in d.items()}
    for k in keys:
        if k.upper() in upper_map:
            try:
                return float(upper_map[k.upper()])
            except (TypeError, ValueError):
                return default
    return default


def fetch_country_metrics(
    iso2: str,
    year: int,
    global_data: dict,
    top_flows: list[dict],
) -> tuple[dict, list[dict]]:
    """ดึงตัวแปรครบทั้ง 4 กลุ่มสำหรับ 1 ประเทศ ใน 1 ปี"""
    params = {**year_date_params(year), "location": iso2}
    names_map = global_data["names_map"]
    iso3, country_name = iso2_to_iso3_and_name(iso2, names_map.get(iso2, ""))

    # กลุ่มที่ 2: ipv4_percent และ ipv6_percent (http/summary/ip_version)
    ip_summary = cf_request("http/summary/ip_version", params).get("summary_0", {})
    ipv4_pct = get_case_insensitive(ip_summary, "IPv4", "IPV4")
    ipv6_pct = get_case_insensitive(ip_summary, "IPv6", "IPV6")

    # กลุ่มที่ 3:
    # 3.1 bot_traffic_percent (http/summary/bot_class)
    bot_summary = cf_request("http/summary/bot_class", params).get("summary_0", {})
    bot_pct = get_case_insensitive(bot_summary, "bot", "BOT", "likely_automated")

    # 3.2 tls_1_3_percent (http/summary/tls_version)
    tls_summary = cf_request("http/summary/tls_version", params).get("summary_0", {})
    tls_1_3_pct = get_case_insensitive(tls_summary, "TLS 1.3", "TLSv1.3", "TLS_1_3")

    # 3.3 mitigation_waf_percent / mitigation_ddos_percent / mitigation_bot_percent
    mit_summary = cf_request("attacks/layer7/summary/mitigation_product", params).get("summary_0", {})
    mit_waf_pct = get_case_insensitive(mit_summary, "WAF")
    mit_ddos_pct = get_case_insensitive(mit_summary, "DDOS", "DDoS")
    mit_bot_pct = get_case_insensitive(mit_summary, "BOT_MANAGEMENT", "BOT", "Bot Management")

    # กลุ่มที่ 4:
    # 4.1 l3_vector_type (attacks/layer3/summary/vector)
    l3_summary = cf_request("attacks/layer3/summary/vector", params).get("summary_0", {})
    if isinstance(l3_summary, dict) and l3_summary:
        sorted_vectors = sorted(
            l3_summary.items(),
            key=lambda kv: float(kv[1]) if str(kv[1]).replace(".", "", 1).isdigit() else 0.0,
            reverse=True,
        )
        top_l3_vector = sorted_vectors[0][0]
        l3_vector_json = json.dumps(l3_summary, ensure_ascii=False)
    else:
        top_l3_vector = None
        l3_vector_json = None

    l3_syn_pct = get_case_insensitive(l3_summary, "SYN Flood", "SYN", "SYN_FLOOD", "TCP Flood")
    l3_udp_pct = get_case_insensitive(l3_summary, "UDP Flood", "UDP", "UDP_FLOOD")

    # คู่โจมตีอันดับ 1 ที่เกี่ยวข้องกับประเทศนี้ (จาก attacks/layer7/top/attacks)
    country_flows = [
        f["attack_flow_pair"]
        for f in top_flows
        if f["origin_country_iso2"] == iso2 or f["target_country_iso2"] == iso2
    ]
    primary_flow_pair = country_flows[0] if country_flows else None

    # 4.3 ข้อมูลอนุกรมเวลารายสัปดาห์ของประเทศนี้ (attacks/layer7/timeseries)
    ts_rows = fetch_weekly_timeseries(year, location_iso2=iso2)
    weekly_values = [r["timeseries_weekly_trend"] for r in ts_rows if r["timeseries_weekly_trend"] is not None]
    weekly_peak = max(weekly_values) if weekly_values else None
    weekly_mean = round(sum(weekly_values) / len(weekly_values), 6) if weekly_values else None

    return {
        # --- Join Keys & Metadata ---
        "country_code": iso3,
        "country_name": country_name,
        "country_iso2": iso2,
        "year": year,
        "meta_date_start": global_data["meta_date_start"],
        "meta_date_end": global_data["meta_date_end"],
        # --- 1. กลุ่มตัวแปรตาม (Target Variables - Y: แยกเฉพาะ DDoS vs รวมทุกกลไก L7) ---
        "target_ddos_percent": global_data["target_ddos_map"].get(iso2),
        "origin_ddos_percent": global_data["origin_ddos_map"].get(iso2),
        "target_l7_mitigated_percent": global_data["target_l7_map"].get(iso2),
        "origin_l7_mitigated_percent": global_data["origin_l7_map"].get(iso2),
        # --- 2. กลุ่มตัวแปรปรับบรรทัดฐานและตรวจสอบคุณภาพ (Normalization & DQ) ---
        "http_traffic_percent": global_data["http_map"].get(iso2),
        "ipv4_percent": ipv4_pct,
        "ipv6_percent": ipv6_pct,
        # --- 3. กลุ่มตัวแปรต้นเชิงพฤติกรรม (Predictor Features - X) ---
        "bot_traffic_percent": bot_pct,
        "tls_1_3_percent": tls_1_3_pct,
        "mitigation_waf_percent": mit_waf_pct,
        "mitigation_ddos_percent": mit_ddos_pct,
        "mitigation_bot_percent": mit_bot_pct,
        # --- 4. กลุ่มตัวแปรสำหรับการสำรวจและการนำเสนอ (EDA & Presentation) ---
        "l3_vector_type": top_l3_vector,
        "l3_syn_percent": l3_syn_pct,
        "l3_udp_percent": l3_udp_pct,
        "l3_vector_breakdown_json": l3_vector_json,
        "attack_flow_pair": primary_flow_pair,
        "timeseries_weekly_mean": weekly_mean,
        "timeseries_weekly_peak": weekly_peak,
    }, ts_rows


def patch_existing_csv(existing_csv: Path, out_dir: Path):
    """
    โหมดดึงเฉพาะ Raw Data ส่วน Global Top Locations และ Outage Annotations เพิ่มลงไฟล์เดิม (~10 วินาที):
      1. ดึง target_ddos_percent & origin_ddos_percent (mitigationProduct=DDOS)
      2. ดึง target_l7_mitigated_percent & origin_l7_mitigated_percent (รวมทุกกลไก L7)
      3. ดึง Outage Annotations (radar/annotations/outages)
      4. บันทึก meta.dateRange (meta_date_start, meta_date_end) ของแต่ละปี
      (ไม่มีกระบวนการ Clean หรือคำนวณ Feature เพิ่มเติม เก็บเป็น Raw Data 100%)
    """
    print(f"พบไฟล์ข้อมูลดิบเดิมที่: {existing_csv}")
    print("กำลังดึงเฉพาะ Raw Data ส่วน Global Top Locations และ Outage Annotations เพิ่มเติม (~10 วินาที)...")

    df = pd.read_csv(existing_csv, keep_default_na=False)
    for col in df.columns:
        if col not in ("country_code", "country_name", "country_iso2"):
            df[col] = df[col].replace("", None)

    for float_col in (
        "target_ddos_percent",
        "origin_ddos_percent",
        "target_l7_mitigated_percent",
        "origin_l7_mitigated_percent",
        "http_traffic_percent",
    ):
        if float_col in df.columns:
            df[float_col] = pd.to_numeric(df[float_col], errors="coerce").astype("float64")
        else:
            df[float_col] = pd.Series([float("nan")] * len(df), dtype="float64")

    for str_col in ("meta_date_start", "meta_date_end"):
        if str_col not in df.columns:
            df[str_col] = pd.Series([None] * len(df), dtype="object")
        else:
            df[str_col] = df[str_col].astype("object")

    df["year"] = df["year"].astype(int)

    years = sorted(df["year"].unique().tolist())
    all_outages = []

    for yr in years:
        print(f"  -> ดึง Raw Global Top Locations (DDOS & All L7) และ Outage Annotations ปี {yr}...")
        gdata = fetch_global_top_locations(yr)
        outages = fetch_outage_annotations(yr)
        all_outages.extend(outages)

        mask = df["year"] == yr
        df.loc[mask, "meta_date_start"] = gdata["meta_date_start"]
        df.loc[mask, "meta_date_end"] = gdata["meta_date_end"]
        df.loc[mask, "target_ddos_percent"] = df.loc[mask, "country_iso2"].map(gdata["target_ddos_map"])
        df.loc[mask, "origin_ddos_percent"] = df.loc[mask, "country_iso2"].map(gdata["origin_ddos_map"])
        df.loc[mask, "target_l7_mitigated_percent"] = df.loc[mask, "country_iso2"].map(gdata["target_l7_map"])
        df.loc[mask, "origin_l7_mitigated_percent"] = df.loc[mask, "country_iso2"].map(gdata["origin_l7_map"])

        if gdata["http_map"]:
            existing_http = pd.to_numeric(df.loc[mask, "http_traffic_percent"], errors="coerce")
            mapped_http = df.loc[mask, "country_iso2"].map(gdata["http_map"])
            df.loc[mask, "http_traffic_percent"] = existing_http.combine_first(mapped_http)

    df = df.sort_values(by=["country_code", "year"]).reset_index(drop=True)
    df.to_csv(existing_csv, index=False, encoding="utf-8-sig")
    print(f"[สำเร็จ 1/2] อัปเดตไฟล์ Raw Data เรียบร้อยที่: {existing_csv} ({len(df)} แถว, {len(df.columns)} คอลัมน์)")

    if all_outages:
        outages_csv = out_dir / "cloudflare_annotations_outages.csv"
        pd.DataFrame(all_outages).to_csv(outages_csv, index=False, encoding="utf-8-sig")
        print(f"[สำเร็จ 2/2] บันทึกตาราง Raw Outage Annotations ที่: {outages_csv} ({len(all_outages)} แถว)")


def main():
    import sys

    # ตรวจสอบ Token ก่อนเริ่ม
    _ = get_headers()

    raw_base = Path(__file__).resolve().parent.parent / "raw"
    cf_subfolder = raw_base / "sourceA" / "cloudeflare_rader"
    output_dir = cf_subfolder if cf_subfolder.is_dir() else raw_base
    output_dir.mkdir(parents=True, exist_ok=True)

    existing_main_csv = output_dir / "cloudflare_radar_source_a.csv"
    if existing_main_csv.is_file() and "--full" not in sys.argv:
        patch_existing_csv(existing_main_csv, output_dir)
        return

    # กรณีรันใหม่ทั้งหมด (--full หรือยังไม่มีไฟล์เดิม): ลองดึงตั้งแต่ปี 2018-2024 (ปีที่ API ไม่มีข้อมูลจะถูกข้ามอัตโนมัติ)
    years_to_fetch = list(range(2018, 2025))

    print("กำลังดึงรายชื่อประเทศทั้งหมดจาก Cloudflare Radar...")
    all_radar_countries = fetch_all_radar_countries()

    main_records = []
    all_flow_records = []
    all_timeseries_records = []
    all_outage_records = []

    for year in years_to_fetch:
        print(f"\n=== เริ่มตรวจสอบและดึงข้อมูล Cloudflare Radar (Source A) ประจำปี {year} ===")

        global_data = fetch_global_top_locations(year)
        flow_rows = fetch_attack_flow_pairs(year, limit=200)
        global_ts = fetch_weekly_timeseries(year, location_iso2=None)
        outage_rows = fetch_outage_annotations(year, limit=200)

        if (
            not global_data["target_l7_map"]
            and not global_data["origin_l7_map"]
            and not global_data["http_map"]
            and not global_ts
        ):
            print(f"  [ข้ามปี {year}] Cloudflare Radar API ไม่มีข้อมูลย้อนหลังสำหรับปี {year}")
            continue

        all_flow_records.extend(flow_rows)
        all_timeseries_records.extend(global_ts)
        all_outage_records.extend(outage_rows)

        countries_for_year = sorted(
            set(all_radar_countries.keys())
            | set(global_data["http_map"].keys())
            | set(global_data["target_l7_map"].keys())
            | set(global_data["origin_l7_map"].keys())
        )
        global_data["names_map"] = {**all_radar_countries, **global_data["names_map"]}

        print(f"  -> พบข้อมูลสำหรับปี {year} จำนวน {len(countries_for_year)} ประเทศ")

        for idx, iso2 in enumerate(countries_for_year, start=1):
            cname = global_data["names_map"].get(iso2, iso2)
            print(f"  [{idx}/{len(countries_for_year)}] กำลังดึงข้อมูลประเทศ: {iso2} ({cname}) ปี {year}...")
            rec, country_ts = fetch_country_metrics(
                iso2=iso2,
                year=year,
                global_data=global_data,
                top_flows=flow_rows,
            )
            main_records.append(rec)
            all_timeseries_records.extend(country_ts)
            time.sleep(0.15)

    if main_records:
        df_main = pd.DataFrame(main_records).sort_values(by=["country_code", "year"]).reset_index(drop=True)
        main_csv = output_dir / "cloudflare_radar_source_a.csv"
        df_main.to_csv(main_csv, index=False, encoding="utf-8-sig")
        print(f"\n[สำเร็จ 1/4] บันทึกตารางหลัก Country-Year ที่: {main_csv} ({len(df_main)} แถว)")

    if all_flow_records:
        df_flows = pd.DataFrame(all_flow_records)
        flows_csv = output_dir / "cloudflare_attack_flow_pairs.csv"
        df_flows.to_csv(flows_csv, index=False, encoding="utf-8-sig")
        print(f"[สำเร็จ 2/4] บันทึกตาราง Attack Flow Pairs ที่: {flows_csv} ({len(df_flows)} แถว)")

    if all_timeseries_records:
        df_ts = pd.DataFrame(all_timeseries_records)
        ts_csv = output_dir / "cloudflare_timeseries_weekly.csv"
        df_ts.to_csv(ts_csv, index=False, encoding="utf-8-sig")
        print(f"[สำเร็จ 3/4] บันทึกตาราง Weekly Timeseries ที่: {ts_csv} ({len(df_ts)} แถว)")

    if all_outage_records:
        df_outages = pd.DataFrame(all_outage_records)
        outages_csv = output_dir / "cloudflare_annotations_outages.csv"
        df_outages.to_csv(outages_csv, index=False, encoding="utf-8-sig")
        print(f"[สำเร็จ 4/4] บันทึกตาราง Outage Annotations ที่: {outages_csv} ({len(df_outages)} แถว)")


if __name__ == "__main__":
    main()
