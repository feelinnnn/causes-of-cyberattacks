# รายงานการสำรวจข้อมูลหลังทำความสะอาดและรวมตาราง (Cleaned & Integrated Data EDA)

เอกสารและชุดกราฟนี้ดึงข้อมูลโดยตรงจากฐานข้อมูล **`data/warehouse/cyberattacks.db`** (ตารางหลัก `country_year` และตาราง `cleaned_*`) เพื่อใช้สำหรับนำเสนอ:
1. **การเปรียบเทียบการเปลี่ยนแปลงหลังผ่าน Pipeline (รูปที่ 1–5 จับคู่แบบ 1:1 กับกราฟ Raw Data EDA ทั้ง 5 รูป)**
2. **ผลการสำรวจความสัมพันธ์และ Insights ของปัจจัยที่ส่งผลต่อการโจมตีทางไซเบอร์ (รูปที่ 6–8)**

---

## ส่วนที่ 1: เปรียบเทียบการเปลี่ยนแปลงจากกราฟ Raw Data ทั้ง 5 รูป (Before vs After Pipeline)

| รูปกราฟ Raw Data (ก่อน Clean) | รูปกราฟ Cleaned Data (หลัง Clean & Join) | สิ่งที่เปลี่ยนแปลงและผลลัพธ์ที่ได้จาก Pipeline |
| :--- | :--- | :--- |
| **`raw_01_entity_inconsistencies.png`**<br>รหัสประเทศคนละมาตรฐาน มีภูมิภาค (`WLD`, `HIC`, `EU`), `Tor`, ชื่อติด `**` และรหัสผิด `GR` | **`clean_01_standardized_entities.png`**<br>`Cleaned Data: Standardized ISO-3 Country Coverage` | • แปลงทุกแหล่งเข้าสู่มาตรฐาน **`ISO-3` เดียวกันครบ 100%** (251 พื้นที่ใน Spine, 0 รหัสภูมิภาคซ้ำซ้อน, 0 รหัสผิด)<br>• แยก Flag ชัดเจนระหว่างประเทศสมาชิก World Bank (217 เศรษฐกิจ) และกลุ่มวิเคราะห์หลักที่มี HTTP Traffic $\ge 0.01\%$ (**144 ประเทศ**) |
| **`raw_02_gci_scale_and_schema_drift.png`**<br>GCI 3 ฉบับคนละสเกล (`0–1`, `0–100`, และแยก 5 เสาหลัก `0–20`) | **`clean_02_gci_unified_scale_and_asof.png`**<br>`Cleaned Data: Unified GCI Score (0–100 Scale) & As-Of Join` | • ปรับสเกลทั้ง 3 ฉบับ (2018, 2020, 2024) เข้าสู่คอลัมน์ **`gci_score_100` (`0–100`)** เดียวกัน (มัธยฐาน: ปี 2018 = `43.0`, ปี 2020 = `50.5`, ปี 2024 = `66.9`)<br>• เชื่อมเข้าตาราง `country_year` แบบ **As-Of Join** (ปี 2022–2023 ใช้ฉบับ 2020, ปี 2024 ใช้ฉบับ 2024) ป้องกัน Data Leakage 100% |
| **`raw_03_missingness_heatmap_by_year.png`**<br>คอลัมน์ `l3_syn/udp` ดิบว่าง 100%, ปี 2022 ขาด HTTP Traffic 100% | **`clean_03_missingness_after_cleaning.png`**<br>`Cleaned Data: Completeness Profile After Cleaning & Integration` | • แกะ JSON ลงคอลัมน์ `l3_syn_percent`, `l3_udp_percent` และแยกเป็นตาราง `cleaned_cloudflare_l3_vectors` (2,523 แถว)<br>• สร้าง `http_traffic_mean` อุดช่องโหว่ปี 2022 ทำให้คัดกรองกลุ่มประเทศหลัก (144 ประเทศ) ซึ่งมีความครบถ้วนของข้อมูลสูงมาก (เช่นในปี 2024 `target_ddos_percent` ว่างเพียง `6.9%` และ `gci_score_100` ว่างเพียง `2.8%`) |
| **`raw_04_distributions_and_skewness.png`**<br>ค่าดิบเบ้ขวาจัดระดับ Power-Law (Skewness `+3.48` ถึง `+48.86`) | **`clean_04_log_transformed_distributions.png`**<br>`Cleaned Data: Distributions After Log & Log-Ratio Transformation` | • เมื่อแปลงตัวแปรโจมตีเป็น **Log-Ratio Attack Intensity** เทียบกับ Traffic และเทค **`log10`** กับ GDP, Secure Servers และ BGP IPv4 `/24` blocks ค่าความเบ้ (Skewness) ลดลงจาก `+8..+48` เหลือเพียง **`-0.5` ถึง `+0.7`** (ใกล้เคียงการแจกแจงปกติ Mean $\approx$ Median) |
| **`raw_05_time_horizon_and_volume_mismatch.png`**<br>เวลาไม่ตรงกัน (1789–2025 vs 2018–2024) และ BGP ดิบ 6.3 ล้านแถว | **`clean_05_integrated_spine_and_tables.png`**<br>`Cleaned Data: Integrated Country-Year Spine (2022–2024) & SQLite Warehouse` | • ยุบรวม BGP 6.3 ล้านแถว (แบบไม่นับ IP ซ้ำ) และคัดคอลัมน์ V-Dem จาก 4,618 เหลือ 16 คอลัมน์<br>• Left-Join ทุกแหล่งเข้ากับ **Spine `country_year` (ปี 2022–2024, 753 แถว × 59 คอลัมน์)** โดยในกลุ่มประเทศวิเคราะห์หลัก (432 แถว) มีข้อมูลครบทั้ง 7 แหล่งสูงถึง **`95.8%`** |

