# ADR-0009：擴大 P5 圖片替換支援範圍（SMask 透明遮罩、簡單剪裁）

- 狀態：已接受（2026-10-16，工程師確認）
- 日期：2026-10-16
- 決策者：工程師
- 需人工確認：否（已確認）

## 背景

`docs/spec.md` §6 P5（原文第 125 行）驗收標準為「拒絕非支援遮罩／剪裁」。`tests/fixtures/manifest.csv`
中 I04（含 SMask 透明背景的 PNG）與 I07（裁剪後的圖片）原列為待人工確認是否支援：

| fixture | 原預期 | 待決事項 |
| --- | --- | --- |
| I04 | support（待確認） | 含 SMask 的 PNG，P5 要不要支援替換？ |
| I07 | reject UNSUPPORTED_LAYOUT（待確認） | 經剪裁的圖片，P5 要不要支援？ |

兩者在一般公文／簡報中都很常見（去背 Logo／印章、插入照片後隨手裁剪），若一律拒絕會明顯縮小 P5
圖片替換功能的實用覆蓋率。

## 選項

1. **維持 spec 原預設（兩者皆 reject）**：最簡單、風險最低，但大幅降低真實文件的可用覆蓋率。
2. **兩者皆改 support，不補測試樣本**：覆蓋率最大化，但會讓 G5-04「拒絕非支援遮罩／剪裁」這條驗收
   標準在 60 份 fixture 中失去任何對應的 reject 樣本，P5 無法用 committed fixture 驗證該行為。
3. **兩者皆改 support，另補一份更難的 reject 樣本**：覆蓋率提升，同時保留 G5-04 的可測試性；代價是
   需新增 fixture、並更動 P0 已鎖定的「固定 60 份」計數。

## 決策

採用選項 3：

- **I04**：確認為 `support`。SMask 透明遮罩圖片可替換；新圖與原圖透明通道／尺寸不符時的處理原則
  （例如要求尺寸相符、或由 P5 重新產生遮罩）留待 P5 設計階段決定，不在本 ADR 範圍內。
- **I07**：由 `reject UNSUPPORTED_LAYOUT` 改為 `support`。裁剪若只是矩陣層級的仿射變換（不含
  非矩形 clip path），底層影像 XObject 替換後既有裁剪變換會自動套用，視為支援範圍。
- **新增 I09**：`reject UNSUPPORTED_LAYOUT`，代表「非矩形 clip path」等仍應拒絕的較複雜遮罩／剪裁
  案例，使 G5-04 保留具體可驗證的 fixture。

## 後果

- `tests/fixtures/manifest.csv`：I04 notes 更新去除待確認字樣；I07 `expected` 改 `support`、
  `reason_code` 清空；新增 I09 列（`status=pending`，待人工以 LibreOffice 製作：插入圖片後裁剪為
  非矩形圖形／自訂形狀）。
- `docs/spec.md`：第 68、87、96、144、199、215 行「60 份／60 fixture」改為「61 份／61 fixture」；
  第 74 行「I 圖片 | 8」改為「I 圖片 | 9」；第 125 行驗收敘述由籠統的「拒絕非支援遮罩／剪裁」改為
  具體指向「非矩形裁剪路徑等複雜案例」，並註記簡單透明遮罩與矩陣層級裁剪屬支援範圍（見本 ADR）。
- `tests/unit/test_manifest.py`：`GROUP_COUNTS["I 圖片"]` 由 8 改 9；
  `test_manifest_has_60_fixtures_in_spec_groups` 更名為
  `test_manifest_has_61_fixtures_in_spec_groups`，斷言的 60 改 61。
- `docs/traceability.md`：G0-07 群組數敘述（I8→I9）與對應測試名稱；G5-01 支援案例 fixture 範圍納入
  I07；G5-04 的範例 fixture 由「I04、I07」改為「I09」。
- `reports/P0/manual-steps.md`：§2 待決事項標記為已決定；§4 人工 fixture 總數由 23 增為 24，§4.4
  新增 I09 的製作說明。
- `reports/P0/report.md`：§9 不確定性表新增本 ADR 決議紀錄，U5（I04／I07 待決）標記已解決。
- I09 在補做（人工以 LibreOffice 製作並登記）前，`tests/unit/test_manifest.py` 的群組計數與總數
  斷言會先失敗；須與 I09 fixture 的登記同批提交，或在過渡期間先同步調整測試與 manifest 後再補 PDF。
