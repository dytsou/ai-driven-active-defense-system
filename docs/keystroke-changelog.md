# Keystroke liveness docs

branch：`keystroke-ml-2`（自 `c72f3db` 分歧）。相關文件：
[`keystroke-features.md`](keystroke-features.md)（前端對接契約）、
[`keystroke-experiments.md`](keystroke-experiments.md)（完整實驗）。

## 一句話

把登入加上「擊鍵 liveness 偵測」——判斷打字像**真人**還是**機器合成/自動化**，當成風險訊號接進現有 login → 風險分級 → MFA/block 流程。
注意：是 **liveness（真人 vs 機器）**，不是「本人 vs 別人冒用」的身分驗證。

## 模型

- 資料集：Mendeley free-text keystroke（真人 vs 合成偽造）；不再綁固定密碼，任意帳密可用。
- 特徵：24 維時間統計（HT/FT 的 mean/std/median/min/max/cv + 百分位/IQR + 打字速度 + 停頓比例…），
  由服務從 `key_down/key_up` 自算。**按 subject 切分** train/test（同一人不跨組，無洩漏），指標在門檻 0.5 下。
- 名詞：AUC 越高越好；**FAR** = 合成被當真人放過（越低越好）；**FRR** = 真人被誤擋（越低越好）。

### 試了哪些模型、表現如何

同一組 24 維特徵 + 混合長度訓練下比較（337k 樣本，1,422 受試者）：

| 模型 | ROC-AUC | FAR | FRR | 備註 |
| --- | ---: | ---: | ---: | --- |
| **HistGradientBoosting（採用）** | **0.973** | 0.051 | 0.152 | 最佳，又快又準 |
| MLP (32,16) | 0.950 | 0.080 | 0.200 | 次之；AUC 高但決策邊界較脆 |
| RandomForest | 0.937 | 0.125 | 0.162 | 穩但較弱 |
| LogisticRegression | 0.804 | 0.326 | 0.233 | 線性，明顯不足 |
| IsolationForest（one-class，只學真人） | 0.675 | 0.659 | 0.145 | **純異常偵測無用**——必須用「有合成負樣本」的監督式 |

最強攻擊（WithinSubjectAll，攻擊者拿到受害者全部樣本）下，HGB 仍有 AUC 0.93 / FAR ≈ 0.11。

### 換密碼（輸入）長度表現如何

關鍵問題：真實登入長度未知。所以做了「訓練長度 × 評估長度」矩陣（詳見實驗日誌），重點兩條：

| 輸入長度（鍵） | 10 | 15 | 20 | 25 | 30 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 長度剛好對上（上限/理想） | 0.942 | 0.958 | 0.969 | 0.975 | 0.980 |
| **採用的混合長度模型（實際部署）** | 0.918 | 0.953 | 0.965 | 0.974 | 0.976 |

- **越長越準**（鍵多 → 訊號多）。
- **混合長度模型在每個長度都接近理想值**（差 ~0.01）→ 一顆模型守住整條長度範圍，不必賭真實長度。
- 反例（為什麼不固定一個長度）：若**只用 30 鍵訓練**，帳面 train AUC 0.995 很漂亮，但拿去判**真實 10 鍵登入會崩到 0.764**（train/serve 長度錯配）。混合長度就是為了避開這個。

### 誠實限制

- **單次登入較弱**（一個短視窗雜訊大，真人偶爾被判 step_up）→ keystroke liveness 定位為**輔助風險訊號**，不是唯一關卡。
- 大量自動化（Hydra / credential stuffing）主要仍靠 rate / missing-keystroke 規則。
- 合成器是統計模型（Gaussian/Histogram/…），屬「分布內」攻擊；真實 bot 行為可能不同。

## 架構 / 整合

- 新服務 `services/keystroke-ml`（FastAPI `POST /v1/risk/score`，host port 8082 → 容器 8081）。
- 模型檔 `liveness_detector.joblib`（~3.3 MB）**已進 git**，build 不需要 1.3 GB 資料集。
- `app` 經 `ml_client` 把**原始 timing** 轉給服務 → 服務自算 24 維特徵 → 合併 ML + 規則 + per-user baseline
  → `allow` / `step_up_mfa` / `block`。
- **floor = 10 鍵**：不足就不評分 → `insufficient_keystroke → MFA`。

## 動到的共用檔（請組員知悉）

| 檔案 | 改了什麼 |
| --- | --- |
| `docker-compose.yml` | 移除壞掉/沒用的 mock-ml；加入 keystroke-ml；app `ML_RISK_URL` 指向它 |
| `app/services/ml_client.py` | 改送**原始 `key_down/key_up`**（不再壓成 3 個摘要數字） |
| `app/services/auth_service.py` | keystroke floor 改 10；每次登入記 `key_count` 到 `audit_events` |
| `app/schemas/auth.py` | 只改註解（features 24 維） |
| `frontend/src/hooks/useKeystroke.js` | **只動這一個前端檔**（見下） |
| `.gitignore` | 放行那一個模型檔 |
| `services/keystroke-ml/*` | 新服務：`main.py` / `inference.py` / `train_liveness.py` / `Dockerfile` / `README.md` / `smoke_test.py` |

### 前端只動了 `useKeystroke.js`，兩件事 + 一件還原

- **A（必要）**：用 `event.code` 配對 keydown/keyup + 略過長按（`event.repeat`）。
  原本兩陣列各自 push，**重疊打字（rollover）時會錯位 → hold time 算錯**；只有前端拿得到 `event.code`，所以必須在這修。
- **B（政策）**：`present` 門檻 3 → 10，跟服務 `min_keys=10` 對齊。
- **已還原**：`flight_times` 維持原本 up-to-up 語意；`dwell/flight` 服務根本不看，不動它們的意義。

## 前端對接

模型實際只依賴 **`timing.key_down` / `timing.key_up`**（毫秒、等長、成對、按序）+ `present`。要確認：

1. 有送 `key_down/key_up`，**單位是 ms**（`performance.now()`，不要轉秒）；
2. `present` 的 floor 用 **10**；
3. **擷取範圍 = 帳號 + 密碼合併**（目前 handler 綁在兩個輸入框，是原本就這樣）→ 請確認這是預期的。

`dwell_times` / `flight_times` 對不對都無所謂（模型不看，由服務自 `key_down/key_up` 重算）。

## 怎麼跑

```bash
docker compose up -d --build          # 整包可 build；app:8000 / keystroke-ml:8082
# 舊 DB 若報 registration_status 之類（目前無 migration）：
docker compose down -v && docker compose up -d --build
```

實測（OrbStack）：**bot → block、missing keystroke → MFA、真人 → 多半放行（偶爾 step_up）**。

真實登入長度分布（埋點後可查）：

```sql
select payload->>'key_count' as key_count, count(*)
from audit_events group by 1 order by 1;
```

## 待討論 / 決定

- 前端擷取「帳號 + 密碼」還是「只密碼」？
- 真實登入長度：已埋點（`audit_events.payload.key_count`），累積後用**真資料**定 floor，不用猜。
- 模型上 HuggingFace：暫緩（已進 git）。
- DB 沒有 migration：schema 變動需 `down -v` 重建或補 migration。
- `keystroke-ml-2` 何時合回主線、跟主要分支對齊。