---

## ส่วนที่ 2: สรุปข้อค้นพบสำคัญ (Key EDA Insights) จากข้อมูลที่ Clean แล้ว (รูปที่ 6–8)

### 1. ปัจจัยที่สัมพันธ์กับ "ปริมาณการโจมตีรวม (% Global Share)" vs "ความเข้มข้นของการโจมตี (Traffic-Normalized Intensity)" (`clean_06` & `clean_07`)
จากการวิเคราะห์สหสัมพันธ์แบบ Spearman Rank Correlation (`clean_06_correlation_heatmap.png`) และกราฟความสัมพันธ์ (`clean_07_key_factor_relationships.png`) พบข้อค้นพบสำคัญที่ต้องแยกเป็น **2 มิติ**:

* **มิติที่ 1 — ปริมาณส่วนแบ่งการโจมตีระดับโลก (`*_percent` — Global Volume Share):**
  * **ขนาดพื้นผิวเครือข่าย (Source C — CAIDA BGP `ipv4_slash24_count` และ `routed_asn_count`)** เป็นตัวแปรที่มีความสัมพันธ์เชิงบวกสูงที่สุดกับปริมาณการโจมตีทั้งฝั่งต้นทางและเป้าหมาย (Spearman $\rho = +0.85$ กับ `origin_l7_mitigated_percent` และ $\rho = +0.70$ กับ `target_ddos_percent`)
  * **โครงสร้างพื้นฐานเศรษฐกิจดิจิทัล (Source B — `secure_internet_servers_per_1m` และ `gdp_per_capita`)** สัมพันธ์เชิงบวกกับการตกเป็นเป้าหมาย DDoS ($\rho = +0.59$)
  * **ข้อสังเกตสำคัญ (Scale Confounding):** ประเทศที่มีคะแนนความพร้อมไซเบอร์สูง (`gci_score_100`) มีสหสัมพันธ์เชิงบวกกับ `% การโจมตีดิบ` ($\rho = +0.53$) **ไม่ใช่เพราะระบบป้องกันแย่ แต่เพราะประเทศที่มี GCI สูงคือประเทศเศรษฐกิจขนาดใหญ่ที่มีโครงข่าย IP และทราฟฟิกอินเทอร์เน็ตมหาศาล** นี่คือเหตุผลสำคัญที่งานวิจัยนี้ต้องควบคุมด้วยปริมาณทราฟฟิก (**Log-Ratio Attack Intensity**)

