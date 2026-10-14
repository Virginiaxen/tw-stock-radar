# 台股 AI 投資研究雷達 V2.0（真實資料 MVP）

這是**真實資料驅動**的個人研究原型，不是已驗證的投資策略，也不是已完成的 AI 新聞分析服務。初次開啟不會有股票價格，必須先成功執行資料更新。未取得資料時不會使用假數據。

## 已實作
- FinMind API v4 取得指定台股歷史收盤價、成交量、月營收、EPS 原始紀錄（若供應者有提供）。
- 20/60 日簡單移動平均、14 日 RSI、歷史收盤價折線圖、股票代號搜尋。
- 手動輸入**已核對的未來 12 個月 EPS**，計算 PE 基準合理價、安全邊際買價；可選失效價與最低報酬風險比反推買價上限。
- GitHub Actions 每個台灣工作日約 17:20 排程取得資料，GitHub Pages 自動發布靜態網站。
- 來源日期、更新時間、缺漏與過期提示；不會用假資料補洞。

## 尚未實作
- 全市場自動選股與品質評分、法人籌碼、法說/新聞 AI 分析、財務數據自動轉換成可驗證 TTM/Forward EPS、券商下單、回測績效、個人登入及價格推播。
- 「每日更新」代表每天嘗試抓取；假日、API 限流、排程延遲、來源資料尚未公布都可能影響新鮮度。

## 雲端部署：GitHub Pages（新手步驟）
1. 登入 https://github.com/，建立**新的 Repository**，例如 `tw-stock-research`。建議先用 Private 測試；**注意 GitHub Pages 是否支援私有網站存取取決於方案，且 Pages 網址可能公開**。不要上傳交易紀錄、個人資訊或任何秘密。
2. 解壓 ZIP，將整個專案內容（包括隱藏資料夾 `.github/workflows/`）上傳至儲存庫根目錄，預設分支命名 `main`。最容易的方法是用 GitHub Desktop：File → Add Local Repository / Create Repository from Existing Files，再 Publish repository。若使用網頁 Upload files，請確認隱藏的 `.github` 資料夾也已上傳。
3. 到儲存庫 `Settings → Secrets and variables → Actions → New repository secret`，名稱填 `FINMIND_TOKEN`，值填你的 FinMind API Token（依 FinMind 現行規則申請）。**不要把 Token 寫進 HTML、Python 原始碼或提交到 GitHub。**
4. 到 `Settings → Actions → General`，將 Workflow permissions 設為 `Read and write permissions`（若組織政策允許）。
5. 到 `Settings → Pages → Build and deployment → Source` 選 `GitHub Actions`。
6. 到 `Actions → Update Taiwan stock data → Run workflow` 手動執行一次。成功後會更新 `data/snapshot.json`，並觸發 `Publish site` 工作流程。
7. 到 `Settings → Pages` 找到網址，通常形如 `https://你的帳號.github.io/tw-stock-research/`。若頁面顯示「尚未取得資料」，回到 Actions 查看 Update 工作的錯誤訊息。
8. 每個台灣工作日約 17:20 系統會嘗試更新。GitHub 排程可能延遲或跳過，且資料來源可能尚未更新；可手動執行補抓。

### 如何新增追蹤股票
編輯 `stocks.json`，例如 `{"stocks":["2330","2317","2454"]}`，儲存後到 Actions 手動執行資料更新。**V2 只更新名單中的股票，不是掃描所有上市櫃股票**。股票代號是否受資料來源支援須自行確認。

### 在 Mac 本機測試
安裝 Python 3.10+，開啟「終端機」並切換到解壓的專案資料夾：
```bash
export FINMIND_TOKEN='你的Token'
python3 scripts/build_data.py
python3 -m http.server 8000
```
然後在 Safari 開啟 `http://localhost:8000/`。請勿直接雙擊 HTML 檔案：Safari 的 `file://` 安全限制可能阻止載入 JSON。

## 資料與模型重要限制
- EPS 是 FinMind `TaiwanStockFinancialStatements` 中 `type=EPS` 的**原始紀錄**，不同資料集可能使用不同命名、累計口徑或季別；程式不自動將其當成近四季 EPS。
- 合理價計算 `EPS × 合理 PE` 僅適合部分有穩定獲利的公司。ETF、金融股、景氣循環股、虧損股不可直接套用同一方法。
- 安全邊際買價 `合理價 × (1-安全邊際)`；若有有效失效價 S、目標價 T、最低 R 值 r，另一上限為 `(T+rS)/(1+r)`，最終取較低者。未納入稅費、滑價、跳空或估值誤差。
- `FINMIND_TOKEN` 只在 GitHub Actions 的伺服端使用；網站只公開 `snapshot.json`。**GitHub Pages 是公開內容發布工具，不是私有投資帳戶系統。**
- FinMind 免費/付費 API 額度、資料集與授權可能變動，請以 https://finmind.github.io/ 為準。

## 故障排除
- `No valid prices fetched`：確認 Token、額度、股票代號及 FinMind API 狀態；工作流程失敗時不會發布空白快照。
- 財報欄位為空：資料集格式、權限或公司資料可能不同；此版本刻意不推測 EPS。
- GitHub Pages 404：確認 `Pages → Source = GitHub Actions`、`main` 分支、Publish site 成功。
- 股票顯示「可能過期」：看個股的資料日期，而不是只看工作流程執行時間。
- 排程未觸發：GitHub Actions 的 cron 不保證準時，必要時手動 Run workflow。
