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
python3 -m unittest discover -s tests -p 'test_sync_javdb.py'
npx wrangler deploy --dry-run
npm run deploy
```

`npm test` 會啟動獨立的本機 Worker 及暫存 KV，測試後自動清理；不使用正式 KV 或呼叫 GitHub dispatch。

### 第三步：享受全自动同步

- 从此之后，**你完全不需要任何手动操作**！
- 位于 `.github/workflows/sync.yml` 的 GitHub 定时机器人会在云端每 6 小时自动运行 `sync.js`。
- 一旦检测到有新片发布，机器人会自动更新数据并提交到你的 GitHub。
- Cloudflare 会在 10 秒内自动检测到 GitHub 变动，完成新资源的自动上线发布！
