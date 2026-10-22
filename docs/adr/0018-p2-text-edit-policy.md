# ADR-0018：P2 文字編輯政策（目標範圍、字寬、溢出、模式 B 字型）

- 狀態：已接受（2026-10-22，工程師於 P2 S1 選定模式 B 字型，S3 確認其餘細節）
- 日期：2026-10-22
- 決策者：工程師
- 需人工確認：否（已確認）

## 背景

P2 的 18 個支援案例中，只有 T07、F01 的目標是整段文字運算子；其餘 15 個是一段運算子內的部分文字
（例如 T01「衛生局」是一整句中的三個字），T08 跨 3 段運算子。P1 的 `text_targets` 以「一個文字顯示運算子」為單位。

替換字寬不同時（例如 F04 `World` → `Earth`、T02「10 月 31 日」→「11 月 5 日」），同一運算子中後續字形的位置
會隨之移動；spec §6 P2 要求處理「不同字寬」，並「替換新字超框一律拒絕，不偷偷縮字」。

模式 B 需要以已包裝的繁中字型重建新文字（ADR-0001、ADR-0008）。

## 決策

### 1. 目標範圍（span target）

- `plan_text_edit` 的目標（**選取範圍**）由 P1 的 `text_targets` 加上字元範圍組成：
  一個或多個**同頁、同一 content stream、同一 Form 路徑、在內容順序中連續**的文字運算子（中間不得夾其他文字運算子），
  以及第一段的起始字元與最後一段的結束字元（以 `text_targets.text` 的字元為單位）。
- span target_id 由各段 target_id 與字元範圍組成，仍含 revision、page_index、content stream、運算子 occurrence、Form 路徑、
  幾何 hash（spec §7）；revision 不符回 `REVISION_CONFLICT`。
- 字元範圍只能落在字形邊界；一個字碼對應多個 Unicode（連字）被切開時回 `UNSUPPORTED_ENCODING`。
- **實際改動範圍**（2026-10-22 工程師確認，因 T08）：EditPlan 先去掉選取文字與新文**相同的開頭與結尾**，
  只改真正不同的字；縮小後的範圍向外擴到字形邊界。新文與選取文字完全相同時回 `INVALID_REQUEST`。
  純插入（例如 T04「三樓」→「三樓第二會議室」）的改動範圍為空，錨定在相同開頭的最後一個字形之後
  （沒有相同開頭時錨定在相同結尾的第一個字形之前）。
- 下列規則套用在**實際改動範圍**，不套用在選取範圍：
  - 只涉及**同一 BT…ET 內相鄰**的文字運算子；否則回 `UNSUPPORTED_LAYOUT`。
  - 涉及的每一段能力都必須是 `support`，否則回傳該段理由碼；選取範圍中未改動的段落只要求能定位（不另判能力）。
  - 標記 PDF 的 MCID 規則（ADR-0017）。
- 例：T08 選取「（02）2720-8889」跨 4 個 BT 與 4 個 MCID，改為「（02）2720-0000」時實際改動只有最後一段的「8889」。
- 模式 B 只重建實際改動的字，因此同一個選取範圍內可能出現原字型與 Noto Sans TC 並存（例如 T04 的「三樓」維持原明體、
  「第二會議室」為黑體）；EditPlan 的 `warnings` 須標示。

### 2. 模式 A 的字寬與位置

- 只改寫目標字元的字碼；目標**之後**、同一 BT 內的字形位置不得移動：以 TJ 位移量補償新舊字寬差。
- 目標本身由原起點開始排列，不置中、不對齊、不縮字、不調字距以塞入框內。
- 新文較短時，原目標尾端到下一個字形之間留白；不自動重排其他文字。
- 只在 TJ 能表達的情況處理：若補償需改到目標以外的運算子（例如中間夾有 `Td`、`Tm`、`'`、`"`），回 `UNSUPPORTED_LAYOUT`。

### 3. 溢出

- 依 manifest／`edit_cases.csv` 的 `editable_region_pt`（呼叫端可給較小的框；EditPlan 記錄實際使用的框）。
- 新文的字形外框（含模式 A 的 TJ 補償後位置、模式 B 的新字型度量）任何一點超出框，回 `TEXT_OVERFLOW`。
- 永不縮小字級、壓縮字寬或換行來避免溢出。

### 4. 模式 B 字型

- P2 一律以 Noto Sans TC（ADR-0008 鎖定版本）重建，不論原文是黑體、明體或拉丁字型。
- 嵌入前以 fontTools 子集化，只含新文用到的字（ADR-0008：MuPDF 無法子集化 CFF OTF）。
- 字級、基線起點、填色與原目標第一個字形相同；EditPlan 的 `font_changes` 記錄原字型名稱與新字型，
  `warnings` 標示「字型已替換，需人工確認版面」（spec §1、§8.2）。
- 明體原文（T04、T06、F07、L05 等）改為黑體屬預期的字型替換，不視為視覺失敗；改動區域外仍須符合 §8.2 門檻。
- 新文含 Noto Sans TC 沒有的字（例如 𠮷）回 `GLYPH_MISSING`，不得顯示方框或改用其他字型。
- P2 之後若要以明體重建明體原文，另立 ADR 更新 ADR-0008。

## 後果

- `core/editplan.py` 定義 span target 與 EditPlan；`worker/edit.py` 實作模式 A、B。
- 測試：`tests/unit/test_edit_plan.py::test_span_target_resolution`（G2-18）、
  `tests/integration/test_edit_text.py::test_following_glyphs_unmoved`（G2-19）、`::test_overflow_rejected`（G2-06）。
- G2-04 的 F03、F08 由本 ADR §4 的 `GLYPH_MISSING` 規則判定（ADR-0013）。
