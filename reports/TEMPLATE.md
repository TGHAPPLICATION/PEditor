# Pn 關卡報告：<主題>

> 依 spec §11 範本。未執行項目標 `NOT RUN`，不得以推測填 PASS；CI 證據與實機證據分開記錄。

## 1. 階段／commit／日期

- 階段：Pn　commit：`<sha>`　日期：YYYY-MM-DD
- 撰寫：Claude Code；審查：<工程師>；獨立核對：<子代理人／日期>

## 2. 環境

| 環境 | OS／架構 | 硬體 | Python／套件／字型版本 |
| --- | --- | --- | --- |
| Windows 實機 | | | |
| macOS 實機 | | | |
| CI windows | | | |
| CI macos | | | |

## 3. 需求 → test ID → fixture／hash → 結果

| 需求 ID | test ID | fixture（hash 前 12 碼） | 環境 | 結果 |
| --- | --- | --- | --- | --- |
| Gn-01 | | | | PASS／FAIL／NOT RUN |

## 4. 執行命令、exit code、測試數

```
<命令>  → exit <code>，<N> passed
```

## 5. 真修改證據

<證據路徑、雙引擎擷取結果、視覺差異；本段無編輯時寫「不適用」>

## 6. 資料完整性與資源／出站紀錄

## 7. 限制、阻擋、未測項目

## 8. 安全審查

<vuln-scan／triage 摘要或 NOT RUN 理由；THREAT_MODEL.md 是否更新>

## 9. 不確定性與人工確認項目

| # | 內容 | 影響 | 需誰確認 |
| --- | --- | --- | --- |

## 10. 關卡結果

- 關卡結果：PASS／BLOCKED
- 下一段可開始：是／否（條件）

## 11. 獨立核對紀錄
