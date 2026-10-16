# CLAUDE.md — PEditor 共同規則

本檔是 Claude Code 在本 repo 的工作規則。每段（P0–P8）開工前必讀：
`docs/spec.md`（規格 v1.1，含 §9 共同提示詞與各段啟動指令）、`docs/adr/`、
`tests/fixtures/manifest.csv`、`docs/traceability.md`、上一段 `reports/Pn/report.md`。

## 專案一句話

離線 PDF 文字編輯器（Python + PySide6 + PyMuPDF/pikepdf），AGPL-3.0 公開。
PDF 一律視為不可信輸入；解析只在 worker 子行程進行（ADR-0004）。

## 工作流程 S1–S5（每段固定）

1. **S1 確認輸入**：讀 spec、ADR、manifest、上段報告；缺漏先列出再問，不自行假設。
2. **S2 拆解任務**：列出「需求 ID → test ID → 修改檔案」，工程師確認後才實作。
3. **S3 產出第一版**：一段一個分支（`pN-<主題>`），只改該段範圍內的檔案。
4. **S4 自我檢查**：本機跑 `uv run ruff check . && uv run ruff format --check . && uv run pytest`；
   推上 GitHub 由 CI 補跑 Windows x64 / macOS arm64。
5. **S5 回報不確定性**：依 `reports/TEMPLATE.md`（spec §11）產出 `reports/Pn/report.md`；
   未執行項目標 `NOT RUN` 並寫原因；不得把 CI 證據寫成實機證據；未完成標 `BLOCKED`，不寫已完成。

關卡報告由另一個未參與實作的子代理人核對（真修改證據與報告一致）後，才請工程師合併。

## 常用指令

```bash
uv sync --locked --all-groups          # 安裝鎖定相依
uv run python scripts/fetch_fonts.py   # 下載 fixture 字型（鎖定 commit + SHA-256）
uv run pytest                          # 全部測試（自動 offscreen）
uv run python scripts/gen_fixtures.py  # 重產合成 fixture 到 tests/fixtures/files/ 並更新 manifest hash
uv run python packaging/smoke_build.py # PyInstaller smoke build + 執行 --smoke
powershell -ExecutionPolicy Bypass -File scripts\p0_windows_check.ps1   # Windows 實機一鍵驗證
bash scripts/p0_macos_check.sh         # macOS 實機一鍵驗證
uv run peditor                         # 啟動 app
```

## 程式風格（karpathy-guidelines）

- 只做該段需求；不預先抽象、不加未被要求的設定項。
- diff 只含必要變更；不順手重構無關程式。
- 有不確定處先說出假設，不猜。
- 每個行為變更都要有對應 test ID（記入 `docs/traceability.md`）。

## 禁止事項（含 spec §9）

- 禁止用白框、註解覆蓋、整頁點陣化冒充原內容編輯；禁止把擷取 bbox 當成內容定位。
- 禁止改測試預期掩蓋失敗；禁止放寬支援範圍；禁止使用未核對的套件 API（查官方文件，以鎖定版本為準）。
- 不得自動上傳 PDF、安裝 telemetry、加入線上服務。

- 不在主行程（UI 行程）以 PyMuPDF／pikepdf 開啟使用者 PDF；一律經 worker（P1 起）。
- 產品程式碼（`src/`）不得匯入任何網路模組（`tests/security/test_offline_guard.py` 會擋）。
- 不提交真實公文、個資或非 OFL／非可再散布字型的 fixture；盲測樣本（B01–B12）不進 repo。
- 日誌與錯誤訊息不得包含文件原文或完整檔案路徑。
- 不升級相依版本、不改 `tool.uv.exclude-newer`，除非有對應 ADR 並跑完整 fixture 回歸。
- 重產 fixture 後 hash 若改變，須說明原因（相依升級或產生器修改）並在報告列出。
- 涉及核心語義、授權或支援範圍改變時，先提出 ADR 待人工確認。
- 不跳過、停用或隔離測試來讓 CI 變綠。
- 不在 commit、程式碼或文件中寫入密碼、金鑰、權杖。

## 技能使用時點

| 技能 | 用途 | 時點 |
| --- | --- | --- |
| defending-code-reference-harness `/threat-model` | 維護 `THREAT_MODEL.md` | P0 建立；架構變更時更新 |
| 同上 `/vuln-scan`、`/triage` | 掃描 worker、parser、IPC、儲存交易 | P1、P2、P3、P7 結束前 |
| 同上 `/patch` | 對確認問題產生修補並跑回歸 | 有發現時 |
| karpathy-guidelines | 限制過度設計 | 全程 |
| anthropics/skills PDF skill | 僅參考擷取流程，不複製進產品 | P1 |

harness 技能以參考方式使用，複製進 `.claude/` 前須核對其授權（Apache-2.0）並鎖定 commit
（目前參考 `d3bea6b5793b5f3d59a75ebe69a58efa88383145`）。不採用其自動化 pipeline（ADR-0005）。
