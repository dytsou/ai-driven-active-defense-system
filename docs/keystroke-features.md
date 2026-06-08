# Keystroke 特徵規格(給前端參考)

本文件定義擊鍵動態(keystroke dynamics)模型的**訓練資料來源**、**前端要擷取/送出的原始格式**、**模型實際使用的特徵向量**,以及**部署選項**。目標:前端送的東西在「定義、單位、欄位」上跟訓練資料完全對齊,模型才會在真實登入時正確運作。

> 注意:這版改用自由文字(free-text)資料集,**不再綁定固定密碼**。使用者可自己註冊任意帳號/密碼,模型靠「打字節奏」判斷,而不是靠打了哪些字。

---

## 1. 模型在做什麼(標籤語意)

- 資料集 = `data/DATASET.zip`(Mendeley *Free-Text Keystroke Dynamics for Liveness Detection*)。
- 每一筆樣本是一次打字序列,標籤只有兩類:
  - `HUMAN` = 真人輸入
  - `*Synthesizer` = 機器合成/偽造的擊鍵(5 種合成器 × 5 種攻擊者知識等級)
- 所以模型是 **liveness / 真人 vs 機器合成** 偵測,**不是**「本人 vs 別的真人冒用」的身分驗證。
- 輸出是一個 `0~1` 的風險分數(越高越像機器/偽造),交給後端風險引擎決定 allow / step_up_mfa / block。

---

## 2. 資料集結構(`data/`,已解壓)

### 2.1 目錄樹

```
data/
├── DATASET.zip                ← 原始壓縮檔(1.3 GB)
├── GAY/                       ← corpus(語料庫,= 一個打字主題/來源)
│   ├── A10075453GKWMB0SRB9SQ/ ← subject(受試者),這層是 Amazon MTurk worker id
│   │   ├── GAY-A10075453GKWMB0SRB9SQ-1-HUMAN.csv
│   │   ├── GAY-A10075453GKWMB0SRB9SQ-1-BetweenSubject-AverageSynthesizer.csv
│   │   ├── GAY-...-1-WithinSubject100-GaussianSynthesizer.csv
│   │   └── ...               ← 每個 session 共 26 個檔(1 真人 + 25 合成)
│   └── ...
├── GUN/                       ← 同上結構,不同主題
├── KM/                        ← CMU/Killourhy-Maxion 來源,subject 為 s019/s021...
├── LSIA/                      ← subject 為純數字 id,每人 session 數最多
└── REVIEW/
```

三層:`corpus / subject / 一堆 CSV`。沒有更深的子資料夾。

### 2.2 檔名規則

```
{CORPUS}-{SUBJECT}-{SESSION}-{VARIANT}.csv
```

- `CORPUS` ∈ `GAY | GUN | KM | LSIA | REVIEW`
- `SUBJECT` = 受試者 id(MTurk id / `s0xx` / 數字,依 corpus 而定)
- `SESSION` = 第幾次輸入(整數;GAY/GUN/KM/REVIEW 為 1–4,LSIA 為 1–100)
- `VARIANT` 兩種形態:
  - `HUMAN` → 真人輸入(正樣本/負風險)
  - `{KNOWLEDGE}-{SYNTHESIZER}` → 機器合成(負樣本/高風險)

每個 session 固定 1 個 `HUMAN` + 5 種 knowledge × 5 種 synthesizer = **25 個合成檔**,共 26 檔。

### 2.3 KNOWLEDGE(攻擊者對受害者了解多少)

| 值 | 意義 |
| --- | --- |
| `BetweenSubject` | 完全不認識受害者,用「別人」的節奏合成(最弱攻擊) |
| `WithinSubject100` | 看過受害者 100 個鍵的樣本 |
| `WithinSubject500` | 看過 500 個鍵 |
| `WithinSubject2500` | 看過 2500 個鍵 |
| `WithinSubjectAll` | 拿到受害者全部樣本(最強攻擊,最難分辨) |

### 2.4 SYNTHESIZER(用什麼演算法產生假節奏)

`AverageSynthesizer` · `GaussianSynthesizer` · `HistogramSynthesizer` · `NonStationaryHistogramSynthesizer` · `UniformSynthesizer`(5 種統計合成法)。

### 2.5 規模(實測)

| corpus | subjects | 真人檔 | 全部 CSV | 每人 session 數 |
| --- | ---: | ---: | ---: | --- |
| GAY | 400 | 1,594 | 41,444 | 1–4 |
| GUN | 399 | 1,594 | 41,444 | 1–4 |
| KM | 20 | 79 | 2,054 | 1–4 |
| LSIA | 136 | 13,597 | 353,522 | 1–100 |
| REVIEW | 488 | 1,952 | 50,752 | 1–4 |
| **合計** | **1,443** | **18,816** | **489,216** | — |

