# 法人籌碼選股（台股三大法人 × 永續 × 未來性 × 投行評等 × 量增）

每個交易日自動產出一份選股報告，並以手機友善的網站呈現（可在 iPhone Safari「加入主畫面」當 App 使用）。

- **網站**：`docs/`（GitHub Pages 靜態網站，讀取 `docs/data/` 的 JSON）
- **資料管線**：`screener/`（Python 3.12，標準庫＋Anthropic SDK）
- **排程**：`.github/workflows/daily-report`，每天 21:00（台北）執行並把報告 commit 回 repo；休市日已有報告會自動略過

## 選股流程

| 步驟 | 內容 | 資料來源 |
|---|---|---|
| 1 候選池 | 上市＋上櫃普通股（排除 ETF／ETN／權證／特別股／存託憑證），近 5 個交易日三大法人買賣超股數 × 當日收盤價逐日加總，取買超金額前 50 名。另列外資、投信 5 日買賣超，以及「買超金額 ÷ 5 日成交值」（≥10% 標「法人主導」） | 證交所 T86、MI_INDEX；櫃買中心三大法人買賣明細、上櫃行情 |
| 2A 永續 | 公司治理評鑑前 20%、臺灣永續指數／富時台灣 ESG 成分股、MSCI ESG A 以上（符合任一） | `config/sustainability.json` 手動清單，或 Claude 網路搜尋（須附來源網址） |
| 2B 未來性 | 成長產業主題（AI 伺服器、先進製程封裝、矽光子、散熱、重電儲能、機器人、低軌衛星、資安、生技新藥），或近 3 個月月營收年增率皆為正 | `config/themes.json`、公開資訊觀測站月營收、Claude 網路搜尋 |
| 2C 投行 | J.P. Morgan、BofA、Morgan Stanley、Goldman Sachs 近 3 個月評等（列出券商／評等／目標價／日期／連結；負面也列） | 自動搜尋 Google 新聞標題擷取（免費）；有 API 金鑰時再加上 Claude 網路搜尋 |
| 入選 | A、B 皆符合，且 C 不是「只有負面評等」；最多 20 檔 | |
| 3 量增 | 量增比＝5 日均量 ÷ 20 日均量，入選股依此排序，≥1.2 標「量增」 | 同步驟 1 |
| 4 報告 | 摘要、精選表、候選池前 20 名對照表、個股新聞＋當日 5 則科技新聞、資料限制、Sources | 以上全部 |

另外補充：本益比（證交所 BWIBBU／櫃買本益比）、外資持股比率 5 日變化（MI_QFIIS／櫃買僑外資持股）、融資餘額 5 日增減（MI_MARGN／櫃買融資融券）。
查不到的欄位一律顯示「—」，並寫入「資料限制說明」。

## 一次性設定

1. **合併到 main**（排程只在預設分支執行）。
2. **開啟 GitHub Pages**：Settings → Pages → Build and deployment → Source 選 *Deploy from a branch*，Branch 選 `main`、資料夾 `/docs`。網址會是 `https://<帳號>.github.io/<repo>/`。
3. **設定 API 金鑰**（啟用條件 A／C 與新聞查證）：Settings → Secrets and variables → Actions → New repository secret，名稱 `ANTHROPIC_API_KEY`。
   未設定時仍會產出報告，但永續性（除手動清單外）、投行評等、新聞會標示「未查證」，通常不會有個股入選。
4. （選用）Actions *Variables*：
   - `SCREENER_MODEL`：預設 `claude-opus-5-5`
   - `SCREENER_MAX_RESEARCH`：每日最多網路研究幾檔（預設 30；候選池前 20 名＋其餘通過條件 B 者）
5. 手動執行：Actions → daily-report → Run workflow（可指定日期、或勾選「不呼叫 Claude API」）。

> 成本提醒：每檔個股研究約使用 8 次網路搜尋，30 檔每日約數美元（依實際 token 用量而定）。可調低 `SCREENER_MAX_RESEARCH` 或改用較便宜的模型。同一交易日重跑時，已研究過的個股會使用 `docs/data/cache/` 快取。

## 本機執行

```bash
pip install -r requirements.txt
python -m pytest -q tests                  # 離線測試（使用與官方格式相同的假資料）
python -m screener --no-llm                # 只跑官方數據步驟
ANTHROPIC_API_KEY=... python -m screener   # 完整報告
python -m http.server -d docs 8000         # 開 http://localhost:8000
```

`python -m screener --date 2026-10-22` 可指定基準日；遇假日會自動往前找最近交易日（例如 2026-10-23 休市）。

## 調整清單

- `config/themes.json`：成長主題 → 股票代號對照表（初始清單為起點，請依需要增修）。
- `config/sustainability.json`：條件A（永續）名單，目前內容：
  - **公司治理評鑑前5%、6%~20%**：第十二屆（114年度，2026-04-30 公布），上市＋上櫃共 362 家，取自證交所公司治理中心評鑑結果 PDF。
  - **臺灣永續指數（FTSE4Good TIP Taiwan ESG）成分股**：臺灣指數公司未公開成分股清單，改用追蹤此指數的元大 00850 ETF 全部持股（110 檔）。
  - **MSCI ESG A 級以上**：沒有公開的整份名單，需要網路研究或手動填入。
  - **更新方式**：臺灣永續指數每年 6 月、12 月定期審核，生效後到 Actions → **update-sustainability** → Run workflow，會重新下載並更新名單。

## 資料限制

- 買超金額為「買賣超股數 × 當日收盤價」估算，非實際成交均價；「外資」為外資及陸資（含外資自營商）。
- 投行評等僅能取自公開新聞報導，券商報告本身不公開，可能遺漏或日期落差。
- 證交所／櫃買中心網站改版時解析可能失效；`tools/probe.py` 可快速檢查各端點目前的回應格式（Actions → probe-endpoints）。
- 本專案為資料整理工具，不構成投資建議。