* **มิติที่ 2 — ความเข้มข้นของการโจมตีเมื่อเทียบกับขนาดทราฟฟิกของประเทศ (`Log-Ratio Intensity`):**
  * เมื่อหารด้วยสัดส่วนทราฟฟิก (`http_traffic_mean`) เพื่อดูว่า **"ประเทศใดเป็นต้นทางหรือเป้าหมายการโจมตีเกินตัวเมื่อเทียบกับทราฟฟิกปกติของตน"**:
  * **สัดส่วนทราฟฟิกบอท (`bot_traffic_percent`)** มีความสัมพันธ์เชิงบวกอย่างชัดเจนกับความเข้มข้นของการเป็นต้นทางโจมตี ($\rho = +0.58$) กล่าวคือ ประเทศที่ทราฟฟิกในประเทศมีสัดส่วน Automated Bot สูง มักเป็นแหล่งกำเนิดการโจมตี Layer 7 ในสัดส่วนที่สูงเกินขนาดทราฟฟิกปกติ
  * **คุณภาพธรรมาภิบาลและหลักนิติธรรม (Source E — `rule_of_law`, `gov_effectiveness`, `v2x_libdem`)** เมื่อดูในกลุ่มความเข้มข้นของการโจมตี พบแนวโน้มที่แตกต่างจากค่าดิบ โดยประเทศในกลุ่มหลักนิติธรรมสูงมีความผันผวนของความเข้มข้นการโจมตีต่ำกว่ากลุ่มประเทศที่ธรรมาภิบาลอ่อนแอ

### 2. ภาพรวมภูมิทัศน์การโจมตีโลก คู่โจมตี และการโจมตีระดับ Layer 3 (`clean_08_attack_landscape_targets_origins.png`)
* **Top Targets vs Top Origins:** สหรัฐอเมริกา (`USA`), จีน (`CHN`), เยอรมนี (`DEU`), สิงคโปร์ (`SGP`), และสหราชอาณาจักร (`GBR`) เป็นทั้งเป้าหมายและต้นทางหลักของทราฟฟิกการโจมตีโลก แต่มีสัดส่วนบทบาทต่างกัน (เช่น `USA` เป็นต้นทาง L7/DDoS อันดับ 1 ในขณะที่หลายประเทศเป็นเป้าหมายสูงกว่าต้นทาง)
* **คู่โจมตีหลัก (`cleaned_cloudflare_attack_pairs`):** คู่โจมตีอันดับต้นๆ ของโลกมีทั้ง **การโจมตีภายในประเทศเดียวกัน (Domestic Attacks เช่น `USA → USA`, `CHN → CHN` ซึ่งคิดเป็น `7.0%` ของคู่ติดอันดับทั้งหมด)** และการโจมตีข้ามพรมแดนระหว่างศูนย์กลางทราฟฟิกหลัก
* **ประเภทการโจมตี Layer 3 (`cleaned_cloudflare_l3_vectors`):** หลังจากแกะข้อมูลออกจาก JSON พบว่า Vector การโจมตีระดับเครือข่ายที่มีสัดส่วนเฉลี่ยสูงสุดคือ **SYN Flood, DNS Amplification, UDP Flood, และ Mirai Botnet Flood**

---

## ข้อเสนอแนะสำหรับขั้นตอนถัดไป (Hypothesis Testing & Feature Engineering)
1. **การตั้งตัวแปรตาม (Target Variable) ในขั้น Modeling:** ควรวิเคราะห์เปรียบเทียบทั้ง **2 รูปแบบ** คือ:
   * โมเดลทำนาย **Global Attack Share (`log10(target_ddos_percent)`)** (ซึ่งจะขับเคลื่อนด้วยขนาดโครงข่าย BGP `/24` blocks, Population, และขนาดเศรษฐกิจ)
   * โมเดลทำนาย **Traffic-Normalized Attack Intensity (`Log-Ratio Intensity`)** (เพื่อตัดอิทธิพลของขนาดประเทศออก แล้ววัดผลของปัจจัยด้าน Bot exposure, ธรรมาภิบาล และความพร้อมด้านไซเบอร์)
2. **การคัดเลือกตัวแปรต้น ( menghindari Multicollinearity):**
   * ในกลุ่ม Source C (BGP): `routed_asn_count`, `routed_prefix_count`, และ `ipv4_slash24_count` มีความสัมพันธ์กันสูงมาก ($\rho > 0.90$) ควรเลือก `log10(ipv4_slash24_count)` เป็นตัวแทนหลักของขนาด Attack Surface
   * ในกลุ่ม Source E (WGI/V-Dem): `gov_effectiveness` กับ `rule_of_law` สัมพันธ์กันสูงมาก ควรเลือกตัวแทนหรือรวมเป็น Composite Index
