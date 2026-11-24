# Handoff

## 本分支（claude/aplus-ui-kit）交接

- **任務**：前端套用共用 UI 套件（統一風格、離線字型、繁中／日文／英文切換）。
- **目前做到哪**：只改 `frontend/`，本機驗證完成，未部署、未合併 main。
- **分支與 commit**：`claude/aplus-ui-kit`，從 main `2fba6b4` 開出；`cc2c9a0` 前端導入，以及本次交接 commit。
- **改了什麼**：
  - `frontend/static/aui/`：UI 套件 dist 複本（CSS token、元件、Noto Sans TC 子集字型 SIL OFL、`au-i18n.js`），由後端既有的 `/static` 掛載提供；拿掉 Google Fonts。
  - `frontend/static/css/main.css`：舊變數與寫死的顏色改指向套件 token，支援淺／深色；圓角對齊套件。
  - `frontend/templates/index.html`：頂列＋語言選單；靜態文字標上 `data-i18n-p`。
  - `frontend/static/js/app.js`：卡片按鈕、空狀態、連線狀態、規則編輯標題改用 `AUI18n.p()`，切換語言時重畫。字典 `frontend/static/js/i18n-phrases.js`（英文原文 → 繁中／日文）。
- **已驗證的證據**：2026-11-22 以本機靜態伺服器（API 回空資料）確認繁中、日文、深色與規則編輯視窗畫面正常；前後截圖在 `docs/ui-kit/`。後端未改、未跑後端測試。
- **未完成與下一步**：toast 訊息與後端錯誤訊息未翻；日文為 AI 翻譯，待母語者校對；部署需重新啟動服務才會生效。
- **注意事項與禁區**：只動 `frontend/`；main 的工作目錄當時有他人未提交的 `backend/` 修改，未碰。`frontend/static/aui/` 不要手改，改套件來源再整包複製。
- **回復點／回滾**：未部署；要退回就換回 main 的 `frontend/`。
- **更新**：2026-11-24，Claude（UI 套件導入）。

