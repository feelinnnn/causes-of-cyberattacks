# Data dictionary

สร้างอัตโนมัติจาก `docs/data_dictionary.yaml` + ข้อมูลจริง ห้ามแก้ไฟล์นี้ตรงๆ ให้แก้ที่ YAML แล้วรันใหม่ (`python -m cyber_pipeline.quality.data_dictionary`)

⚠ = ความหมายต้องตรวจกับ codebook / เอกสารทางการอีกครั้ง

## Sources

| Source | Provider | License | Period | Fetched | Raw files |
|---|---|---|---|---|---|
| A_cloudflare | Cloudflare Radar API ([link](https://developers.cloudflare.com/radar/)) | CC BY-NC 4.0 (API data; non-commercial, attribution required) | 2022-2024 (HTTP metrics 2023-2024 only) | main table 2026-11-18 (re-fetched, patch mode); attack pairs and weekly series 2026-11-17 | `data/raw/sourceA/cloudeflare_rader/` |
| B_worldbank_wdi | World Bank, World Development Indicators API ([link](https://data.worldbank.org/)) | CC BY 4.0 | 2018-2024 | 2026-11-17 | `data/raw/sourceB/world_bank_econ_pred.csv, data/raw/sourceC/world_bank_digi_found.csv` |
| C_caida_bgp | CAIDA RouteViews Prefix-to-AS (rv2, IPv4) + CAIDA AS-to-Organization ([link](https://www.caida.org/catalog/datasets/routeviews-prefix2as/)) | CAIDA Acceptable Use Agreement (cite the dataset; report publications to CAIDA) | one snapshot per year, 1 July 2018-2024 | 2026-11-17 (manual download) | `data/raw/sourceC/BGP/, data/raw/sourceC/ip24prefix/` |
| E_worldbank_wgi | World Bank, Worldwide Governance Indicators ([link](https://www.worldbank.org/en/publication/worldwide-governance-indicators)) | CC BY 4.0 (World Bank Data Catalog) | 2018-2024 | 2026-11-17 | `data/raw/sourceE/world_bank_gov_wgi.csv` |
| E_vdem | V-Dem Institute, Country-Year Full+Others v16 ([link](https://www.v-dem.net/data/the-v-dem-dataset/)) | CC BY-SA 4.0 | 2018-2024 used (file covers 1789-2025) | 2026-11-17 (manual download, v16) | `data/raw/sourceE/V-Dem-CY-Full+Others-v16.csv` |
| E_itu_gci | ITU Global Cybersecurity Index, editions 2018, 2020, 2024 ([link](https://www.itu.int/en/ITU-D/Cybersecurity/Pages/global-cybersecurity-index.aspx)) | © ITU, all rights reserved: use and cite for analysis; do not redistribute the raw tables | editions 2018, 2020, 2024 | 2026-11-17 (manual) | `data/raw/sourceE/GCI_*_Raw.csv` |

## `country_reference`

- **Layer:** cleaned  ·  **Grain:** one country or territory  ·  **Key:** `iso3`  ·  **Source:** built from Cloudflare + World Bank codes
- **Rows:** 252  ·  **Columns:** 5

| Column | Type | Non-null | Range / values | Unit | Description | NaN means |
|---|---|---|---|---|---|---|
| `iso3` | text | 100% | 252 values: ABW, AFG, AGO, AIA … |  | รหัสประเทศ ISO 3166-1 alpha-3 (key หลักของทั้งโปรเจค) |  |
| `iso2` | text | 100% | 251 values: AD, AE, AF, AG … |  | รหัสประเทศ ISO alpha-2 (Cloudflare และ CAIDA ใช้รหัสนี้) | ไม่มีใน Cloudflare (เช่น CHI ของ World Bank) |
| `name` | text | 100% | 252 values: Afghanistan, Aland Islands, Albania, Algeria … |  | ชื่อประเทศ (จาก Cloudflare ถ้ามี ไม่งั้นจาก World Bank) |  |
| `name_wb` | text | 86% | 217 values: Afghanistan, Albania, Algeria, American Samoa … |  | ชื่อประเทศตาม World Bank | ไม่อยู่ในรายชื่อ World Bank |
| `in_worldbank` | bool | 100% | true 86% |  | อยู่ในรายชื่อ 217 เศรษฐกิจของ World Bank หรือไม่ |  |

## `cloudflare_country_year`

- **Layer:** cleaned  ·  **Grain:** country x year  ·  **Key:** `iso3, year`  ·  **Source:** A_cloudflare
- **Rows:** 753  ·  **Columns:** 21

| Column | Type | Non-null | Range / values | Unit | Description | NaN means |
|---|---|---|---|---|---|---|
| `iso3` | text | 100% | 251 values: ABW, AFG, AGO, AIA … |  | รหัสประเทศ ISO3 |  |
| `iso2` | text | 100% | 251 values: AD, AE, AF, AG … |  | รหัสประเทศ ISO2 |  |
| `country_name` | text | 100% | 251 values: Afghanistan, Aland Islands, Albania, Algeria … |  | ชื่อประเทศตาม Cloudflare |  |
| `year` | int | 100% | 2022 – 2024 |  | ปีที่ดึงข้อมูล (ช่วงจริงดูที่ meta_date_start/end) |  |
| `target_ddos_percent` | float | 75% | 0 – 29.88 | % of world | สัดส่วนของ DDoS L7 ทั้งโลกที่ยิงใส่เว็บซึ่งจดทะเบียน (billing) ในประเทศนี้ (mitigationProduct=DDOS) | ไม่อยู่ในรายการที่ API คืนมา (คืนมาไม่ถึง limit จึงน่าจะเป็นประเทศที่แทบไม่โดน ~0 แต่ยังไม่เติมค่า) |
| `origin_ddos_percent` | float | 80% | 0.000272 – 26.28 | % of world | สัดส่วนของ DDoS L7 ทั้งโลกที่มาจาก IP ในประเทศนี้ (ไม่ใช่สัญชาติผู้โจมตี) | ไม่ติด top 200 ของ API (ค่าน่าจะเล็กมาก) |
| `target_l7_mitigated_percent` | float | 80% | 1e-06 – 38.13 | % of world | สัดส่วนของคำขอ L7 ที่ถูกบล็อกทั้งโลก (ทุกระบบ ไม่เฉพาะ DDoS) ที่ยิงใส่ประเทศนี้ | ไม่ติด top 200 ของ API |
| `origin_l7_mitigated_percent` | float | 80% | 0.000603 – 21.51 | % of world | สัดส่วนของคำขอ L7 ที่ถูกบล็อกทั้งโลก (ทุกระบบ) ที่มาจากประเทศนี้ | ไม่ติด top 200 ของ API |
| `http_traffic_percent` | float | 66% | 0 – 24.71 | % of world | สัดส่วน HTTP traffic ทั้งโลกที่มาจากประเทศนี้ | ปี 2022 ไม่มีข้อมูล |
| `ipv4_percent` | float | 66% | 4.809 – 100 | % of country traffic | สัดส่วน HTTP traffic จากประเทศนี้ที่ใช้ IPv4 | ปี 2022 ไม่มีข้อมูล |
| `ipv6_percent` | float | 66% | 0 – 95.19 | % of country traffic | สัดส่วน HTTP traffic จากประเทศนี้ที่ใช้ IPv6 (รวมกับ ipv4 = 100) | ปี 2022 ไม่มีข้อมูล |
| `bot_traffic_percent` | float | 66% | 4.384 – 92.59 | % of country traffic | สัดส่วน HTTP traffic จากประเทศนี้ที่ Cloudflare จัดว่าเป็น bot | ปี 2022 ไม่มีข้อมูล |
| `tls_1_3_percent` | float | 66% | 22.23 – 100 | % of country traffic | สัดส่วน HTTPS traffic จากประเทศนี้ที่ใช้ TLS 1.3 (ตัวแทนความทันสมัยของอุปกรณ์) | ปี 2022 ไม่มีข้อมูล |
| `origin_mitig_waf_percent` | float | 99% | 11.88 – 100 | % of attacks from country | ในการโจมตี L7 ที่มาจากประเทศนี้ ถูกบล็อกด้วย WAF กี่ % | ไม่มีการโจมตีที่บันทึกได้ |
| `origin_mitig_ddos_percent` | float | 99% | 0 – 86.67 | % of attacks from country | ในการโจมตี L7 ที่มาจากประเทศนี้ ถูกบล็อกด้วยระบบ DDoS กี่ % | ไม่มีการโจมตีที่บันทึกได้ |
| `origin_mitig_bot_percent` | float | 99% | 0 – 8.967 | % of attacks from country | ในการโจมตี L7 ที่มาจากประเทศนี้ ถูกบล็อกด้วย Bot management กี่ % | ไม่มีการโจมตีที่บันทึกได้ |
| `l3_top_vector` | text | 34% | 12 values: CLDAP Flood, DNS Amplification, GRE Flood, ICMP Flood … |  | ประเภทการโจมตี L3 ที่ประเทศนี้โดนมากที่สุด (direction=TARGET) | ไม่มีข้อมูล L3 ของประเทศนี้ |
| `l3_syn_percent` | float | 34% | 0 – 96.6 | % of L3 attacks | สัดส่วน SYN Flood ในการโจมตี L3 ที่ประเทศนี้โดน (0 = ไม่ติด top 10) | ไม่มีข้อมูล L3 |
| `l3_udp_percent` | float | 34% | 0 – 92.86 | % of L3 attacks | สัดส่วน UDP Flood ในการโจมตี L3 ที่ประเทศนี้โดน (0 = ไม่ติด top 10) | ไม่มีข้อมูล L3 |
| `meta_date_start` | text | 100% | 3 values: 2021-12-27T00:00:00Z, 2022-12-26T00:00:00Z, 2024-01-01T00:00:00Z |  | วันเริ่มจริงของข้อมูลตามที่ API แจ้ง (Radar จัดช่วงตามสัปดาห์ เช่น ปี 2022 = 2021-12-27 ถึง 2022-12-26) |  |
| `meta_date_end` | text | 100% | 3 values: 2022-12-26T00:00:00Z, 2023-12-25T00:00:00Z, 2024-12-30T00:00:00Z |  | วันสิ้นสุดจริงของข้อมูลตามที่ API แจ้ง |  |

## `cloudflare_l3_vectors`

- **Layer:** cleaned  ·  **Grain:** country x year x attack vector  ·  **Key:** `iso3, year, vector`  ·  **Source:** A_cloudflare
- **Rows:** 2,523  ·  **Columns:** 4

| Column | Type | Non-null | Range / values | Unit | Description | NaN means |
|---|---|---|---|---|---|---|
| `iso3` | text | 100% | 131 values: AGO, ALB, ARE, ARG … |  | รหัสประเทศ ISO3 (ประเทศที่โดนโจมตี) |  |
| `year` | int | 100% | 2023 – 2024 |  | ปี |  |
| `vector` | text | 100% | 30 values: ACK Flood, ACK-RST Flood, ARMS Flood, CLDAP Flood … |  | ประเภทการโจมตี L3 เช่น SYN Flood หรือ DNS Amplification (other = นอก top 10) |  |
| `percent` | float | 100% | 0.000165 – 100 | % of L3 attacks | สัดส่วนของ vector นี้ในการโจมตี L3 ที่ประเทศนี้โดน |  |

## `cloudflare_attack_pairs`

- **Layer:** cleaned  ·  **Grain:** year x origin country x target country (top 200 pairs per year)  ·  **Key:** `year, origin_iso2, target_iso2`  ·  **Source:** A_cloudflare
- **Rows:** 600  ·  **Columns:** 11

| Column | Type | Non-null | Range / values | Unit | Description | NaN means |
|---|---|---|---|---|---|---|
| `year` | int | 100% | 2022 – 2024 |  | ปี |  |
| `rank` | int | 100% | 1 – 269 |  | อันดับของคู่ในปีนั้น (มีช่วงกระโดด เพราะ API ตัดบางอันดับ) |  |
| `origin_iso3` | text | 100% | 77 values: ALB, ARE, ARG, AUS … |  | ISO3 ประเทศต้นทาง (T1 = เครือข่าย Tor) |  |
| `origin_iso2` | text | 100% | 77 values: AE, AL, AR, AU … |  | ISO2 ประเทศต้นทาง |  |
| `origin_country_name` | text | 100% | 77 values: Albania, Algeria, Argentina, Australia … |  | ชื่อประเทศต้นทาง |  |
| `target_iso3` | text | 100% | 43 values: AFG, ALA, ALB, ARE … |  | ISO3 ประเทศเป้าหมาย |  |
| `target_iso2` | text | 100% | 43 values: AE, AF, AL, AR … |  | ISO2 ประเทศเป้าหมาย |  |
| `target_country_name` | text | 100% | 43 values: Afghanistan, Aland Islands, Albania, Algeria … |  | ชื่อประเทศเป้าหมาย |  |
| `attack_share_percent` | float | 100% | 0.03963 – 29.53 | % of world L7 attacks | สัดส่วนของการโจมตี L7 ทั้งโลกที่เป็นคู่นี้ (top 200 รวมกันได้ 67-77%) |  |
| `origin_is_country` | bool | 100% | true 99% |  | false ถ้าต้นทางไม่ใช่ประเทศ (Tor) |  |
| `is_domestic` | bool | 100% | true 7% |  | true ถ้าต้นทางกับเป้าหมายเป็นประเทศเดียวกัน |  |

## `cloudflare_timeseries_weekly`

- **Layer:** cleaned  ·  **Grain:** area x request year x week  ·  **Key:** `iso2, request_year, week_start`  ·  **Source:** A_cloudflare
- **Rows:** 40,386  ·  **Columns:** 8

| Column | Type | Non-null | Range / values | Unit | Description | NaN means |
|---|---|---|---|---|---|---|
| `iso3` | text | 100% | 254 values: ABW, AFG, AGO, AIA … |  | รหัส ISO3 (หรือ GLOBAL / AP / EU) |  |
| `iso2` | text | 100% | 254 values: AD, AE, AF, AG … |  | รหัส ISO2 (หรือ GLOBAL / AP / EU) |  |
| `country_name` | text | 100% | 254 values: AP, Afghanistan, Albania, Algeria … |  | ชื่อพื้นที่ |  |
| `scope` | text | 100% | 3 values: country, global, region |  | country / region / global |  |
| `request_year` | int | 100% | 2022 – 2024 |  | ปีของ request ที่ดึง (สัปดาห์เดียวกันอาจอยู่ 2 request) |  |
| `week_start` | text | 100% | 158 values: 2021-12-27, 2022-01-03, 2022-01-10, 2022-01-17 … |  | วันเริ่มสัปดาห์ (จันทร์) |  |
| `trend_scaled` | float | 100% | 0 – 1 | 0-1, scaled | ปริมาณการโจมตี L7 รายสัปดาห์ ปรับสเกลให้ค่าสูงสุดใน request = 1 เทียบข้ามประเทศหรือข้ามปีไม่ได้ |  |
| `is_partial_week` | bool | 100% | true 3% |  | true ถ้าสัปดาห์คร่อมปีของ request |  |

## `wb_econ`

- **Layer:** cleaned  ·  **Grain:** country x year  ·  **Key:** `iso3, year`  ·  **Source:** B_worldbank_wdi
- **Rows:** 1,519  ·  **Columns:** 7

| Column | Type | Non-null | Range / values | Unit | Description | NaN means |
|---|---|---|---|---|---|---|
| `iso3` | text | 100% | 217 values: ABW, AFG, AGO, ALB … |  | รหัสประเทศ ISO3 |  |
| `country_name` | text | 100% | 217 values: Afghanistan, Albania, Algeria, American Samoa … |  | ชื่อประเทศตาม World Bank |  |
| `year` | int | 100% | 2018 – 2024 |  | ปี |  |
| `gdp_per_capita` | float | 96% | 216.2 – 2.88e+05 | current USD | GDP ต่อหัว (NY.GDP.PCAP.CD) | ยังไม่รายงาน |
| `secure_internet_servers_per_1m` | float | 99% | 0.07652 – 3.263e+06 | per 1M people | จำนวน secure internet server ต่อประชากร 1 ล้านคน (IT.NET.SECR.P6) | ยังไม่รายงาน |
| `fdi_net_inflows` | float | 90% | -1,303 – 452.2 | % of GDP | เงินลงทุนโดยตรงจากต่างประเทศสุทธิ (BX.KLT.DINV.WD.GD.ZS) | ยังไม่รายงาน |
| `population` | int | 100% | 9646 – 1450935791 | people | ประชากรทั้งหมด (SP.POP.TOTL) |  |

## `wb_digital`

- **Layer:** cleaned  ·  **Grain:** country x year  ·  **Key:** `iso3, year`  ·  **Source:** B_worldbank_wdi
- **Rows:** 1,519  ·  **Columns:** 5

| Column | Type | Non-null | Range / values | Unit | Description | NaN means |
|---|---|---|---|---|---|---|
| `iso3` | text | 100% | 217 values: ABW, AFG, AGO, ALB … |  | รหัสประเทศ ISO3 |  |
| `country_name` | text | 100% | 217 values: Afghanistan, Albania, Algeria, American Samoa … |  | ชื่อประเทศ |  |
| `year` | int | 100% | 2018 – 2024 |  | ปี |  |
| `internet_users_pct` | float | 84% | 2.731 – 100 | % of population | สัดส่วนประชากรที่ใช้อินเทอร์เน็ต (IT.NET.USER.ZS) | ยังไม่รายงาน (ปีล่าสุดขาดบ่อย) |
| `broadband_subs_per_100` | float | 87% | 0 – 75.75 | per 100 people | จำนวน fixed broadband ต่อประชากร 100 คน (IT.NET.BBND.P2) | ยังไม่รายงาน |

## `wb_governance`

- **Layer:** cleaned  ·  **Grain:** country x year  ·  **Key:** `iso3, year`  ·  **Source:** E_worldbank_wgi
- **Rows:** 1,519  ·  **Columns:** 5

| Column | Type | Non-null | Range / values | Unit | Description | NaN means |
|---|---|---|---|---|---|---|
| `iso3` | text | 100% | 217 values: ABW, AFG, AGO, ALB … |  | รหัสประเทศ ISO3 |  |
| `country_name` | text | 100% | 217 values: Afghanistan, Albania, Algeria, American Samoa … |  | ชื่อประเทศ |  |
| `year` | int | 100% | 2018 – 2024 |  | ปี |  |
| `gov_effectiveness` | float | 94% | -2.312 – 2.126 | score approx -2.5..2.5 | WGI Government Effectiveness (ยิ่งสูงยิ่งดี) | WGI ไม่ประเมินประเทศนี้/ปีนี้ |
| `rule_of_law` | float | 95% | -2.327 – 2.097 | score approx -2.5..2.5 | WGI Rule of Law (ยิ่งสูงยิ่งดี) | WGI ไม่ประเมินประเทศนี้/ปีนี้ |

## `vdem_country_year`

- **Layer:** cleaned  ·  **Grain:** country x year  ·  **Key:** `iso3, year`  ·  **Source:** E_vdem
- **Rows:** 1,232  ·  **Columns:** 16

| Column | Type | Non-null | Range / values | Unit | Description | NaN means |
|---|---|---|---|---|---|---|
| `iso3` | text | 100% | 176 values: AFG, AGO, ALB, ARE … |  | รหัสประเทศ (V-Dem country_text_id; PSE = West Bank เท่านั้น) |  |
| `country_name` | text | 100% | 176 values: Afghanistan, Albania, Algeria, Angola … |  | ชื่อประเทศตาม V-Dem |  |
| `year` | int | 100% | 2018 – 2024 |  | ปี |  |
| `v2smgovcapsec` | float | 100% | -3.167 – 3.497 | latent score (approx -3.6..3.7) | รัฐมีบุคลากรและทรัพยากรพอจะรับมือภัยไซเบอร์หรือไม่ (ยิ่งสูงยิ่งมีขีดความสามารถ: ต่ำสุด = รับมือไม่ได้แม้การโจมตีง่ายๆ, สูงสุด = รับมือการโจมตีซับซ้อนได้) |  |
| `v2smprivcon` | float | 98% | -3.538 – 2.33 | latent score | กฎหมายเปิดให้รัฐเข้าถึงข้อมูลส่วนบุคคลบนอินเทอร์เน็ตได้แค่ไหน (ยิ่งสูงยิ่งคุ้มครอง: ต่ำสุด = รัฐเข้าถึงได้ทุกอย่าง, สูงสุด = เข้าถึงได้เฉพาะกรณีพิเศษ) | ไม่มีกฎหมายความเป็นส่วนตัว (v2smprivex = No จึงข้ามคำถามนี้ ว่างโดยการออกแบบ) |
| `v2smprivex` | float | 100% | -2.97 – 1.838 | latent score | มีกฎหมายคุ้มครองความเป็นส่วนตัวและข้อมูลของผู้ใช้อินเทอร์เน็ตหรือไม่ (ใช่/ไม่ใช่ ค่าประมาณ > 0.86 ≈ มี) |  |
| `v2x_polyarchy` | float | 100% | 0.014 – 0.918 | 0-1 | ดัชนีประชาธิปไตยเชิงเลือกตั้ง |  |
| `v2x_libdem` | float | 100% | 0.007 – 0.89 | 0-1 | ดัชนีประชาธิปไตยเสรีนิยม |  |
| `v2x_rule` | float | 100% | 0.007 – 0.998 | 0-1 | ดัชนีหลักนิติธรรม |  |
| `v2smgovfilprc` | float | 100% | -3.735 – 2.695 | latent score | รัฐบล็อกเว็บเพื่อเซ็นเซอร์เนื้อหาการเมืองบ่อยแค่ไหน (ยิ่งสูง = ยิ่งไม่ค่อยบล็อก: ต่ำสุด = บล็อกเป็นประจำ, สูงสุด = แทบไม่เคย) |  |
| `v2smgovshut` | float | 100% | -3.9 – 2.081 | latent score | รัฐตัดอินเทอร์เน็ตในประเทศบ่อยแค่ไหน (ยิ่งสูง = ยิ่งไม่ค่อยตัด: ต่ำสุด = ตัดเป็นประจำ, สูงสุด = แทบไม่เคย) |  |
| `v2smgovsmmon` | float | 100% | -3.586 – 2.988 | latent score | รัฐสอดส่องเนื้อหาการเมืองบนโซเชียลมีเดียครอบคลุมแค่ไหน (ยิ่งสูง = ยิ่งสอดส่องน้อย: ต่ำสุด = แทบทุกอย่าง, สูงสุด = แทบไม่สอดส่อง) |  |
| `v2smfordom` | float | 100% | -3.876 – 3.049 | latent score | รัฐบาลต่างชาติใช้โซเชียลมีเดียปล่อยข้อมูลเท็จเพื่อแทรกแซงการเมืองในประเทศบ่อยแค่ไหน (ยิ่งสูง = ยิ่งน้อย: ต่ำสุด = ทุกประเด็นสำคัญ, สูงสุด = แทบไม่เคย) |  |
| `v2smpolcap` | float | 100% | -3.099 – 4.214 | latent score | พรรคการเมืองหลักมีบุคลากรและทรัพยากรพอจะรับมือภัยไซเบอร์หรือไม่ (ยิ่งสูงยิ่งมีขีดความสามารถ) ไม่ใช่ศักยภาพของหน่วยบังคับใช้กฎหมาย |  |
| `v2smgovcapsec_nr` | float | 100% | 2 – 14 | coders | จำนวนผู้เชี่ยวชาญที่ประเมิน v2smgovcapsec (น้อย = ค่าน่าเชื่อถือน้อย) |  |
| `v2smprivcon_nr` | float | 98% | 1 – 14 | coders | จำนวนผู้เชี่ยวชาญที่ประเมิน v2smprivcon | ไม่มีการประเมิน |

## `gci_country_edition`

- **Layer:** cleaned  ·  **Grain:** country x GCI edition  ·  **Key:** `iso3, edition`  ·  **Source:** E_itu_gci
- **Rows:** 563  ·  **Columns:** 12

| Column | Type | Non-null | Range / values | Unit | Description | NaN means |
|---|---|---|---|---|---|---|
| `edition` | int | 100% | 2018 – 2024 |  | ฉบับของ GCI (2018 / 2020 / 2024) |  |
| `name_raw` | text | 100% | 251 values: Afghanistan, Albania, Algeria, Andorra … |  | ชื่อประเทศตามไฟล์ ITU ก่อนแปลงเป็นรหัส |  |
| `iso3` | text | 100% | 194 values: AFG, AGO, ALB, AND … |  | รหัสประเทศ ISO3 |  |
| `gci_score_100` | float | 100% | 0 – 100 | 0-100 | คะแนน GCI รวม ปรับเป็นสเกล 0-100 (2018 คูณ 100 และ 2024 รวม 5 ด้าน) วิธีวัดต่างกันในแต่ละฉบับ |  |
| `gci_rank` | float | 69% | 1 – 182 |  | อันดับโลก | ฉบับ 2024 ไม่มีอันดับ |
| `gci_tier` | text | 31% | 5 values: T1, T2, T3, T4 … |  | ระดับ T1 (ดีสุด) ถึง T5 | มีเฉพาะฉบับ 2024 |
| `gci_flag` | text | 8% | 2 values: *, ** |  | เครื่องหมายท้ายชื่อในฉบับ 2020: * = ไม่มีข้อมูล (no data collected), ** = ประเทศไม่ตอบแบบสอบถาม ทีม GCI เก็บข้อมูลเอง | ไม่มีเครื่องหมาย (ประเทศตอบแบบสอบถามเอง) |
| `pillar_legal` | float | 31% | 0 – 20 | 0-20 | คะแนนด้านกฎหมาย | มีเฉพาะฉบับ 2024 |
| `pillar_technical` | float | 31% | 0 – 20 | 0-20 | คะแนนด้านเทคนิค | มีเฉพาะฉบับ 2024 |
| `pillar_organizational` | float | 31% | 0 – 20 | 0-20 | คะแนนด้านองค์กร | มีเฉพาะฉบับ 2024 |
| `pillar_capacity` | float | 31% | 0 – 20 | 0-20 | คะแนนด้านการพัฒนาขีดความสามารถ | มีเฉพาะฉบับ 2024 |
| `pillar_cooperation` | float | 31% | 0 – 20 | 0-20 | คะแนนด้านความร่วมมือ | มีเฉพาะฉบับ 2024 |

## `bgp_country_year`

- **Layer:** cleaned  ·  **Grain:** country x year  ·  **Key:** `iso3, year`  ·  **Source:** C_caida_bgp
- **Rows:** 1,645  ·  **Columns:** 6

| Column | Type | Non-null | Range / values | Unit | Description | NaN means |
|---|---|---|---|---|---|---|
| `iso3` | text | 100% | 238 values: ABW, AFG, AGO, AIA … |  | รหัสประเทศ ISO3 (ประเทศที่องค์กรเจ้าของ ASN จดทะเบียน) |  |
| `iso2` | text | 100% | 238 values: AD, AE, AF, AG … |  | รหัสประเทศ ISO2 |  |
| `year` | int | 100% | 2018 – 2024 |  | ปีของ snapshot (1 ก.ค.) |  |
| `routed_asn_count` | int | 100% | 1 – 18064 | ASNs | จำนวน ASN สาธารณะที่ประกาศเส้นทาง IPv4 จริง |  |
| `routed_prefix_count` | float | 100% | 1 – 2.642e+05 | prefixes | จำนวน IPv4 prefix ที่ประกาศ (prefix ที่มีหลายเจ้าของแบ่งเป็นเศษส่วน) |  |
| `ipv4_slash24_count` | float | 100% | 1 – 4.96e+06 | /24 blocks (x256 = IPs) | ขนาด IPv4 ที่ถูก route เป็นจำนวนบล็อก /24 (ไม่นับซ้ำระหว่าง block ใหญ่กับ block ย่อย) |  |

## `country_year`

- **Layer:** integrated  ·  **Grain:** country x year (spine = 251 countries/territories x every year present in Cloudflare)  ·  **Key:** `iso3, year`  ·  **Source:** all cleaned country x year tables, left-joined on the spine
- **Rows:** 753  ·  **Columns:** 59

| Column | Type | Non-null | Range / values | Unit | Description | NaN means |
|---|---|---|---|---|---|---|
| `iso3` | text | 100% | 251 values: ABW, AFG, AGO, AIA … |  | รหัสประเทศ ISO3 |  |
| `iso2` | text | 100% | 250 values: AD, AE, AF, AG … |  | รหัสประเทศ ISO2 |  |
| `country_name` | text | 100% | 251 values: Afghanistan, Aland Islands, Albania, Algeria … |  | ชื่อประเทศจาก country_reference |  |
| `in_worldbank` | bool | 100% | true 86% |  | อยู่ในรายชื่อ World Bank หรือไม่ |  |
| `year` | int | 100% | 2022 – 2024 |  | ปี (ตามปีที่มีใน Cloudflare) |  |
| `target_ddos_percent` | float | 75% | 0 – 29.88 | % of world | สัดส่วนของ DDoS L7 ทั้งโลกที่ยิงใส่เว็บซึ่งจดทะเบียน (billing) ในประเทศนี้ (mitigationProduct=DDOS) | ไม่อยู่ในรายการที่ API คืนมา (คืนมาไม่ถึง limit จึงน่าจะเป็นประเทศที่แทบไม่โดน ~0 แต่ยังไม่เติมค่า) |
| `origin_ddos_percent` | float | 80% | 0.000272 – 26.28 | % of world | สัดส่วนของ DDoS L7 ทั้งโลกที่มาจาก IP ในประเทศนี้ (ไม่ใช่สัญชาติผู้โจมตี) | ไม่ติด top 200 ของ API (ค่าน่าจะเล็กมาก) |
| `target_l7_mitigated_percent` | float | 80% | 1e-06 – 38.13 | % of world | สัดส่วนของคำขอ L7 ที่ถูกบล็อกทั้งโลก (ทุกระบบ ไม่เฉพาะ DDoS) ที่ยิงใส่ประเทศนี้ | ไม่ติด top 200 ของ API |
| `origin_l7_mitigated_percent` | float | 80% | 0.000603 – 21.51 | % of world | สัดส่วนของคำขอ L7 ที่ถูกบล็อกทั้งโลก (ทุกระบบ) ที่มาจากประเทศนี้ | ไม่ติด top 200 ของ API |
| `http_traffic_percent` | float | 66% | 0 – 24.71 | % of world | สัดส่วน HTTP traffic ทั้งโลกที่มาจากประเทศนี้ | ปี 2022 ไม่มีข้อมูล |
| `ipv4_percent` | float | 66% | 4.809 – 100 | % of country traffic | สัดส่วน HTTP traffic จากประเทศนี้ที่ใช้ IPv4 | ปี 2022 ไม่มีข้อมูล |
| `ipv6_percent` | float | 66% | 0 – 95.19 | % of country traffic | สัดส่วน HTTP traffic จากประเทศนี้ที่ใช้ IPv6 (รวมกับ ipv4 = 100) | ปี 2022 ไม่มีข้อมูล |
| `bot_traffic_percent` | float | 66% | 4.384 – 92.59 | % of country traffic | สัดส่วน HTTP traffic จากประเทศนี้ที่ Cloudflare จัดว่าเป็น bot | ปี 2022 ไม่มีข้อมูล |
| `tls_1_3_percent` | float | 66% | 22.23 – 100 | % of country traffic | สัดส่วน HTTPS traffic จากประเทศนี้ที่ใช้ TLS 1.3 (ตัวแทนความทันสมัยของอุปกรณ์) | ปี 2022 ไม่มีข้อมูล |
| `origin_mitig_waf_percent` | float | 99% | 11.88 – 100 | % of attacks from country | ในการโจมตี L7 ที่มาจากประเทศนี้ ถูกบล็อกด้วย WAF กี่ % | ไม่มีการโจมตีที่บันทึกได้ |
| `origin_mitig_ddos_percent` | float | 99% | 0 – 86.67 | % of attacks from country | ในการโจมตี L7 ที่มาจากประเทศนี้ ถูกบล็อกด้วยระบบ DDoS กี่ % | ไม่มีการโจมตีที่บันทึกได้ |
| `origin_mitig_bot_percent` | float | 99% | 0 – 8.967 | % of attacks from country | ในการโจมตี L7 ที่มาจากประเทศนี้ ถูกบล็อกด้วย Bot management กี่ % | ไม่มีการโจมตีที่บันทึกได้ |
| `l3_top_vector` | text | 34% | 12 values: CLDAP Flood, DNS Amplification, GRE Flood, ICMP Flood … |  | ประเภทการโจมตี L3 ที่ประเทศนี้โดนมากที่สุด (direction=TARGET) | ไม่มีข้อมูล L3 ของประเทศนี้ |
| `l3_syn_percent` | float | 34% | 0 – 96.6 | % of L3 attacks | สัดส่วน SYN Flood ในการโจมตี L3 ที่ประเทศนี้โดน (0 = ไม่ติด top 10) | ไม่มีข้อมูล L3 |
| `l3_udp_percent` | float | 34% | 0 – 92.86 | % of L3 attacks | สัดส่วน UDP Flood ในการโจมตี L3 ที่ประเทศนี้โดน (0 = ไม่ติด top 10) | ไม่มีข้อมูล L3 |
| `has_cloudflare` | bool | 100% | true 100% |  | join กับ cloudflare_country_year ติดหรือไม่ |  |
| `gdp_per_capita` | float | 81% | 216.2 – 2.88e+05 | current USD | GDP ต่อหัว (NY.GDP.PCAP.CD) | ยังไม่รายงาน |
| `population` | float | 86% | 9,646 – 1.451e+09 | people | ประชากรทั้งหมด (SP.POP.TOTL) |  |
| `secure_internet_servers_per_1m` | float | 86% | 0.2882 – 3.263e+06 | per 1M people | จำนวน secure internet server ต่อประชากร 1 ล้านคน (IT.NET.SECR.P6) | ยังไม่รายงาน |
| `fdi_net_inflows` | float | 78% | -376.1 – 170.1 | % of GDP | เงินลงทุนโดยตรงจากต่างประเทศสุทธิ (BX.KLT.DINV.WD.GD.ZS) | ยังไม่รายงาน |
| `has_wb_econ` | bool | 100% | true 86% |  | join กับ wb_econ ติดหรือไม่ |  |
| `internet_users_pct` | float | 72% | 7.145 – 100 | % of population | สัดส่วนประชากรที่ใช้อินเทอร์เน็ต (IT.NET.USER.ZS) | ยังไม่รายงาน (ปีล่าสุดขาดบ่อย) |
| `broadband_subs_per_100` | float | 70% | 0 – 60.97 | per 100 people | จำนวน fixed broadband ต่อประชากร 100 คน (IT.NET.BBND.P2) | ยังไม่รายงาน |
| `has_wb_digital` | bool | 100% | true 86% |  | join กับ wb_digital ติดหรือไม่ |  |
| `gov_effectiveness` | float | 82% | -2.285 – 2.123 | score approx -2.5..2.5 | WGI Government Effectiveness (ยิ่งสูงยิ่งดี) | WGI ไม่ประเมินประเทศนี้/ปีนี้ |
| `rule_of_law` | float | 82% | -2.23 – 2.014 | score approx -2.5..2.5 | WGI Rule of Law (ยิ่งสูงยิ่งดี) | WGI ไม่ประเมินประเทศนี้/ปีนี้ |
| `has_wb_governance` | bool | 100% | true 86% |  | join กับ wb_governance ติดหรือไม่ |  |
| `v2smgovcapsec` | float | 70% | -3.167 – 3.497 | latent score (approx -3.6..3.7) | รัฐมีบุคลากรและทรัพยากรพอจะรับมือภัยไซเบอร์หรือไม่ (ยิ่งสูงยิ่งมีขีดความสามารถ: ต่ำสุด = รับมือไม่ได้แม้การโจมตีง่ายๆ, สูงสุด = รับมือการโจมตีซับซ้อนได้) |  |
| `v2smprivcon` | float | 68% | -3.488 – 2.12 | latent score | กฎหมายเปิดให้รัฐเข้าถึงข้อมูลส่วนบุคคลบนอินเทอร์เน็ตได้แค่ไหน (ยิ่งสูงยิ่งคุ้มครอง: ต่ำสุด = รัฐเข้าถึงได้ทุกอย่าง, สูงสุด = เข้าถึงได้เฉพาะกรณีพิเศษ) | ไม่มีกฎหมายความเป็นส่วนตัว (v2smprivex = No จึงข้ามคำถามนี้ ว่างโดยการออกแบบ) |
| `v2smprivex` | float | 70% | -2.97 – 1.838 | latent score | มีกฎหมายคุ้มครองความเป็นส่วนตัวและข้อมูลของผู้ใช้อินเทอร์เน็ตหรือไม่ (ใช่/ไม่ใช่ ค่าประมาณ > 0.86 ≈ มี) |  |
| `v2x_polyarchy` | float | 70% | 0.014 – 0.917 | 0-1 | ดัชนีประชาธิปไตยเชิงเลือกตั้ง |  |
| `v2x_libdem` | float | 70% | 0.009 – 0.887 | 0-1 | ดัชนีประชาธิปไตยเสรีนิยม |  |
| `v2x_rule` | float | 70% | 0.007 – 0.998 | 0-1 | ดัชนีหลักนิติธรรม |  |
| `v2smgovfilprc` | float | 70% | -3.735 – 2.695 | latent score | รัฐบล็อกเว็บเพื่อเซ็นเซอร์เนื้อหาการเมืองบ่อยแค่ไหน (ยิ่งสูง = ยิ่งไม่ค่อยบล็อก: ต่ำสุด = บล็อกเป็นประจำ, สูงสุด = แทบไม่เคย) |  |
| `v2smgovshut` | float | 70% | -3.9 – 2.081 | latent score | รัฐตัดอินเทอร์เน็ตในประเทศบ่อยแค่ไหน (ยิ่งสูง = ยิ่งไม่ค่อยตัด: ต่ำสุด = ตัดเป็นประจำ, สูงสุด = แทบไม่เคย) |  |
| `v2smgovsmmon` | float | 70% | -3.586 – 2.988 | latent score | รัฐสอดส่องเนื้อหาการเมืองบนโซเชียลมีเดียครอบคลุมแค่ไหน (ยิ่งสูง = ยิ่งสอดส่องน้อย: ต่ำสุด = แทบทุกอย่าง, สูงสุด = แทบไม่สอดส่อง) |  |
| `v2smfordom` | float | 70% | -3.876 – 2.706 | latent score | รัฐบาลต่างชาติใช้โซเชียลมีเดียปล่อยข้อมูลเท็จเพื่อแทรกแซงการเมืองในประเทศบ่อยแค่ไหน (ยิ่งสูง = ยิ่งน้อย: ต่ำสุด = ทุกประเด็นสำคัญ, สูงสุด = แทบไม่เคย) |  |
| `v2smpolcap` | float | 70% | -3.099 – 4.214 | latent score | พรรคการเมืองหลักมีบุคลากรและทรัพยากรพอจะรับมือภัยไซเบอร์หรือไม่ (ยิ่งสูงยิ่งมีขีดความสามารถ) ไม่ใช่ศักยภาพของหน่วยบังคับใช้กฎหมาย |  |
| `v2smgovcapsec_nr` | float | 70% | 2 – 13 | coders | จำนวนผู้เชี่ยวชาญที่ประเมิน v2smgovcapsec (น้อย = ค่าน่าเชื่อถือน้อย) |  |
| `v2smprivcon_nr` | float | 68% | 1 – 11 | coders | จำนวนผู้เชี่ยวชาญที่ประเมิน v2smprivcon | ไม่มีการประเมิน |
| `has_vdem` | bool | 100% | true 70% |  | join กับ vdem_country_year ติดหรือไม่ |  |
| `routed_asn_count` | float | 94% | 1 – 1.806e+04 | ASNs | จำนวน ASN สาธารณะที่ประกาศเส้นทาง IPv4 จริง |  |
| `routed_prefix_count` | float | 94% | 1 – 2.642e+05 | prefixes | จำนวน IPv4 prefix ที่ประกาศ (prefix ที่มีหลายเจ้าของแบ่งเป็นเศษส่วน) |  |
| `ipv4_slash24_count` | float | 94% | 1 – 4.96e+06 | /24 blocks (x256 = IPs) | ขนาด IPv4 ที่ถูก route เป็นจำนวนบล็อก /24 (ไม่นับซ้ำระหว่าง block ใหญ่กับ block ย่อย) |  |
| `has_bgp` | bool | 100% | true 94% |  | join กับ bgp_country_year ติดหรือไม่ |  |
| `gci_score_100` | float | 77% | 0 – 100 | 0-100 | คะแนน GCI จากฉบับล่าสุดที่ไม่เกินปีนี้ (as-of join) | ไม่มีใน GCI |
| `gci_tier` | text | 23% | 5 values: T1, T2, T3, T4 … |  | tier ของ GCI (มีเฉพาะเมื่อใช้ฉบับ 2024) | ฉบับที่ใช้ไม่มี tier |
| `gci_edition_used` | float | 77% | 2,020 – 2,024 |  | ฉบับ GCI ที่ใช้กับปีนี้ |  |
| `gci_age_years` | float | 77% | 0 – 4 | years | ปีนี้ห่างจากฉบับ GCI ที่ใช้กี่ปี (ยิ่งมากยิ่งเก่า) |  |
| `has_gci` | bool | 100% | true 77% |  | มีค่า GCI (as-of) หรือไม่ |  |
| `has_population` | bool | 100% | true 86% |  | มีข้อมูลประชากรหรือไม่ (ใช้คัดดินแดนที่ไม่มีคนอยู่ออก) |  |
| `http_traffic_mean` | float | 100% | 0 – 24.51 | % of world | ค่าเฉลี่ย http_traffic_percent ของประเทศจากทุกปีที่มีข้อมูล (ใช้แทนปีที่ขาด) |  |
| `traffic_above_0_01pct` | bool | 100% | true 58% |  | true ถ้า http_traffic_mean >= 0.01% (ตัดประเทศที่ traffic น้อยจนค่าแกว่ง) |  |
| `n_sources_available` | int | 100% | 1 – 7 |  | จำนวน source ที่มีข้อมูลในแถวนี้ (0-7) |  |