合成:真人 ≈ 25:1。訓練時要注意**類別不平衡**(下採樣合成、或對真人加權)。

### 2.6 每個 CSV 的欄位

每個 CSV = 一次打字 session,逐鍵一列,**CRLF 換行**,5 個 corpus 表頭都是 `VK,HT,FT`:

| 欄位 | 意義 | 單位 |
| --- | --- | --- |
| `VK` | Windows virtual key code(按了哪個鍵) | — |
| `HT` | hold time = 放開 − 按下(按住多久) | 毫秒 ms |
| `FT` | flight time = **本鍵按下 − 前一鍵按下(down-to-down)**;第一鍵為 `-1` | 毫秒 ms |

常見 `VK`:`8`=Backspace、`16`=Shift、`32`=Space、`65–90`=A–Z、`48–57`=0–9。

重點:
- 單位是**毫秒**。`HT`/`FT` 都是整數毫秒。
- `FT` 是 **down-to-down**(實測 200 個真人檔 `FT` 從不為負,排除 release-to-press 定義)。
- 第一個鍵沒有前一鍵,`FT = -1`(哨兵值,計算特徵時要排除)。
- `VK`(打了什麼字)**不進模型**,模型只用 `HT`/`FT` 的時間統計,所以密碼內容不影響、也不外洩給模型。

---

## 3. 前端要送的原始格式(契約)

前端在使用者於密碼(或指定輸入框)打字時,記錄每個鍵的 `keydown` / `keyup` 時間戳(用 `performance.now()`,單位 ms),登入請求帶上:

```json
{
  "keystroke": {
    "present": true,
    "timing": {
      "key_down": [12.0, 110.0, 250.0],
      "key_up":   [80.0, 190.0, 330.0]
    }
  }
}
```

規則(務必照做,否則模型對不上訓練分布):

1. **單位 = 毫秒**(`performance.now()` 已是 ms,不要轉成秒)。
2. `hold_times[i] = key_up[i] - key_down[i]`(對應資料集 `HT`)。
3. `flight_times[i] = key_down[i] - key_down[i-1]`(**down-to-down**,對應資料集 `FT`)。
   - 後端會由 `key_down` / `key_up` 自己推導,前端不必送這兩組衍生欄位。
4. 第一鍵 `flight_times[0] = -1`(哨兵,後端會排除)。
5. `present = true` 只有在有效鍵數 `>= 25` 時才設;太短的序列統計不穩,且目前最佳模型以 25-key login windows 訓練。
6. 只記「字元鍵」的節奏即可;不必送 `VK`/實際字元(隱私 + 模型用不到)。送密碼明文給 ML 是不必要也不該做的。

> 相容性:現有 `timing` 已有 `key_down`/`key_up`,後端可直接由這兩個陣列推導 `hold_times`/`flight_times`,所以前端最小改動是「確保有送 `key_down`/`key_up`,且 `present` 使用 `>= 25`」。

---

## 4. 模型實際使用的特徵向量

從一次 session 的 `hold_times`(HT)與 `flight_times`(FT,排除 `-1`)算出**固定長度**特徵;目前最佳模型以 25-key login windows 訓練,太短的輸入不跑模型。特徵目前採用 24 維:

| # | 名稱 | 公式 | 說明 |
| --- | --- | --- | --- |
| 1 | `ht_mean` | mean(HT) | 平均按鍵時間 |
| 2 | `ht_std` | pstdev(HT) | 按鍵時間波動 |
| 3 | `ht_median` | median(HT) | |
| 4 | `ht_min` | min(HT) | |
| 5 | `ht_max` | max(HT) | |
| 6 | `ht_cv` | ht_std / ht_mean | 變異係數(節奏一致性) |
| 7 | `ft_mean` | mean(FT) | 平均鍵間間隔 |
| 8 | `ft_std` | pstdev(FT) | |
| 9 | `ft_median` | median(FT) | |
| 10 | `ft_min` | min(FT) | |
| 11 | `ft_max` | max(FT) | |
| 12 | `ft_cv` | ft_std / ft_mean | |
| 13 | `n_keys` | len(HT) | 鍵數 |
| 14 | `total_time_ms` | key_up[-1] − key_down[0] | 總輸入時長 |
| 15 | `typing_speed` | n_keys / (total_time_ms / 1000) | 每秒鍵數 |
| 16 | `hesitation_ratio` | count(FT > 2 × ft_median) / n_keys | 異常停頓比例 |
| 17 | `ht_p25` | percentile(HT, 25) | |
| 18 | `ht_p75` | percentile(HT, 75) | |
| 19 | `ht_iqr` | ht_p75 − ht_p25 | 按鍵時間離散度 |
| 20 | `ft_p25` | percentile(FT, 25) | |
| 21 | `ft_p75` | percentile(FT, 75) | |
| 22 | `ft_iqr` | ft_p75 − ft_p25 | 鍵間間隔離散度 |
| 23 | `ft_fast_ratio` | count(FT < 50ms) / len(FT) | 極短鍵間(rollover/重疊)比例 |
| 24 | `ht_ft_ratio` | ht_mean / ft_mean | 按鍵 vs 鍵間的相對節奏 |

