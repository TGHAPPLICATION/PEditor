# PEditor — 離線 PDF 文字編輯器

在不連網的環境中，直接修改 PDF 內既有文字（含繁體中文），並保留原排版。

> 狀態：**P2（文字修改 CLI POC）進行中**。可用 CLI 分析與替換文字；桌面介面尚未提供編輯（P4）。進度見 `reports/`。

## 使用（CLI）

```bash
uv run peditor analyze X.pdf --out D                       # 只讀分析：能力報告與頁面 PNG
uv run peditor edit-text X.pdf --find 原文 --new 新文 --out D  # 替換文字，另存 D/output.pdf
```

`edit-text` 另輸出 `plan.json`（EditPlan：模式、字型替換、影響資源）與 `validation.json`（結構檢查、內容差異）。
不會覆寫既有輸出檔，也不修改原檔。

## 限制（請先閱讀）

- **不是機密抹除工具**：只移除指定位置的文字顯示內容。舊文字仍可能存在於 metadata、註解、附件、書籤、
  其他頁面或字型資料中；本工具不提供、也不宣稱鑑識級遮蔽（spec §8.1）。
- 原字型缺字時改用 Noto Sans TC 重建該段文字（模式 B），字型會與原文不同，需人工確認版面（ADR-0018）。
  Noto Sans TC 也沒有的字（例如 𠮷）一律拒絕，不顯示方框。
- 新文字超出可改動區域一律拒絕，不自動縮字或重排。
- 不支援的文件或物件（加密、簽章、XFA、直排、旋轉文字、Type3、無可靠 ToUnicode 等）會回傳理由碼並拒絕編輯。
- 開發階段的模式 B 字型由環境變數 `PEDITOR_MODE_B_FONT` 指定（測試預設為 `tests/fixtures/fonts/`）；
  正式安裝包於 P8 內附。

## 開發

需求：[uv](https://docs.astral.sh/uv/)、Python 3.13（uv 會自動處理）。

```bash
uv sync --locked --all-groups
uv run python scripts/fetch_fonts.py   # fixture 字型（約 22 MB，不入 repo）
uv run pytest
uv run peditor
```

Linux 開發機若出現 `libEGL.so.1` 找不到，需安裝 `libegl1 libgl1 libxkbcommon0 libfontconfig1`。
（目標平台為 Windows x64 與 macOS arm64，Linux 僅供開發。）

## 文件

- 規格：`docs/spec.md`；決策：`docs/adr/`；追溯表：`docs/traceability.md`
- 測試樣本：`tests/fixtures/manifest.csv`（61 份；repo 內樣本在 `tests/fixtures/files/`）；編輯案例：`tests/fixtures/edit_cases.csv`
- 打包與 SBOM：`packaging/`
- 威脅模型：`THREAT_MODEL.md`
- Claude Code 規則：`CLAUDE.md`

## 授權

AGPL-3.0-only（見 `LICENSE`）。第三方元件見 `THIRD_PARTY_NOTICES.md`。
