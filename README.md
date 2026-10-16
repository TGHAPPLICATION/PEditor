# PEditor — 離線 PDF 文字編輯器

在不連網的環境中，直接修改 PDF 內既有文字（含繁體中文），並保留原排版。

> 狀態：**P0（規格、環境與資料集）**。目前只有空白視窗，尚無編輯功能。進度見 `reports/`。

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
- 測試樣本：`tests/fixtures/manifest.csv`（60 份；合成樣本在 `tests/fixtures/files/`）
- 打包與 SBOM：`packaging/`
- 威脅模型：`THREAT_MODEL.md`
- Claude Code 規則：`CLAUDE.md`

## 授權

AGPL-3.0-only（見 `LICENSE`）。第三方元件見 `THIRD_PARTY_NOTICES.md`。
