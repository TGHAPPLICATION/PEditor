# .claude/skills 第三方來源

以下檔案逐字複製自 [anthropics/defending-code-reference-harness](https://github.com/anthropics/defending-code-reference-harness)，
commit `d3bea6b5793b5f3d59a75ebe69a58efa88383145`（2026-08-06），授權 Apache-2.0（全文見
`LICENSE-defending-code-reference-harness`）。依 ADR-0005 只使用互動技能，不使用其自動化 pipeline。

| 本 repo 路徑 | 來源路徑 | 修改 |
| --- | --- | --- |
| `vuln-scan/SKILL.md` | `.claude/skills/vuln-scan/SKILL.md` | 無 |
| `triage/SKILL.md` | `.claude/skills/triage/SKILL.md` | 無 |
| `triage/README.md` | `.claude/skills/triage/README.md` | 無 |
| `_lib/checkpoint.py` | `.claude/skills/_lib/checkpoint.py` | 無 |

未複製：`triage/fixtures/`（canary 範例，引用本 repo 不存在的 `targets/canary`）與其他技能。

本機注意：Windows 的 `python3` 可能是 Microsoft Store 替身程式；`triage` 的 checkpoint 指令改以
`uv run python .claude/skills/_lib/checkpoint.py …` 執行（同一支腳本，只在目前資料夾內寫檔，不連網）。
