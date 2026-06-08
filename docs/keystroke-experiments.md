# Keystroke liveness 模型實驗日誌

記錄訓練/調參的實驗與結果(含未達標的「失敗」結果,作為報告佐證)。
資料集、特徵定義見 `docs/keystroke-features.md`;訓練腳本 `services/keystroke-ml/train_liveness.py`。

通用設定:標籤 HUMAN=0 / 合成=1;**按 subject 切分** train/test(同一人不跨組,避免洩漏);
合成抽樣 `synth_per_session=2`(真人:合成 ≈ 1:2);指標在門檻 0.5 下計算。
- **AUC** 越高越好;**FAR** = 合成被當真人放過(越低越好);**FRR** = 真人被當合成誤擋(越低越好)。

---

## 背景:為什麼要做視窗化

全長 free-text session(~700 鍵)上模型極強(AUC ~0.98),但**真實登入只打 ~15 鍵的密碼**,
屬於分布外。於是把每個 session 切成固定長度 `window` 的區塊,每塊當一次「登入長度」樣本訓練。

---

## 實驗 1:視窗大小可行性探針(子集)

設定:`--corpora GAY --max-subjects 50`,各 window 比較最佳模型 AUC。

| window | MLP AUC | RF AUC | MLP FAR/FRR@0.5 | 樣本數 |
| ---: | ---: | ---: | --- | ---: |
| full(~700) | 0.981 | 0.977 | 0.04 / 0.06 | 600 |
| 25 | 0.913 | 0.899 | 0.15 / 0.19 | 21,112 |
| 20 | 0.896 | 0.891 | 0.18 / 0.21 | 26,474 |
| 15 | 0.876 | 0.874 | 0.20 / 0.23 | 35,403 |

結論:短輸入「可行但變弱」(AUC 0.88–0.91,遠高於亂猜 0.5);**越長越好**;
0.5 門檻下誤差偏高(~15–23%),需靠更多資料 + 換模型 + 調門檻改善。

---

## 實驗 2:全量資料 + 加入 HistGradientBoosting(window=20)

設定:`--corpora GAY,GUN,REVIEW,LSIA --window 20 --max-windows 6`,337,266 樣本,1,422 受試者。

| 模型 | AUC | ACC | FAR | FRR | fit(s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| **HistGradientBoosting** | **0.9620** | 0.899 | 0.058 | 0.185 | 3.7 |
| MLP | 0.9400 | 0.866 | 0.076 | 0.250 | 34.3 |
| RandomForest | 0.9335 | 0.859 | 0.127 | 0.170 | 24.2 |
| LogisticRegression | 0.8633 | 0.756 | 0.257 | 0.218 | 0.8 |
| IsolationForest(1-class) | 0.6806 | 0.540 | 0.603 | 0.173 | 1.0 |

HGB 分攻擊者知識等級(AUC / FAR):

| 知識等級 | AUC | FAR@0.5 |
| --- | ---: | ---: |
| BetweenSubject | 0.959 | 0.059 |
| WithinSubject100 | 0.999 | 0.001 |
| WithinSubject500 | 0.979 | 0.024 |
| WithinSubject2500 | 0.947 | 0.083 |
| WithinSubjectAll(最強) | 0.925 | 0.127 |

結論:**全量資料 + HGB 是目前最佳**(window=20:0.896→0.962)。HGB 又快又準、明顯勝過 MLP/RF;
純 one-class(IsolationForest)依舊無用。最強攻擊 WithinSubjectAll 仍有 AUC 0.925。
FRR 0.185 偏高(18.5% 真人會被擋),下一步靠門檻調校 + 風險分級(邊界→step_up_mfa)緩解。

---

## 實驗 3:HGB 視窗大小掃描(全量)

| window | AUC | FAR | FRR | WithinSubjectAll AUC |
| ---: | ---: | ---: | ---: | ---: |
| 15 | 0.9500 | 0.068 | 0.216 | 0.907 |
| 20 | 0.9620 | 0.058 | 0.185 | 0.925 |
| 25 | 0.9698 | 0.052 | 0.161 | 0.938 |
| 30 | 0.9742 | 0.049 | 0.148 | 0.946 |

單調變好(鍵越多訊號越多)。但越長越要使用者多打字;前端擷取「帳號+密碼」合併,
實務約 20–25 鍵 → **取 window=25 為操作點**(AUC 0.970)。

## 實驗 4a:特徵工程(base 16 維 vs +8 extra = 24 維)

新增 `EXTRA_COLUMNS`:`ht_p25/p75/iqr`、`ft_p25/p75/iqr`、`ft_fast_ratio`(flight<50ms 比例,反映 rollover)、`ht_ft_ratio`。

| 設定 | AUC | WithinSubjectAll AUC |
| --- | ---: | ---: |
| w20 base(16) | 0.9620 | 0.925 |
| w20 +extra(24) | 0.9669 | 0.933 |
| w25 base(16) | 0.9698 | 0.938 |
| **w25 +extra(24)** | **0.9754** | **0.949** |

extra features 一致有效(+0.005~0.006 AUC,對最強攻擊更明顯)→ 採用 24 維。

## 實驗 4b:HGB 超參數掃描(w25 + extra,337k 樣本)

| 設定 | AUC | FAR | FRR |
| --- | ---: | ---: | ---: |
| A lr.1 it300(原) | 0.9754 | 0.048 | 0.144 |
| **C lr.1 it500 leaf63** | **0.9774** | 0.045 | 0.138 |
| E lr.05 it800 leaf63 +class_weight | 0.9772 | 0.072 | 0.094 |

C 最佳。E 用 class_weight 把 FRR 壓到 0.094(代價 FAR 升到 0.072),需要少誤擋時可選。

## 實驗 4c:門檻 / 風險分級(最佳模型 C)

門檻掃描(FAR/FRR 取捨曲線):

| thr | FAR | FRR |
| ---: | ---: | ---: |
| 0.40 | 0.031 | 0.174 |
| 0.50 | 0.045 | 0.138 |
| 0.70 | 0.085 | 0.081 |
| 0.90 | 0.186 | 0.029 |

風險分級(allow<0.4 / step_up 0.4–0.9 / block≥0.9):

| | allow | step_up_mfa | block |
| --- | ---: | ---: | ---: |
| 真人 | **82.6%** | 14.6% | 2.9% |
| 合成 | 3.1% | 15.5% | **81.4%** |

**最終選擇:HistGradientBoosting(lr0.1, it500, leaf63)+ window=25 + 24 維特徵,AUC 0.977。**
搭配風險分級,真人僅 2.9% 被硬擋、合成 81.4% 被擋,step_up_mfa 吸收不確定性,登入體驗可接受。
