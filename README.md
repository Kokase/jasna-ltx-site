# Jasna-LTX 资源库 (1:1 独立复刻与自动同步版)

本工程是针对 `Jasna-LTX 资源库` 的 1:1 完整技术复刻，具备**零维护、全自动定时同步、纯前端极速响应、暗黑设计系统与下载器直接联动**的能力。

---

## 🌟 核心功能特性

1. **1:1 暗黑拟物视觉规范**：
   - 极深碳黑底色 (`#0c0c0e`)、高质感卡片 (`#141418`) 与品牌粉红强调色 (`#e83e8c`)。
   - 左侧女优分类抽屉实时统计，右侧自适应栅格卡片流。
2. **纯前端零延迟检索**：
   - 支持番号、女优、片商、日文/中文标题拼音模糊检索。
   - 多维度即时排序（评分、日期、入库时间、体积、番号、随机排序）。
   - 无限滚动触底平滑加载（`IntersectionObserver`）。
3. **下载中枢与集成设置**：
   - 一键复制 ed2k / 磁力链接，支持精简文件名。
   - 批量导出面板（一键复制全部链接、统计累计下载总容量）。
   - 直连 **Aria2 RPC**、**115 云下载**。
4. **全自动云端同步（无需手动干预）**：
   - 内置 `scripts/sync.js` 同步引擎，自动比对源头最新发布的 LTX 压制种子。
   - 内置 `.github/workflows/sync.yml`，在 GitHub Actions 云端**每 6 小时自动巡检一次**，发现新资源自动入库并触发 Cloudflare 自动部署。

---

## 🚀 目录结构

```
jasna-ltx/
├── index.html                  # 1:1 纯前端单页应用
├── css/
│   └── style.css               # 原版 CSS 变量、毛玻璃与暗黑样式
├── js/
│   └── app.js                  # 极速搜索、过滤、排序与下载联动引擎
├── data/
│   └── movies.json             # 核心数据库（包含资源详情、评分、字幕与时间戳）
├── scripts/
│   └── sync.js                 # 全自动数据更新同步引擎
├── .github/
│   └── workflows/
│       └── sync.yml            # GitHub Actions 云端定时作业（每 6 小时自动跑）
├── wrangler.toml               # Cloudflare Workers 設定檔
└── README.md
```

---

## 🛠️ 上线与自动同步配置步骤（大白话教程）

### 第一步：推送到你的 GitHub

