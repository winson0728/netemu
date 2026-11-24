# 交接檔（handoff.md）

> 任何 Agent 接手前先讀；收工、每完成一段、回報負責人前更新。

## 本分支（claude/aplus-manual-20261122）交接

> 本段給接手本分支的 Agent；下方原有的專案交接內容保留不動。

- **任務與對應查核點**：A+ 前瞻計畫 11/22 派工：為各子專案產生操作手冊。本 repo 是 NetEmu（tc／netem 網路劣化模擬器），供 doublink-tester 回歸測試模擬 5G／Wi-Fi 線路。
- **目前做到哪**：手冊 v1.0 已完成並推送：定位、Mermaid 架構、功能、安裝部署與回復、Web UI 逐步操作（3 張截圖）、REST API、參數、FAQ、安全、版本紀錄與待確認。
- **分支與最新 commit**：`claude/aplus-manual-20261122`，基底 `origin/main`（`2fba6b4`）；手冊 commit `1431b05`（本段 handoff 為其後一個 commit）。手冊：`docs/操作手冊.md`（新建 v1.0）＋`docs/images/netemu-*.jpg`。已推送到 origin；未合併、未開 PR。本機 worktree：`.claude/worktrees/aplus-manual-20261122/`。
- **已驗證的證據**：2026-11-22：截圖以 `origin/main` 的 `git archive` 在工作站 WSL 以非 root、只聽 127.0.0.1:18081 執行擷取（只看到 `eth0`，未套用任何 tc 規則），擷取後已停止並刪除暫存資料。推送前機密掃描 0 筆。**推送用 winson0728 帳號**（winson392 沒有此 repo 寫入權）。
- **未完成的工作與下一步**：
  1. `NETEMU_VARIATION_SEED`（可重現劣化）只在工作站 `C:\codex-workspace\netemu` 主 checkout 的未提交變更中；是否提交、Lab VM 是否已部署待確認。
  2. Lab VM（192.168.105.115）實際畫面可在 Lab 擷取替換；UI 統一風格完成後重拍。
  3. 核對 Lab VM `/opt/netemu` 的實際版本。
- **注意事項與禁區**：
  - 只在本分支工作；不推 main、不合併、不開 PR（等負責人決定）；不改 AGENTS.md。
  - 手冊不得寫入密碼、金鑰、token（只寫存放位置或取得方式）；推送前做機密掃描。
  - 截圖只在 Lab 或本機擷取；工研院場域（.120、.150、Orin、CM5）與正式環境只能唯讀，不截入帳密與識別資訊。
  - 另有 session 在做全 UI 統一風格與中日英三語，完成後手冊截圖要重拍。
  - 主 checkout 在 main 且有未提交變更（variation seed），**不要動或覆蓋**。
  - Lab NetEmu VM 被每日回歸使用，變更前先公告；`install.sh` 會 `rm -rf /opt/netemu`，先備份資料目錄。
  - 推送需 winson0728 權限：`gh auth switch --user winson0728` 推完再切回 winson392。
- **回復點／回滾方式**：`git revert 1431b05`，或刪除遠端分支。
- **更新時間與更新者**：2026-11-24（台北）｜更新者：manual 子 session（A+ 操作手冊：多網融合與網路測試系列）
- 彙整結果另見 A+ 共用筆記 `DOC-MANUAL-多網融合與網路測試-結果.md`。

---

## 專案交接

（本 repo 先前沒有 handoff.md；專案層級內容待專案負責人補。）
