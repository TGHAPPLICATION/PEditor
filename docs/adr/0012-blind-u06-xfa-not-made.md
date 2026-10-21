# ADR-0012：盲測 U06（XFA）無法製作，盲測數接受 11 份

- 狀態：已接受（2026-10-21，工程師確認）
- 日期：2026-10-21
- 決策者：工程師
- 需人工確認：否（已確認）

## 背景

spec §5 要求保留至少 12 份盲測，G8 驗收寫明「61 fixture 與 12 盲測結果」。manifest 的 12 份盲測為
T10–T12、F09–F10、L08、I08、B07–B08、U06、S07–S08。

U06 是 XFA 表單（預期 reject `UNSUPPORTED_FEATURE`）。XFA 只能用 Adobe LiveCycle Designer／AEM Forms Designer 製作；
Word、LibreOffice、瀏覽器與一般 Acrobat「準備表單」都做不出。manual-steps §5.12 事先允許「做不到請標記無法製作」。

2026-10-21 保管人交付 hash 清冊（11 份盲測＋S07 對照原檔），並確認單位內沒有可建立 XFA 的軟體，U06 無法製作。
repo 內也沒有任何 XFA 樣本（U05 是 PDF/A，同為 `UNSUPPORTED_FEATURE`）。

## 選項

1. **接受 11 份盲測**：U06 標為無法製作，不另補。不需再請保管人製作；G8 盲測數量由 12 降為 11。
2. 請保管人改做另一類盲測補足 12 份：符合 spec 數量，但需重新製作並重交清冊；XFA 仍無樣本。
3. 由工程師或 AI 以腳本產生 XFA 作為盲測：XFA 結構由開發方設計，失去盲測意義，不採用。

## 決策

採用選項 1：盲測以 11 份為準，U06 標為無法製作。

## 後果

- G0-08、G8-03 的盲測數量以 11 份計（T10–T12、F09–F10、L08、I08、B07–B08、S07–S08）；manifest U06 列保留
  （`blind=true`、`status=pending`），notes 註明無法製作。`test_at_least_12_blind_fixtures_kept_offline` 檢查的是
  manifest 結構（12 列盲測、檔案不在 repo），不因此修改。
- XFA 拒絕路徑沒有盲測，也沒有人工樣本。P1 能力判定仍須偵測 `/AcroForm /XFA` 並拒絕 `UNSUPPORTED_FEATURE`；
  其測試以腳本產生的合成 XFA 檔（非盲測、不計入 61 份 manifest）覆蓋，最晚於 P7 安全強化時補上。
- P8 盲測報告須寫明「11 份，U06 無法製作（本 ADR）」，不得寫成 12 份。
- 若日後取得 XFA 製作工具，可由保管人補做 U06、重交整份清冊，屆時另以 ADR 取代本決策。