1. 在 [GitHub](https://github.com/) 上新建一个空仓库（例如名为 `my-ltx-hub`）。
2. 在本地终端进入本目录，执行以下命令推送到 GitHub：
   ```bash
   git init
   git add .
   git commit -m "feat: init Jasna-LTX replica"
   git branch -M main
   git remote add origin https://github.com/你的用户名/my-ltx-hub.git
   git push -u origin main
   ```

### 第二步：在 Cloudflare Workers 連接 Git

1. 在 [Cloudflare 控制台](https://dash.cloudflare.com/) 開啟 Workers 和 Pages，建立或選擇 Worker `jasna-ltx-site`。
2. 連接 Git repo `Kokase/jasna-ltx-site`，Production branch 選擇 `main`。
3. 沿用以下 Workers Builds 設定：
   - **Build command**：留空。
   - **Deploy command**：`npx wrangler deploy`。
   - **Root directory**：repo 根目錄（`/`）。
4. Wrangler 的 `[build]` 會自動執行 `npm run build`，把原有 `functions/api/` 編譯成 `dist/worker/index.js`。`/api/*` 保留原有路由、HTTP method 及回應格式，其餘路徑由 Workers Static Assets 提供，並沿用 `_headers`。
5. `wrangler.toml` 的 `LTX_KV` binding 指向此部署帳戶的 `jasna-ltx-site-LTX_KV` namespace。若 fork 到另一個帳戶，請先建立該帳戶的 KV namespace，再替換 `id`。沿用同一 namespace 才會保留現有資料；`npm run dev` 預設使用本機 KV。
6. `/api/sync` 使用 runtime secret `GITHUB_TOKEN` 觸發 `Kokase/jasna-ltx-site` 的 `sync.yml`（`main` branch）。Token 只需此 repo 的 Actions 讀寫權限，並須在 Worker 的 Variables and Secrets 中以 secret 設定，勿放入 Git 或僅設定於 build environment。Token 到期時須在此處更新；排程 workflow 本身使用 GitHub 自動提供的 `GITHUB_TOKEN`。

`scripts/build-assets.mjs` 只把現有公開檔案及 `css/`、`js/`、`data/`、`dl/`、`xdown/` 複製至 `dist/client/`，避免上傳 server-side 程式碼、設定及依賴；新增其他公開檔案或目錄時須同步更新這份清單。

本機開發、驗證及部署：

```bash
npm install
npm run dev
npm test
python3 -m unittest discover -s tests -p 'test_*.py'
npx wrangler deploy --dry-run
npm run deploy
```

`npm test` 會啟動獨立的本機 Worker 及暫存 KV，測試後自動清理；不使用正式 KV 或呼叫 GitHub dispatch。

### 第三步：啟用及驗證自動同步

- Fork 後，在 GitHub Actions 頁面啟用 Actions，再開啟 `sync.yml` 並選擇 **Enable workflow**；fork 的排程 workflow 預設停用。
- `.github/workflows/sync.yml` 每六小時先合併 `imports/sync-source.json`，再執行 `scripts/sync_javdb.py`。排程為 UTC `0 */6 * * *`，即台北時間 02:00、08:00、14:00、20:00；實際開始時間可能因 GitHub 排隊而延遲。
- `POST /api/sync` 或 GitHub 的 **Run workflow** 可手動觸發同一流程。API 回應成功只代表已觸發，完整結果須查看該次 Actions run。
- Workflow 發現資料變更後會提交到 `Kokase/jasna-ltx-site` 的 `main`，再由 Cloudflare 自動構建及部署。沒有新增項目時，既有資料的補錄仍會逐批執行。


### 同步範圍及圖片載入

workflow 的 JavDB 步驟只從首頁、SIRO 及 GANA 分類頁挑選作品，每次最多新增 20 筆。新增項目是作品資料，下載連結仍然留空；這不是參考站的完整資料鏡像。JSON 合併步驟則只使用你提交至 `imports/sync-source.json` 的值，不會自行搜尋圖片或下載連結。

作品列表每批顯示 24 張卡片，接近頁尾 300px 時追加下一批。海報及側欄頭像只在接近可視範圍時建立圖片元素，離開範圍後卸載；文字卡片及其尺寸保留，向上捲動時圖片重新載入。這限制了活躍圖片數量，但不會清除瀏覽器自行管理的圖片快取。

### 本機 JSON 匯入及差異報告

`scripts/import_json.py` 只讀取你提供的本機 JSON，不會連接或抓取外站。接受 `{"items": [...]}` 或直接的作品陣列，每筆必須有非空字串 `code`；作品欄位沿用 `data/movies.json` 格式。先把匯出檔放到 `work/imports/export.json`，再預覽：

```bash
python3 scripts/import_json.py work/imports/export.json --report work/imports/preview.json
```

預設只產生報告，不修改作品資料。報告包含新增番号、本站獨有番号、每個補入欄位的前後值、重複列及衝突的雙方值。檢查報告後，可明確套用：

```bash
python3 scripts/import_json.py work/imports/export.json --apply --report work/imports/applied.json
```

合併規則：

- 番号只忽略大小寫及首尾空白；保留中間符號和前置零，避免誤認不同作品。
- 匯入檔的重複番号先合併，衝突時保留最先出現的非空值。若本站資料本身有重複番号，工具會停止，避免自動刪除既有紀錄。
- 已有作品的非空值優先，`0` 和 `false` 亦屬有效值。只補 `null`、空白字串、空陣列或空物件；陣列以原順序追加不重複內容，物件逐欄合併。本站獨有作品、欄位及排列次序保留，新作品追加到尾部。
- 同時接受單一 `link` 和 `links` 陣列，會補齊網站使用的 `links`。既有連結的確認狀態不變；新連結沿用匯出檔的 `pending_links`，只有未提供此陣列時才使用單一連結的 `linkPending`。缺少狀態的新作品預設待確認，不會自動核實外部連結。
- 新作品會補齊網站必須的欄位及型別。根層 `avatars`、`genres`、`buzz`、統計等 metadata 保留本站版本；匯出檔這些根層欄位只列入 `ignored_root_fields`，不匯入。作品內的 genre ID 需與本站對應。
- 重複匯入相同內容不會再追加作品、更新時間戳或建立多餘備份。

`--apply` 有實際變更時，會先把原檔逐 byte 備份到 `work/import-backups/`，再以同目錄暫存檔原子替換；如讀取後發現目標檔已改動，會停止並要求重新預覽。備份路徑寫入報告，備份及匯出工作目錄已排除於 Git，亦不在公開 assets 白名單內。`--target PATH` 可指定另一份資料檔作測試。

匯入不修改 API、KV、secret 或六小時排程；現有自動同步仍會按番号略過已收錄作品。套用及測試後，檢查 `git diff -- data/movies.json`，再提交正式資料變更，Cloudflare 才會部署該份資料。請先更新本機 `main`，並避免在同一 checkout 同時執行匯入及同步程式。

### API 更新時合併 JSON 及排查缺漏

固定來源為 `imports/sync-source.json`，目前以既有 4,330 筆基本資料快照建立。之後把你提供的新 JSON 更新到此路徑並提交至 `main`，便可由同一個 API 或排程執行。來源檔只供 workflow 使用，不會複製到公開 assets；`source` 欄位只記錄出處，不會用來抓取外站。

```bash
# 沿用原有完整更新：先合併 JSON，再執行原有同步
curl -X POST https://jasna-ltx-site.gugugwear.workers.dev/api/sync

# 只合併已提供的 JSON，不執行外站抓取
curl -X POST 'https://jasna-ltx-site.gugugwear.workers.dev/api/sync?mode=import'

# 讀取正式部署資料的缺漏報告
curl 'https://jasna-ltx-site.gugugwear.workers.dev/api/sync?audit=1'
```

API 的原有回應格式保留，POST 成功仍只表示已觸發 Actions。workflow 會先跑匯入測試，再以 `--fill-empty-only` 合併：非空字串、數字、布林及陣列均保留，只有空值才補入；已有連結的確認狀態亦保留。沒有資料變更時不會提交多餘的資料更新。有變更時沿用原有 bot commit 及 Cloudflare 部署流程。

若提供的 JSON 包含 `cover`、`shot`、`links` 或單一 `link`，可依上述規則補入空白欄位；現有快照沒有這些內容，因此不會因此新增圖片或連結。只有 `rawScore` 的新紀錄會同時以此值初始化網站使用的 `score`。

每次 build 會根據部署資料產生 `data/sync-audit.json`，由 `GET /api/sync?audit=1` 回傳。報告的 `updated_at` 是資料版本，並列出 `total`、`missing_cover`、`missing_links`、`missing_both`、`complete` 及各番号的 `missing` 欄位。這只檢查封面和連結欄位是否有值，不會測試遠端 URL 是否有效；報告本身不含圖片或下載 URL。

### 可疊加的列表篩選

頁首的「有連結」及「中文」是獨立切換按鈕，可與搜尋、演員、確認狀態、片商、分類、連結類型及想看清單同時生效；條件以 AND 合併，先篩選整份資料，再排序及分批顯示。開啟時會更新結果總數，網址以 `linked=1` 及 `sub=1` 保留狀態，重新載入或使用上一頁亦會還原。

「有連結」只代表紀錄內已有非空連結，包括待確認連結，不驗證外部檔案是否有效；可再疊加「已確認」狀態。原本「中文」只隱藏已載入卡片的方式已改為資料層篩選，避免數量及分頁不一致。
