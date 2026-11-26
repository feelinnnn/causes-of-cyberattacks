# รายงานการทดสอบสมมติฐานและค่าทางสถิติ (Statistical Inference & Hypothesis Testing Report)

> **ที่มาของข้อมูล:** คำนวณจริงจากชุดข้อมูล [data/analytical/v2/features.csv](file:///home/sutthinun/src/causes-of-cyberattacks/data/analytical/v2/features.csv) ($N = 432$ แถว = $144$ ประเทศ $\times\ 3$ ปี), ผลพยากรณ์ Batch ML V1/V2 และ Online ML 30 เดือน  
> **สคริปต์ประมวลผล:** [src/analysis/statistical_inference.py](file:///home/sutthinun/src/causes-of-cyberattacks/src/analysis/statistical_inference.py) (`PYTHONPATH=src .venv/bin/python -m analysis.statistical_inference`)  
> **ไฟล์ตารางผลลัพธ์ดิบทั้งหมด (`NaN = 0, Inf = 0`):**
> * [hypothesis_block_tests.csv](file:///home/sutthinun/src/causes-of-cyberattacks/data/analytical/stats/hypothesis_block_tests.csv) (45 แถว)
> * [ols_clustered_coefficients.csv](file:///home/sutthinun/src/causes-of-cyberattacks/data/analytical/stats/ols_clustered_coefficients.csv) (455 แถว)
> * [vif_diagnostics.csv](file:///home/sutthinun/src/causes-of-cyberattacks/data/analytical/stats/vif_diagnostics.csv) (31 แถว)
> * [spearman_correlations.csv](file:///home/sutthinun/src/causes-of-cyberattacks/data/analytical/stats/spearman_correlations.csv) (125 แถว)
> * [ml_model_wilcoxon_tests.csv](file:///home/sutthinun/src/causes-of-cyberattacks/data/analytical/stats/ml_model_wilcoxon_tests.csv) (48 แถว)

---

## 1. ระเบียบวิธีทางสถิติ (Statistical Methodology)

เพื่อให้ค่า $p\text{-value}$ ในรายงานถูกต้องตามหลักสถิติระดับสากลและไม่เกิดอคติจากโครงสร้างข้อมูล Panel Data ($144$ ประเทศ $\times\ 3$ ปี):

1. **Country-Clustered Standard Errors (`cov_type="cluster"`, grouped by `iso3`):** ข้อมูล 3 ปีของประเทศเดียวกันมีความสัมพันธ์กันเอง (Serial/Within-country Correlation) จึงปรับความคลาดเคลื่อนมาตรฐานแบบจับกลุ่ม 144 ประเทศ เพื่อไม่ให้ $p\text{-value}$ ต่ำเกินจริง
2. **Cluster-Robust Nested Wald $F$-Test:** ทดสอบสมมติฐานระดับกลุ่ม ($H_0: \beta_{\text{block}} = \mathbf{0}$) โดยเปรียบเทียบระหว่างโมเดลควบคุมขนาดประเทศ (**`M0: Controls Only`** = `http_traffic_mean_log_z + population_log_z`) กับโมเดลที่เพิ่มตัวแปรสมมติฐาน $H_1, H_2, H_3$ และตรวจสอบความคงทนด้วย **Year Fixed Effects (`M4c`)** และ **ชุด Uncensored 399 แถว**
3. **Full Column Rank Guardrail สำหรับ OLS & VIF:** ในกลุ่มฟีเจอร์ V2 ทั้ง 25 ตัว มี 4 ตัวที่เป็นผลรวม/ผลต่างเชิงเส้นตรงเป๊ะของตัวแปรอื่น (`asn_per_capita_log_z`, `traffic_per_capita_log_z`, `ipv4_per_asn_log_z`, `cyber_readiness_index_z`) จึงคัด 4 ตัวนี้ออกเฉพาะในสมการ OLS และ VIF ให้เหลือตัวแปรอิสระเชิงเส้น **21 ตัว (`V2_Extended_21`)** โดยคงค่า $R^2$ เท่าเดิมทุกประการและรับประกันเมทริกซ์เต็มแรงก์ (`rank = k`) ส่วนการวิเคราะห์ Spearman ใช้ครบทั้ง 25 ตัวแปร
4. **Multiple Testing & Non-Parametric Tests:**
   * ใช้ **Spearman's $\rho$ + Benjamini–Hochberg FDR ($q\text{-value}$)** สำหรับความสัมพันธ์เชิงเดี่ยวที่ไม่พึ่งสมมติฐานเส้นตรง
   * ใช้ **Paired Wilcoxon Signed-Rank Test** ทดสอบว่าความคลาดเคลื่อนสัมบูรณ์ (`|residual|`) ของโมเดล ML V2 (`n = 144` ประเทศ ปี 2024) และ Online ML (`n = 30` เดือน และ `n = 144` ประเทศ) ต่ำกว่า Baseline อย่างมีนัยสำคัญทางสถิติ

> **เกณฑ์สัญลักษณ์นัยสำคัญทางสถิติที่ใช้ในรายงาน:** `***` $p < 0.001$, `**` $p < 0.01$, `*` $p < 0.05$, `.` $p < 0.10$ (Marginally Significant), `ns` = ไม่มีนัยสำคัญทางสถิติ ($p \ge 0.10$)

---

## 2. สรุปผลการทดสอบสมมติฐานระดับกลุ่ม ($H_1, H_2, H_3$ — Cluster-Robust Wald $F$-Test)

### ตารางที่ 1: เปรียบเทียบประสิทธิภาพและ $p\text{-value}$ รายกลุ่มสมมติฐาน (`All_432`, $N = 432$, $144$ Clusters)

| เป้าหมาย ($Y$) | แบบจำลอง (Model Spec) | $k$ | $R^2$ | $\text{Adj. } R^2$ | $\Delta R^2$ vs `M0` | Block Wald $F$ | Block $p\text{-value}$ | นัยสำคัญ | สรุปผลสมมติฐาน |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Target DDoS (Floored)** | `M0: Controls Only` (`Traffic + Pop`) | 2 | `0.2576` | `0.2542` | `0.0000` | `42.2785` | `3.75e-15` | `***` | ฐานควบคุมมีนัยสำคัญสูง |
| **Target DDoS (Floored)** | `M1a: Controls + H1 (V1, +3)` | 5 | `0.2881` | `0.2797` | `+0.0304` | `2.2098` | `0.0895` | `.` | ก้ำกึ่งใน V1 (ขาดโครงข่ายลึก) |
| **Target DDoS (Floored)** | **`M1b: Controls + H1 (V2, +9)`** | 11 | **`0.3443`** | **`0.3272`** | **`+0.0867`** | **`3.1014`** | **`0.00196`** | **`**`** | **สนับสนุน $H_1$ ชัดเจน ($p < 0.01$)** |
| **Target DDoS (Floored)** | `M2: Controls + H2 (GDP+FDI, +2)` | 4 | `0.2582` | `0.2512` | `+0.0005` | `0.0496` | `0.9516` | `ns` | **ไม่สนับสนุน $H_2$** เมื่อคุมขนาดประเทศ |
| **Target DDoS (Floored)** | `M3a: Controls + H3 (V1, +3)` | 5 | `0.2941` | `0.2858` | `+0.0365` | `2.6600` | `0.0505` | `.` | ก้ำกึ่ง ($p \approx 0.05$) |
| **Target DDoS (Floored)** | `M3b: Controls + H3 (V2, +8)` | 10 | `0.3084` | `0.2919` | `+0.0507` | `1.5661` | `0.1400` | `ns` | กลุ่มความพร้อมเดี่ยวไม่พอ |
| **Target DDoS (Floored)** | `M4a: Full V1 Core` (10 vars) | 10 | `0.3440` | `0.3284` | `+0.0864` | `4.7928` | `3.08e-05` | `***` | รวมทุกปัจจัย V1 สำคัญสูง |
| **Target DDoS (Floored)** | **`M4b: Full V2 Extended`** (21 vars) | 21 | **`0.4039`** | **`0.3733`** | **`+0.1462`** | **`4.3206`** | **`1.61e-07`** | **`***`** | **โมเดลรวม V2 สำคัญสูงสุด** |
| **Target DDoS (Floored)** | `M4c: Full V2 + Year FE` (23 vars) | 23 | `0.4087` | `0.3754` | `+0.1511` | `4.1292` | `4.07e-07` | `***` | คงทนหลังคุม Shock รายปี |
| **Target DDoS (Raw 432)** | `M1b` ($H_1$ V2) / `M4b` (Full V2) | 11/21 | `0.3289` / `0.3802` | `0.3113` / `0.3485` | `+0.0989` / `+0.1503` | `2.9789` / `4.2293` | `0.00280` / `2.50e-07` | `**` / `***` | ยืนยันผลตรงกับชุด Floored |
| **Target DDoS (Uncens. 399)** | `M1b` ($H_1$ V2) / `M4b` (Full V2) | 11/21 | `0.2893` / `0.3636` | `0.2691` / `0.3281` | `+0.0844` / `+0.1586` | `3.0703` / `4.1709` | `0.00219` / `3.77e-07` | `**` / `***` | ตัด 33 แถวศูนย์ ผลไม่เปลี่ยน |
| **Origin DDoS Intensity** | `M0: Controls Only` | 2 | `0.0403` | `0.0358` | `0.0000` | `4.7440` | `0.0101` | `*` | ขนาดประเทศอธิบายฝั่งต้นทางน้อย |
| **Origin DDoS Intensity** | **`M1b: Controls + H1 (V2, +9)`** | 11 | **`0.2340`** | **`0.2139`** | **`+0.1937`** | **`7.5440`** | **`5.36e-09`** | **`***`** | โครงข่าย/บอทอธิบายต้นทางแรง |
| **Origin DDoS Intensity** | **`M3a / M3b: Controls + H3 (V1/V2)`** | 5/10 | `0.0895` / **`0.1465`** | `0.0788` / **`0.1262`** | `+0.0492` / **`+0.1062`** | `4.0047` / **`4.2726`** | `0.00899` / **`1.25e-04`** | `**` / **`***`** | **มีนัยสำคัญเชิงสถิติ ($p < 0.001$)** แม้ $\Delta R^2$ ปานกลาง |
| **Origin DDoS Intensity** | **`M4b / M4c: Full V2 / +Year FE`** | 21/23 | **`0.3109`** / `0.3164` | **`0.2756`** / `0.2779` | **`+0.2706`** / `+0.2761` | **`5.2725`** / `5.0596` | **`1.73e-09`** / `4.69e-09` | **`***`** | ยืนยันร่วมทุกมิติ |
| **Origin L7 Intensity** | **`M1b: Controls + H1 (V2, +9)`** | 11 | **`0.2181`** | **`0.1976`** | **`+0.1854`** | **`5.4880`** | **`1.80e-06`** | **`***`** | บอท/IPv4 ขับเคลื่อนเว็บ L7 |
| **Origin L7 Intensity** | **`M3a / M3b: Controls + H3 (V1/V2)`** | 5/10 | `0.0959` / **`0.1251`** | `0.0853` / **`0.1043`** | `+0.0632` / **`+0.0924`** | `4.4300` / **`3.2778`** | `0.00520` / **`0.00184`** | `**` / **`**`** | มีนัยสำคัญเชิงสถิติ ($p < 0.01$) |
| **Origin L7 Intensity** | **`M4b / M4c: Full V2 / +Year FE`** | 21/23 | **`0.3057`** / `0.3099` | **`0.2702`** / `0.2710` | **`+0.2730`** / `+0.2772` | **`5.4806`** / `5.4416` | **`6.55e-10`** / `7.85e-10` | **`***`** | แข็งแรงที่สุดในฝั่ง Origin |

**ข้อค้นพบเชิงสถิติสำคัญจากตารางที่ 1:**
* **$H_1$ (ความเปิดรับดิจิทัล):** ได้รับการพิสูจน์อย่างแข็งแรงมาก ($F = 3.101, p = 0.00196 \text{ **}$ ในชุด Floored; และ $p = 0.00280 \text{ **}$, $0.00219 \text{ **}$ ในชุด Raw และ Uncensored 399)
* **$H_2$ (ความมั่งคั่งทางเศรษฐกิจล้วน — GDP & FDI):** **ไม่มีนัยสำคัญทางสถิติเลย** ($\Delta R^2 = +0.0005, F = 0.0496, p = 0.9516 \text{ ns}$) ยืนยันว่าประเทศร่ำรวยไม่ได้โดนโจมตีมากขึ้นเพราะตัวเงิน GDP แต่โดนเพราะความหนาแน่นของโครงสร้างดิจิทัลที่ตามมา
* **$H_3$ (ความพร้อมไซเบอร์และธรรมาภิบาล — ฝั่งต้นทาง):** ในเชิงสถิติแบบกลุ่มระดับในตัวอย่าง (`All_432`) มีนัยสำคัญชัดทั้ง Origin DDoS (`M3b`: $F = 4.273, p = 0.000125 \text{ ***}$) และ Origin L7 ($F = 3.278, p = 0.00184 \text{ **}$) โดยเฉพาะเมื่อใส่ตัวแปรปฏิกิริยาร่วม **`unsecured_asn_z`** (`p = 0.0274 *`) และพอรวมเข้า `M4b` ที่มี `bot_traffic_percent_z` + `ipv4_slash24_count_log_z` ค่า Block $p$ พุ่งไปถึง $1.73 \times 10^{-9}$ และ $6.55 \times 10^{-10}$!

---

## 3. ผลการวิเคราะห์ถดถอยพหุคูณระดับตัวแปร (Country-Clustered OLS Coefficients)

### ตารางที่ 2ก: ฝั่งผู้ถูกโจมตี (`attack_intensity_floored_log`) — เทียบ `V1 Core 10` กับ `V2 Extended 21`

| ตัวแปร (Standardized Feature) | กลุ่ม | **V1 Core (`M4a`)**: $\beta$ (SE) | V1 $t$ / $p\text{-value}$ | **V2 Extended (`M4b`)**: $\beta$ (SE) | V2 $t$ / $p\text{-value}$ | V2 95% CI | V2 VIF |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `http_traffic_mean_log_z` | Control | `+0.427` (`0.595`) | `0.72` / `0.4734 ns` | `+0.368` (`0.611`) | `0.60` / `0.5464 ns` | `[-0.829, +1.565]` | `19.49` |
| `population_log_z` | Control | `-0.790` (`0.423`) | `-1.87` / `0.0620 .` | `-0.600` (`0.526`) | `-1.14` / `0.2545 ns` | `[-1.632, +0.432]` | `16.52` |
| `internet_users_pct_z` | $H_1$ | `+0.395` (`0.266`) | `1.48` / `0.1378 ns` | `+0.153` (`0.274`) | `0.56` / `0.5754 ns` | `[-0.384, +0.691]` | `4.89` |
| **`broadband_subs_per_100_z`** | **$H_1$** | **`+0.616`** (`0.229`) | **`2.69` / `0.0071 **`** | **`+0.924`** (`0.306`) | **`3.02` / `0.0025 **`** | **`[+0.324, +1.524]`** | `6.11` |
| `routed_asn_count_log_z` | $H_1$ | `+0.630` (`0.327`) | `1.93` / `0.0541 .` | `+0.586` (`0.412`) | `1.42` / `0.1550 ns` | `[-0.222, +1.394]` | `9.76` |
| `routed_prefix_count_log_z` | $H_1$ | — | — | `+0.708` (`0.461`) | `1.54` / `0.1245 ns` | `[-0.195, +1.611]` | `12.51` |
| `ipv4_slash24_count_log_z` | $H_1$ | — | — | `-0.820` (`0.491`) | `-1.67` / `0.0948 .` | `[-1.782, +0.142]` | `11.25` |
| `secure_servers_per_1m_log_z` | $H_1$ | — | — | `+0.157` (`0.439`) | `0.36` / `0.7211 ns` | `[-0.704, +1.018]` | `10.66` |
| `ipv6_pct_log_z` | $H_1$ | — | — | `-0.165` (`0.105`) | `-1.57` / `0.1163 ns` | `[-0.370, +0.041]` | `1.48` |
| **`tls_1_3_percent_z`** | **$H_1$** | — | — | **`-0.234`** (`0.102`) | **`-2.29` / `0.0221 *`** | **`[-0.435, -0.034]`** | `1.35` |
| `bot_traffic_percent_z` | $H_1$ | — | — | `+0.008` (`0.121`) | `0.07` / `0.9479 ns` | `[-0.230, +0.246]` | `1.57` |
| `gdp_per_capita_log_z` | $H_2$ | **`-0.885`** (`0.397`) | `-2.23` / `0.0257 *` | `-0.719` (`0.420`) | `-1.71` / `0.0872 .` | `[-1.542, +0.105]` | `12.76` |
| `fdi_net_inflows_clipped_z` | $H_2$ | `-0.027` (`0.139`) | `-0.19` / `0.8476 ns` | `-0.154` (`0.129`) | `-1.19` / `0.2323 ns` | `[-0.406, +0.099]` | `1.34` |
| `gci_z_within_edition` | $H_3$ | `-0.222` (`0.245`) | `-0.90` / `0.3656 ns` | `-0.321` (`0.268`) | `-1.20` / `0.2310 ns` | `[-0.847, +0.204]` | `3.90` |
| **`v2smgovcapsec_z`** | **$H_3$** | **`+0.677`** (`0.195`) | **`3.47` / `0.0005 ***`** | **`+0.552`** (`0.197`) | **`2.81` / `0.0050 **`** | **`[+0.166, +0.937]`** | `2.64` |
| `gov_effectiveness_z` | $H_3$ | `-0.044` (`0.305`) | `-0.14` / `0.8850 ns` | `+0.401` (`0.448`) | `0.90` / `0.3703 ns` | `[-0.476, +1.279]` | `18.36` |
| `rule_of_law_z` | $H_3$ | — | — | `-0.001` (`0.444`) | `0.00` / `0.9982 ns` | `[-0.872, +0.870]` | `19.23` |
| `v2smfordom_z` | $H_3$ | — | — | `-0.044` (`0.146`) | `-0.30` / `0.7619 ns` | `[-0.329, +0.241]` | `1.43` |
| `v2x_polyarchy_z` | $H_3$ | — | — | `-0.430` (`0.222`) | `-1.93` / `0.0530 .` | `[-0.866, +0.006]` | `3.60` |
| `unsecured_asn_z` | $H_3$ | — | — | `-0.032` (`0.225`) | `-0.14` / `0.8858 ns` | `[-0.473, +0.408]` | `2.43` |
| `unsecured_broadband_z` | $H_3$ | — | — | `+0.137` (`0.184`) | `0.75` / `0.4550 ns` | `[-0.223, +0.497]` | `2.58` |

*(หมายเหตุ: ในโมเดล `M1b: Controls + H1 (V2)` ที่ยังไม่มีตัวแปร $H_2/H_3$ มาซ้อนทับ พบ `routed_prefix_count_log_z` $\beta = +1.127, p = 0.0051 \text{ **}$, `broadband_subs_per_100_z` $\beta = +0.685, p = 0.0130 \text{ *}$, `tls_1_3_percent_z` $\beta = -0.240, p = 0.0161 \text{ *}$, และ `ipv6_pct_log_z` $\beta = -0.209, p = 0.0362 \text{ *}$)*

### ตารางที่ 2ข: ตัวแปรที่มีนัยสำคัญทางสถิติ ($p < 0.10$) ฝั่งต้นทางโจมตี (`Origin DDoS` & `Origin L7`)

| เป้าหมาย & แบบจำลอง | ตัวแปรสำคัญ | กลุ่ม | $\beta$ (Std.) | Cluster SE | $t$-stat | $p\text{-value}$ | 95% CI | นัยสำคัญ |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`Origin DDoS` (`M3b`: $H_3$ V2)** | `http_traffic_mean_log_z` | Control | `+0.4061` | `0.1306` | `3.11` | `0.00188` | `[+0.150, +0.662]` | `**` |
| **`Origin DDoS` (`M3b`: $H_3$ V2)** | **`unsecured_asn_z`** ($H_1 \times H_3$) | $H_3$ | **`+0.1728`** | `0.0783` | `2.21` | **`0.02738`** | **`[+0.019, +0.326]`** | **`*`** |
| **`Origin DDoS` (`M4b`: Full V2)** | **`bot_traffic_percent_z`** | $H_1$ | **`+0.1806`** | `0.0506` | `3.57` | **`0.00036`** | **`[+0.081, +0.280]`** | **`***`** |
| **`Origin DDoS` (`M4b`: Full V2)** | **`ipv4_slash24_count_log_z`** | $H_1$ | **`+0.4613`** | `0.1519` | `3.04` | **`0.00239`** | **`[+0.164, +0.759]`** | **`**`** |
| **`Origin DDoS` (`M4b`: Full V2)** | `routed_prefix_count_log_z` | $H_1$ | `+0.3144` | `0.1497` | `2.10` | `0.03573` | `[+0.021, +0.608]` | `*` |
| **`Origin DDoS` (`M4b`: Full V2)** | `population_log_z` | Control | `-0.4707` | `0.2034` | `-2.31` | `0.02068` | `[-0.869, -0.072]` | `*` |
| **`Origin DDoS` (`M4b`: Full V2)** | `unsecured_asn_z` / `rule_of_law_z` | $H_3$ | `+0.1476` / `-0.3998` | `0.0828` / `0.2311` | `1.78` / `-1.73` | `0.0748` / `0.0837` | `[-0.015,+0.310]` / `[-0.853,+0.053]` | `.` |
| **`Origin L7` (`M4b`: Full V2)** | **`ipv4_slash24_count_log_z`** | $H_1$ | **`+0.4993`** | `0.1208` | `4.13` | **`0.000036`** | **`[+0.263, +0.736]`** | **`***`** |
| **`Origin L7` (`M4b`: Full V2)** | **`bot_traffic_percent_z`** | $H_1$ | **`+0.1662`** | `0.0527` | `3.15` | **`0.00162`** | **`[+0.063, +0.269]`** | **`**`** |
| **`Origin L7` (`M4b`: Full V2)** | `population_log_z` | Control | `-0.4313` | `0.1860` | `-2.32` | `0.02038` | `[-0.796, -0.067]` | `*` |
| **`Origin DDoS / L7` (`M4c` Year FE)** | `year_2023` (vs 2022) | Year_FE | `+0.1587` / `+0.1136` | `0.0638` / `0.0566` | `2.49` / `2.01` | `0.01289` / `0.04480` | — | `*` / `*` |

---

## 4. ผลวินิจฉัย Multicollinearity (`VIF`) — เหตุผลทางสถิติที่ต้องใช้ ML ต่อจาก OLS

### ตารางที่ 3: ค่า Variance Inflation Factor ที่มีระดับปานกลาง–รุนแรง ($\text{VIF} \ge 5.0$)

| ชุดตัวแปร | ตัวแปร (Feature) | กลุ่ม | ค่า VIF | ระดับความซ้ำซ้อน |
| :--- | :--- | :---: | :---: | :--- |
| **`V1_Core_10`** | `http_traffic_mean_log_z` / `gdp_per_capita_log_z` | Control / $H_2$ | `13.81` / `11.60` | **Severe ($\ge 10$)** |
| **`V1_Core_10`** | `population_log_z` / `gov_effectiveness_z` | Control / $H_3$ | `8.72` / `6.16` | **Moderate ($5\text{--}10$)** |
| **`V2_Extended_21`** | `http_traffic_mean_log_z` | Control | **`19.49`** | **Severe ($\ge 10$)** |
| **`V2_Extended_21`** | `rule_of_law_z` / `gov_effectiveness_z` | $H_3$ | **`19.23`** / **`18.36`** | **Severe ($\ge 10$)** |
| **`V2_Extended_21`** | `population_log_z` / `gdp_per_capita_log_z` | Control / $H_2$ | **`16.52`** / **`12.76`** | **Severe ($\ge 10$)** |
| **`V2_Extended_21`** | `routed_prefix_count_log_z` / `ipv4_slash24_count_log_z` | $H_1$ | **`12.51`** / **`11.25`** | **Severe ($\ge 10$)** |
| **`V2_Extended_21`** | `secure_servers_per_1m_log_z` | $H_1$ | **`10.66`** | **Severe ($\ge 10$)** |
| **`V2_Extended_21`** | `routed_asn_count_log_z` / `broadband_subs_per_100_z` | $H_1$ | `9.76` / `6.11` | **Moderate ($5\text{--}10$)** |

* **ประเด็นสำคัญสำหรับเขียนลงรายงาน:** ใน OLS ทั่วไป เมื่อมีตัวแปร 8 ตัวที่มี $\text{VIF} \ge 10$ (เช่น `rule_of_law_z` กับ `gov_effectiveness_z` หรือ `secure_servers_per_1m_log_z` กับ `gdp_per_capita_log_z`) ค่าสัมประสิทธิ์ $\beta$ และ $p\text{-value}$ รายตัวอาจถูกแบ่งเฉลี่ยกันจนดูเหมือนตัวแปรสำคัญไม่ Significant (เช่น `secure_servers_per_1m_log_z` ได้ $\rho = +0.477 \text{ ***}$ แต่ใน OLS ได้ $p = 0.721$) **นี่คือเหตุผลทางคณิตศาสตร์ที่ยืนยันว่าต้องขยับไปใช้ Regularized Linear (`Ridge` L2 Penalty) และ Non-linear Tree Ensembles (`Extra Trees`, `Voting Ensemble`) ในพาร์ท Machine Learning!**

---

## 5. สหสัมพันธ์แบบ Spearman ($\rho$, $p\text{-value}$ และ FDR $q\text{-value}$)

### ตารางที่ 4: ตัวแปรเด่นที่มีนัยสำคัญหลังปรับแก้ Benjamini–Hochberg FDR (`All_432`)

| เป้าหมาย ($Y$) | ตัวแปร (Feature) | กลุ่ม | Spearman $\rho$ | Raw $p\text{-value}$ | FDR $q\text{-value}$ | นัยสำคัญ (FDR) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **`Target DDoS (Floored)`** | `secure_servers_per_1m_log_z` | $H_1$ | **`+0.4773`** | `5.77e-26` | `1.44e-24` | `***` |
| | `broadband_subs_per_100_z` | $H_1$ | **`+0.4713`** | `2.82e-25` | `3.52e-24` | `***` |
| | `traffic_per_capita_log_z` | $H_1$ | `+0.4627` | `2.63e-24` | `2.20e-23` | `***` |
| | `asn_per_capita_log_z` | $H_1$ | `+0.4556` | `1.59e-23` | `9.93e-23` | `***` |
| | `routed_asn_count_log_z` | $H_1$ | `+0.4154` | `1.89e-19` | `9.45e-19` | `***` |
| | `cyber_readiness_index_z` / `v2smgovcapsec_z` | $H_3$ | `+0.3952` / `+0.3786` | `1.35e-17` / `3.60e-16` | `5.63e-17` / `9.99e-16` | `***` |
| | `gdp_per_capita_log_z` | $H_2$ | `+0.3902` | `3.67e-17` | `1.31e-16` | `***` |
| **`Origin DDoS Intensity`** | `bot_traffic_percent_z` | $H_1$ | **`+0.2907`** | `7.33e-10` | `1.83e-08` | `***` |
| | `routed_prefix_count_log_z` | $H_1$ | `+0.2736` | `7.45e-09` | `9.32e-08` | `***` |
| | `unsecured_asn_z` ($H_1 \times H_3$) | $H_3$ | **`+0.2159`** | `5.94e-06` | `4.95e-05` | `***` |
| **`Origin L7 Intensity`** | `bot_traffic_percent_z` | $H_1$ | **`+0.3424`** | `2.50e-13` | `6.26e-12` | `***` |
| | `unsecured_asn_z` / `unsecured_broadband_z` | $H_3$ | `+0.2106` / `+0.1754` | `1.01e-05` / `2.48e-04` | `1.26e-04` / `1.24e-03` | `***` / `**` |
| | `v2smfordom_z` *(การปิดกั้นข้อมูลต่างประเทศ)* | $H_3$ | **`-0.1540`** | `1.32e-03` | `5.51e-03` | `**` |

---

## 6. การทดสอบความต่างของโมเดล ML ด้วย Paired Wilcoxon Signed-Rank Test

### ตารางที่ 5: ยืนยันทางสถิติว่าโมเดล V2 และ Online ML ลด Error ได้จริง (ไม่ใช่ความบังเอิญ)

| โดเมน | โจทย์ (Task) | การเปรียบเทียบ (`Candidate` vs `Reference`) | หน่วย ($n$) | Mean Error (`Ref → Cand`) | ลด Error | Wilcoxon $p$ (2-sided) | นัยสำคัญ |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Batch 2024** | `Target_DDoS_Intensity` | V2 `Extra_Trees` vs `Dummy_Mean` | `144` ประเทศ | `1.8271 → 1.3390` | `-26.72%` | **`3.64e-06`** | `***` |
| **Batch 2024** | `Target_DDoS_Intensity` | V2 `Extra_Trees` vs `Controls_Only_OLS` | `144` ประเทศ | `1.5687 → 1.3390` | `-14.64%` | **`9.72e-04`** | `***` |
| **Batch 2024** | `Target_DDoS_Intensity` | V2 `Extra_Trees` vs V1 `Gradient_Boosting` | `144` ประเทศ | `1.4672 → 1.3390` | `-8.74%` | **`4.69e-04`** | `***` |
| **Batch 2024** | `Target_DDoS_Floored` | V2 `Voting_Ensemble` vs `Controls_Only_OLS` | `144` ประเทศ | `1.5409 → 1.3501` | `-12.38%` | **`0.00105`** | `**` |
| **Batch 2024** | `Target_DDoS_Forecast_Lag1` | V2 `Extra_Trees` vs V2 Structural `Voting` | `144` ประเทศ | `1.3501 → 1.1628` | `-13.88%` | **`0.02205`** | `*` |
| **Batch 2024** | `Origin_DDoS_Intensity` | V2 `Extra_Trees` vs `Controls_Only_OLS` | `144` ประเทศ | `0.6673 → 0.5469` | `-18.05%` | **`4.45e-04`** | `***` |
| **Batch 2024** | `Origin_DDoS_Intensity` | V2 `Extra_Trees` vs V1 (`H3`) `Extra_Trees` | `144` ประเทศ | `0.6500 → 0.5469` | `-15.86%` | **`9.20e-05`** | `***` |
| **Batch 2024** | `Origin_L7_Intensity` | V2 `Gradient_Boosting` vs `Controls_Only_OLS` | `144` ประเทศ | `0.5236 → 0.3751` | `-28.35%` | **`1.60e-06`** | `***` |
| **Batch 2024** | `Origin_L7_Intensity` | V2 `Gradient_Boosting` vs V1 (`H3`) `Extra_Trees` | `144` ประเทศ | `0.4620 → 0.3751` | `-18.80%` | **`8.46e-06`** | `***` |
| **Online 30m** | `Target_DDoS_Intensity` | `Champion–Challenger` vs `Frozen_Baseline` | `30` เดือน (RMSE) | `1.9158 → 0.7124` | **`-62.81%`** | **`1.86e-09`** | `***` |
| **Online 30m** | `Target_DDoS_Intensity` | `Champion–Challenger` vs `Online_SGD` | `30` เดือน (RMSE) | `0.8923 → 0.7124` | `-20.16%` | **`5.59e-09`** | `***` |
| **Online 30m** | `Target_DDoS_Intensity` | `Champion–Challenger` vs `Sliding_Retrain_8m` | `144` ประเทศ (MAE) | `0.5584 → 0.5416` | `-3.00%` | **`3.62e-08`** | `***` |
| **Online 30m** | `Origin_DDoS_Intensity` | `Champion–Challenger` vs `Frozen_Baseline` | `30` เดือน (RMSE) | `1.1047 → 0.5804` | **`-47.46%`** | **`1.86e-09`** | `***` |
| **Online 30m** | `Origin_L7_Intensity` | `Champion–Challenger` vs `Frozen_Baseline` | `30` เดือน (RMSE) | `1.0312 → 0.6079` | **`-41.05%`** | **`1.86e-09`** | `***` |

* **ค่า `p-value` ของ Data & Concept Drift (จาก `KS-Test` ใน [online_drift_events.csv](file:///home/sutthinun/src/causes-of-cyberattacks/data/analytical/online/online_drift_events.csv)):**
  * เกิด Drift ทั้งสิ้น `12` ครั้ง (Target DDoS), `10` ครั้ง (Origin DDoS) และ `11` ครั้ง (Origin L7) โดยเหตุการณ์ `Data+Concept_Drift` และ `Data_Drift` มีค่า Median `min_ks_pvalue < 0.0001` (`max_feature_z_shift` สูงสุด `1.33 SD`)
  * โดยเฉพาะในเดือนวิกฤต **`2023-01`** ที่ Cloudflare API เปลี่ยนสเกลรายปี ระบบตรวจพบ `Concept_Drift` พร้อมกันทั้ง 3 โจทย์ด้วย **`min_ks_pvalue = 0.03686`** (`Target DDoS`, RMSE `1.2887 > 0.7711`), **`0.00230`** (`Origin DDoS`, RMSE `1.0489 > 0.6263`) และ **`0.00367`** (`Origin L7`, RMSE `1.1210 > 0.6481`)

---

## 7. สรุปสำหรับเขียนอภิปรายผลในเล่มรายงาน

1. **แยกแยะ *In-Sample Inference* vs *Out-of-Sample Generalization* ให้ชัด:** ในเชิงสถิติ $H_3$ มีนัยสำคัญในกลุ่มตัวอย่าง (`p = 0.000125` สำหรับ Origin DDoS) เมื่อรวม `unsecured_asn_z` แต่เมื่อทดสอบทายประเทศใหม่แบบ Cross-Validation (`GroupKFold R²`) ยังได้ค่าติดลบ สะท้อนว่า "ความพร้อมไซเบอร์มีนัยสำคัญเชิงความสัมพันธ์ แต่มีกำลังทำนายเดี่ยวไม่เพียงพอถ้าไม่รู้ขนาดโครงสร้างพื้นฐานและบอทเน็ตจริง (`H1`)"
2. **ชี้เหตุผลรองรับการใช้ ML ต่อยอดจาก OLS:** ค่า `VIF` สูงสุดถึง `19.49` ใน `V2_Extended_21` เป็นหลักฐานเชิงปริมาณว่าทำไม Linear OLS แบบธรรมดาจึงแกว่ง และทำไม `Voting_Ensemble` / `Extra_Trees` จึงพัฒนาความแม่นยำเหนือกว่า `Controls_Only_OLS` อย่างมีนัยสำคัญทางสถิติ (`Wilcoxon p < 0.0011`)
3. **ข้อจำกัดสำคัญที่ต้องระบุเสมอ:** ข้อมูลเป็นระดับมหภาครายประเทศแบบ Observational Panel (3 ปี) จึงพิสูจน์ได้ในระดับ **ความสัมพันธ์ทางสถิติที่มีการควบคุมตัวแปรกวน (Controlled Association)** และ **ความแม่นยำเชิงพยากรณ์ (Predictive Validity)** ไม่ใช่ความสัมพันธ์เชิงสาเหตุสมบูรณ์ (Strict Causality)
