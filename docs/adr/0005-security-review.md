# ADR-0005：安全審查流程

- 狀態：已接受
- 日期：2026-10-12
- 需人工確認：否

## 背景

計畫書指定使用 anthropics/defending-code-reference-harness 的互動技能。該 harness 的自動化
pipeline 以 C/C++ 記憶體漏洞為目標，需 Docker、gVisor 與持續計費的 API 金鑰；
該 repo 註明不再維護。

## 決策

- 使用其互動技能：`/threat-model`（P0）、`/vuln-scan` + `/triage`（P1、P2、P3、P7 結束前）、
  `/patch`（有發現時）。
- 不跑自動化 pipeline（成本高、對 Python 桌面程式效益低）。
- 參考版本鎖定 commit `d3bea6b5793b5f3d59a75ebe69a58efa88383145`（Apache-2.0）；
  若要複製技能進 `.claude/`，須保留授權聲明並記錄 commit。
- 相依供應鏈：`uv.lock` 雜湊鎖定、`tool.uv.exclude-newer` 冷卻期、GitHub Actions 以 commit SHA 鎖定；
  repo 開啟 secret scanning、Dependabot alerts（人工於 GitHub 設定）。
- Microsoft SkillOpt 初版不導入。

## 後果

- 每段報告須附 vuln-scan／triage 結果摘要或 `NOT RUN` 理由。
- `THREAT_MODEL.md` 於架構變更（如 IPC、儲存交易）時更新。