實作上是 16 維基礎 + 8 維 extra = **24 維**(extra 在實驗中對短輸入一致有效,見 `docs/keystroke-experiments.md`)。後端服務由 `key_down/key_up` 自動算出這 24 維,前端只要送原始時間戳。

為什麼這些能分真人/機器:真人的 `*_std`、`*_cv`、`*_iqr`、`hesitation_ratio` 通常較高(節奏不規則);很多合成器產生的節奏過於規律或分布偏移,會在這些維度露餡。

訓練前統一做:
- `total_time_ms` 用 `key_up`/`key_down` 端點算,避免累加誤差。
- 特徵做 `StandardScaler` 標準化(scaler 參數要跟模型一起存,前端推論時要套同一組 mean/scale)。
- `ht_mean` 等若為 0(空序列)時 `*_cv` 設 0,避免除以零。

---

## 5. 模型輸入 / 輸出契約

- 輸入:上面 24 維特徵(`StandardScaler` 後)。
- 輸出:`risk_score ∈ [0,1]`(越高越像機器/偽造)。
- 後端風險引擎沿用現有對應:`>=0.9` block、`>=0.7` step_up_mfa、其餘 allow(實際門檻以 `services/keystroke-ml` 設定為準)。
- 序列太短(`present=false` 或 `n_keys < 25`):不跑模型,回退到既有統計/baseline 路徑。

---

## 6. 部署選項與 quantization 評估

需求:希望模型小到能**直接放前端**,不必每次打 API 到後端。

- **特徵只有 24 維 → 模型本來就很小。** 關鍵看選哪種模型:
  - **線性模型(Logistic Regression / Linear SVM)**:權重就是 24 個係數 + 截距 + scaler 的 mean/scale。可直接存成 JSON(< 2 KB),前端用約 20 行純 JS 做「標準化 + 內積 + sigmoid」即可,**不需要任何 ML 函式庫,也不需要 quantization**。← 最推薦的前端部署法。
  - **小型 MLP(1~2 層)**:用 `skl2onnx`/`tf` 轉 ONNX,前端用 `onnxruntime-web` 跑;檔案數十 KB。需要 quantization 的門檻通常是「數 MB 的神經網路」,這裡用不到。
  - **RandomForest / IsolationForest(樹模型)**:可用 `skl2onnx` 轉 ONNX 在前端跑,但 300 棵樹會到 MB 級,且 quantization 對「樹結構」幾乎不縮(縮的是浮點權重,樹的大小來自節點數)。**樹模型建議留在後端**。
- **結論建議:** 若要「免後端、放前端」,就選**線性模型或小 MLP**,以 JSON / ONNX 部署,**quantization 在此規模沒必要**。若要用樹集成(通常準度較好),就維持後端 `services/keystroke-ml` 推論。
- **安全提醒:** 前端推論可被使用者竄改/繞過(改 JS 直接回傳低風險)。所以前端模型只適合做「即時 UX 提示 / 降低後端負載」;**最終風險判定仍應在後端再算一次**,前端結果不可單獨採信。

---

## 7. 待確認 / 與現況的落差

- 舊 CMU 版的 31 個固定欄位作廢;改用本文件第 4 節的 24 維彙總特徵(自由文字、任意密碼皆適用)。
- 訓練腳本已建立:讀 `data/` → 抽 24 維特徵 → 標準化 → 訓練 → 存模型 + scaler。目前最佳設定見 `docs/keystroke-experiments.md`。

### 目前決定(2026-06-07)

- **推論先全部放後端**,沿用 `services/keystroke-ml` 的做法(FastAPI `/v1/risk/score`),不先做前端部署。
- **多種模型都訓練、比較後再決定怎麼搭配**:Logistic、小型 MLP、RandomForest、HistGradientBoosting、IsolationForest。用同一組 24 維特徵 + 同一個 train/test split(注意 subject 不要同時出現在 train 和 test,避免洩漏),比 ROC-AUC / FAR-FRR 後再決定要不要做 ensemble。
- 第 6 節的前端部署/quantization 評估暫時保留作未來參考,現階段不實作。
