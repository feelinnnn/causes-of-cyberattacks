# Data quality report

Rules run: 119  ·  PASS 93  ·  WARN 26  ·  FAIL 0

FAIL = error rule broken (pipeline stops). WARN = reported, pipeline continues. Full detail: `reports/dq/dq_results.csv`. Cleaning actions: `data/cleaned/_cleaning_log.csv`.

## Summary by rule

| Rule | Dimension | Checks | PASS | WARN | FAIL |
|---|---|---|---|---|---|
| R01 | uniqueness | 11 | 11 | 0 | 0 |
| R02 | referential integrity | 11 | 11 | 0 | 0 |
| R03 | validity | 31 | 31 | 0 | 0 |
| R04 | consistency | 7 | 7 | 0 | 0 |
| R05 | completeness | 18 | 1 | 17 | 0 |
| R06 | join coverage | 7 | 7 | 0 | 0 |
| R07 | cross-source consistency | 3 | 3 | 0 | 0 |
| R08 | plausibility | 6 | 0 | 6 | 0 |
| R09 | reliability | 2 | 0 | 2 | 0 |
| R10 | timeliness | 11 | 10 | 1 | 0 |
| R11 | documentation | 12 | 12 | 0 | 0 |

## Findings (WARN / FAIL)

| Rule | Table | Column | Check | Failed | % | Detail |
|---|---|---|---|---|---|---|
| R09 WARN | vdem_country_year | `v2smgovcapsec_nr` | coders > 3 | 10/1232 | 0.81 | few-coder country-years: FJI, GNQ, SSD, VUT |
| R09 WARN | vdem_country_year | `v2smprivcon_nr` | coders > 3 | 324/1203 | 26.93 | few-coder country-years: AFG, AGO, ARE, AZE, BDI, BGD, BLR, BTN, CAF, COD, COG, COM, CUB, DJI, DOM, ECU, EGY, ERI, ETH, FJI, GAB, GIN, GNB, GNQ, GTM, GUY, HRV, HTI, IRN, IRQ, JAM, KGZ, KHM, LAO, LBR, LBY, MDA, MDG, MDV, MMR,  |
| R05 WARN | country_year | `http_traffic_percent` | missing <= 30% (year 2022) | 217/217 | 100.0 |  |
| R05 WARN | country_year | `ipv4_percent` | missing <= 30% (year 2022) | 217/217 | 100.0 |  |
| R05 WARN | country_year | `ipv6_percent` | missing <= 30% (year 2022) | 217/217 | 100.0 |  |
| R05 WARN | country_year | `bot_traffic_percent` | missing <= 30% (year 2022) | 217/217 | 100.0 |  |
| R05 WARN | country_year | `tls_1_3_percent` | missing <= 30% (year 2022) | 217/217 | 100.0 |  |
| R05 WARN | country_year | `l3_top_vector` | missing <= 30% (year 2022) | 217/217 | 100.0 |  |
| R05 WARN | country_year | `l3_top_vector` | missing <= 30% (year 2023) | 96/217 | 44.24 |  |
| R05 WARN | country_year | `l3_top_vector` | missing <= 30% (year 2024) | 88/217 | 40.55 |  |
| R05 WARN | country_year | `l3_syn_percent` | missing <= 30% (year 2022) | 217/217 | 100.0 |  |
| R05 WARN | country_year | `l3_syn_percent` | missing <= 30% (year 2023) | 96/217 | 44.24 |  |
| R05 WARN | country_year | `l3_syn_percent` | missing <= 30% (year 2024) | 88/217 | 40.55 |  |
| R05 WARN | country_year | `l3_udp_percent` | missing <= 30% (year 2022) | 217/217 | 100.0 |  |
| R05 WARN | country_year | `l3_udp_percent` | missing <= 30% (year 2023) | 96/217 | 44.24 |  |
| R05 WARN | country_year | `l3_udp_percent` | missing <= 30% (year 2024) | 88/217 | 40.55 |  |
| R05 WARN | country_year | `broadband_subs_per_100` | missing <= 30% (year 2024) | 66/217 | 30.41 |  |
| R05 WARN | country_year | `gci_tier` | missing <= 30% (year 2022) | 217/217 | 100.0 |  |
| R05 WARN | country_year | `gci_tier` | missing <= 30% (year 2023) | 217/217 | 100.0 |  |
| R08 WARN | country_year | `ipv4_percent` | robust |z| <= 5.0 | 16/500 | 3.2 | e.g. SJM-2024, UMI-2024, IND-2024, IND-2023, MYS-2024 |
| R08 WARN | country_year | `ipv6_percent` | robust |z| <= 5.0 | 16/500 | 3.2 | e.g. SJM-2024, UMI-2024, IND-2024, IND-2023, MYS-2024 |
| R08 WARN | country_year | `tls_1_3_percent` | robust |z| <= 5.0 | 14/499 | 2.81 | e.g. CCK-2023, BVT-2023, BVT-2024, HMD-2023, SGS-2023 |
| R08 WARN | country_year | `l3_udp_percent` | robust |z| <= 5.0 | 7/254 | 2.76 | e.g. IRL-2024, IRL-2023, TTO-2024, SVK-2023, REU-2024 |
| R08 WARN | country_year | `fdi_net_inflows` | robust |z| <= 5.0 | 32/584 | 5.48 | e.g. LUX-2022, MLT-2024, CYM-2023, CYP-2024, MLT-2022 |
| R08 WARN | country_year | `v2smpolcap` | robust |z| <= 5.0 | 3/528 | 0.57 | e.g. CHN-2022, CHN-2023, CHN-2024 |
| R10 WARN | country_year | `broadband_subs_per_100` | has value in 2024 for >= 80% of countries | 66/217 | 30.41 | available 69.6% |
