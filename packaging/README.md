# packaging

| 檔案 | 用途 | 段落 |
| --- | --- | --- |
| `smoke_build.py` | PyInstaller onedir 打包並執行 `--smoke`，證明相依可凍結並在目標平台啟動（G0-04） | P0 |
| `pyinstaller_entry.py` | PyInstaller 進入點 | P0 |
| `sbom/sbom-runtime.cdx.json` | 執行期相依 SBOM 草案（CycloneDX 1.5） | P0 草案；P8 正式 |

重新產生 SBOM（相依變更後）：

```bash
uv export --format cyclonedx1.5 --no-dev --frozen --preview > packaging/sbom/sbom-runtime.cdx.json
```

正式安裝包（Windows 安裝程式、macOS app／DMG）、離線安裝說明、簽章與 notarization 於 P8 處理（spec §6 P8）。
各平台須原生建置，不從單一 OS 跨平台產出。
