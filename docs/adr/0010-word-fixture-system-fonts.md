# ADR-0010：Word 人工 fixture 使用 Windows 11 內建 Noto TC 可變字型

- 狀態：已接受（2026-10-19，工程師確認）
- 日期：2026-10-19
- 決策者：工程師
- 需人工確認：否（已確認）

## 背景

ADR-0008 鎖定 fixture 字型為 `NotoSansTC-Regular.otf`（noto-cjk@f8d1575，CFF）與
`NotoSerifTC-VF.ttf`（google/fonts@bd8f81d），並以 SHA-256 驗證。`reports/P0/manual-steps.md` §4.1
要求人工製作前安裝這兩個字型。

2026-10-19 在製作機（Windows 11 Pro 10.0.26200、Word 2021 16.0.14334）製作 T05 時發現：

| 檔案 | 來源 | 版本 | SHA-256 |
| --- | --- | --- | --- |
| `C:\Windows\Fonts\NotoSansTC-VF.ttf` | Windows 內建（擁有者 TrustedInstaller） | 2.04 | `c6481c5d93420aeac11087367dae56ae7492eb1989ce42f4ca5d5aa5e2db3116` |
| `C:\Windows\Fonts\NotoSerifTC-VF.ttf` | Windows 內建（擁有者 TrustedInstaller） | 2.02 | `c8b7df78de02c2c35875de707d1d336762fd4db8864a66e249940879fb6859d8` |

兩者 family 名稱與 ADR-0008 的字型相同（「Noto Sans TC」「Noto Serif TC」）。即使另以目前使用者安裝
ADR-0008 鎖定版，Word 仍選用系統內建版：T05 匯出的 PDF 嵌入 `BCDEEE+Noto-Sans-TC`（FontFile2，
含 `fvar`／`gvar`，版本 2.04），未經 instancing，PDF 檢視器以預設 instance（Thin）呈現。
系統字型屬作業系統元件，不宜移除。

## 選項

1. **接受 Windows 內建字型**，記錄版本與 hash。
2. 以 fontTools 將 ADR-0008 字型改 family 名稱後安裝，讓 Word 可選用；嵌入名稱與 hash 仍與 ADR-0008 不同。
3. Word 系列 fixture 改在沒有內建 Noto 的電腦製作。

## 決策

採用選項 1：Word 製作的人工 fixture（T05、T06、T09、F06、L04、L07、B03、B05、I06）字型來源為
Windows 11 內建 Noto Sans TC／Noto Serif TC 可變字型（OFL-1.1）。這是 Windows 11 使用者以 Word
實際會產出的 PDF，並多涵蓋「嵌入未 instancing 的可變 TrueType」這種真實樣態。

- 每份 fixture 的 `manifest.csv` notes 註明「Win11 內建 VF（ADR-0010）」。
- ADR-0008 的鎖定字型仍用於程式產生的 fixture 與模式 B 重建字型，不受影響。
- LibreOffice 系列製作時若同樣選到內建字型，另行確認後再擴大本 ADR 範圍。

## 後果

- 嵌入字型的授權仍為 OFL-1.1，可隨 repo 散布；來源以本 ADR 的版本與 SHA-256 追溯（G0-17）。
- P1 擷取與 P2 模式 B 須能處理嵌入的可變 TrueType（含 `gvar`），並以 PDF 實際呈現（預設 instance）
  為準，不得依 Word 畫面上的字重判斷。
- Windows 更新可能替換內建字型；後續製作時若 hash 改變，須在 notes 記錄新版本。
