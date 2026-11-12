"""P8 發布建置（spec §6 P8、ADR-0025）：PyInstaller onedir（視窗程式）＋模式 B 字型與授權，
建置後以打包結果自我檢查，再產生平台安裝包。

- Windows：`dist/PEditor/`，再以 Inno Setup（`packaging/windows/peditor.iss`）產生安裝程式。
- macOS：`dist/PEditor.app`，再以 `hdiutil` 產生 DMG。
- 自我檢查（打包結果，不用開發環境的 Python）：`--smoke` 啟動主視窗；`edit-text` 以 T01（模式 A）
  與 F02（模式 B，需要打包進去的字型）改字並另存——兩者都經由打包後的 worker 子命令與 Job Object。
- 輸出 `build/release/SHA256SUMS.txt`（安裝包與 onedir 內每個檔案的 SHA-256）。
- 安裝目錄附 `licenses/`：各執行期套件 wheel 內的授權檔、PyInstaller bootloader 授權、
  `packaging/licenses/`（Qt 的 LGPL／GPL 全文、MuPDF 第三方、CPython）（P8 授權核對 F1）。

用法：uv run python packaging/build_release.py [--no-installer]
先執行 `uv run python scripts/fetch_fonts.py`（字型不入庫，ADR-0008）。
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "release"
DIST, WORK = OUT / "dist", OUT / "work"
FONTS = ROOT / "tests" / "fixtures" / "fonts"
FIXTURES = ROOT / "tests" / "fixtures" / "files"
FONT = "NotoSansTC-Regular.otf"
FONT_LICENSE = "LICENSE-NotoSansCJK.txt"
DOCS = ["LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md"]
# 隨安裝包散布的套件（uv export --no-dev）與 PyInstaller（bootloader 編入執行檔）
LICENSED = ["pymupdf", "pikepdf", "pyside6-essentials", "shiboken6", "pillow", "lxml", "packaging",
            "fonttools", "pyinstaller"]  # fmt: skip
EXTRA_LICENSES = ROOT / "packaging" / "licenses"
# 安裝包必須附上的授權檔（自我檢查；相對 licenses/）
REQUIRED_LICENSES = [
    "qt/LGPL-3.0-only.txt",
    "qt/GPL-3.0-only.txt",
    "python/PSF-2.0.txt",
    "mupdf-thirdparty/freetype--FTL.TXT",
    "mupdf-thirdparty/libjpeg--README",
    "pikepdf/LICENSE.txt",
    "pikepdf/third-party-licenses/openssl.txt",
    "pikepdf/third-party-licenses/libjpeg-turbo-README.ijg.txt",
    "pillow/LICENSE",
    "lxml/LICENSES.txt",
    "pyinstaller/COPYING.txt",
    "pymupdf/COPYING",
]
MARKER = "PEDITOR_SMOKE_OK"
BUNDLE_ID = "io.github.tghapplication.peditor"


def _version() -> str:
    sys.path.insert(0, str(ROOT / "src"))
    from peditor import __version__

    return __version__


def _commit() -> str:
    """建置來源 commit（CI 用 GITHUB_SHA，本機用 git）；寫進包內 resources/BUILD 供視窗標題顯示。"""
    sha = os.environ.get("GITHUB_SHA", "")
    if not sha:
        done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=False)  # fmt: skip
        sha = done.stdout.strip() if done.returncode == 0 else ""
    return sha[:7] if sha.isalnum() else ""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def collect_licenses(dest: Path) -> list[str]:
    """把隨包元件的授權檔複製到 dest（P8 授權核對 F1）；回傳相對路徑清單（排序）。

    wheel 的授權檔在 dist-info 的 `licenses/` 下（PEP 639），舊式 wheel 則是 dist-info 內的
    LICENSE／COPYING／NOTICE 檔；PyInstaller 打包時不會帶入這些檔案。
    """
    dest.mkdir(parents=True, exist_ok=True)
    for name in LICENSED:
        dist = importlib.metadata.distribution(name)
        for item in dist.files or []:
            parts = item.parts
            if not parts or not parts[0].endswith(".dist-info"):
                continue
            if "licenses" in parts:
                rel = Path(*parts[parts.index("licenses") + 1 :])
            elif parts[-1].upper().startswith(("LICENSE", "COPYING", "NOTICE")):
                rel = Path(parts[-1])
            else:
                continue
            target = dest / name / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item.locate(), target)
    shutil.copytree(EXTRA_LICENSES, dest, dirs_exist_ok=True)
    version = f"python{sys.version_info[0]}.{sys.version_info[1]}"
    base = Path(sys.base_prefix)
    for candidate in (base / "LICENSE.txt", base / "lib" / version / "LICENSE.txt"):
        if candidate.is_file():  # CPython 完整授權（含其內嵌元件）；找不到時只有 PSF-2.0 全文
            shutil.copy2(candidate, dest / "python" / "LICENSE.txt")
            break
    found = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
    missing = [r for r in REQUIRED_LICENSES if r not in found]
    if missing:
        raise SystemExit(f"缺少授權檔：{missing}")
    return found


def build() -> Path:
    """PyInstaller onedir；回傳打包後執行檔路徑。"""
    font = FONTS / FONT
    if not font.is_file():
        raise SystemExit("缺少模式 B 字型：先執行 uv run python scripts/fetch_fonts.py")
    sep = os.pathsep
    data = [
        f"{font}{sep}peditor/resources/fonts",
        f"{FONTS / FONT_LICENSE}{sep}peditor/resources/fonts",
    ]
    if commit := _commit():
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "BUILD").write_text(commit, encoding="ascii")
        data.append(f"{OUT / 'BUILD'}{sep}peditor/resources")
    command = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onedir", "--windowed",
        "--name", "PEditor",
        "--distpath", str(DIST), "--workpath", str(WORK), "--specpath", str(WORK),
        "--paths", str(ROOT / "src"),
        "--osx-bundle-identifier", BUNDLE_ID,
    ]  # fmt: skip
    for item in data:
        command += ["--add-data", item]
    command.append(str(ROOT / "packaging" / "pyinstaller_entry.py"))
    subprocess.run(command, check=True)
    if sys.platform == "darwin":
        exe = DIST / "PEditor.app" / "Contents" / "MacOS" / "PEditor"
        docs_dir = DIST / "PEditor.app" / "Contents" / "Resources"
    else:
        exe = DIST / "PEditor" / ("PEditor.exe" if os.name == "nt" else "PEditor")
        docs_dir = DIST / "PEditor"
    for name in DOCS:
        shutil.copy2(ROOT / name, docs_dir / name)
    collect_licenses(docs_dir / "licenses")
    return exe


def self_check(exe: Path) -> dict:
    """以打包結果自我檢查；任何一項失敗即 SystemExit。"""
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    env.pop("PEDITOR_MODE_B_FONT", None)  # 只能用打包進去的字型
    smoke = subprocess.run([str(exe), "--smoke"], capture_output=True, text=True, env=env,
                           timeout=180, check=False)  # fmt: skip
    if smoke.returncode != 0 or MARKER not in smoke.stdout:
        raise SystemExit(f"--smoke 失敗（exit {smoke.returncode}）")
    results = {"smoke": "ok"}
    for fid, find, new, mode in (("T01", "衛生局", "測試局", "A"), ("F02", "醫事", "藥事", "B")):
        out = OUT / "selfcheck" / fid
        shutil.rmtree(out, ignore_errors=True)
        run = subprocess.run(
            [str(exe), "edit-text", str(FIXTURES / f"{fid}.pdf"), "--find", find, "--new", new,
             "--out", str(out)],
            capture_output=True, text=True, env=env, timeout=300, check=False,
        )  # fmt: skip
        plan_path = out / "plan.json"
        if run.returncode != 0 or not (out / "output.pdf").is_file() or not plan_path.is_file():
            raise SystemExit(f"edit-text {fid} 失敗（exit {run.returncode}）")
        got = json.loads(plan_path.read_text(encoding="utf-8")).get("mode")
        if got != mode:
            raise SystemExit(f"edit-text {fid} 模式 {got}，預期 {mode}")
        results[fid] = f"mode {mode}"
    return results


def installer(version: str) -> Path:
    if sys.platform == "darwin":
        dmg = OUT / f"PEditor-{version}-macos-arm64.dmg"
        dmg.unlink(missing_ok=True)
        subprocess.run(["hdiutil", "create", "-volname", "PEditor", "-srcfolder",
                        str(DIST / "PEditor.app"), "-ov", "-format", "UDZO", str(dmg)],
                       check=True)  # fmt: skip
        return dmg
    iscc = shutil.which("iscc") or r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if not Path(iscc).is_file() and not shutil.which("iscc"):
        raise SystemExit("找不到 Inno Setup（ISCC.exe）；ADR-0025")
    subprocess.run([iscc, f"/DAppVersion={version}", f"/DSourceDir={DIST / 'PEditor'}",
                    f"/DOutputDir={OUT}", str(ROOT / "packaging" / "windows" / "peditor.iss")],
                   check=True)  # fmt: skip
    return OUT / f"PEditor-{version}-windows-x64-setup.exe"


def checksums(package: Path | None) -> Path:
    base = DIST / ("PEditor.app" if sys.platform == "darwin" else "PEditor")
    lines = []
    if package is not None:
        lines.append(f"{_sha256(package)}  {package.name}")
    for path in sorted(p for p in base.rglob("*") if p.is_file() and not p.is_symlink()):
        lines.append(f"{_sha256(path)}  {path.relative_to(DIST).as_posix()}")
    target = OUT / "SHA256SUMS.txt"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def main(argv: list[str]) -> int:
    version = _version()
    exe = build()
    results = self_check(exe)
    package = None if "--no-installer" in argv else installer(version)
    sums = checksums(package)
    base = DIST / ("PEditor.app" if sys.platform == "darwin" else "PEditor")
    size = sum(f.stat().st_size for f in base.rglob("*") if f.is_file() and not f.is_symlink())
    summary = {"version": version, "commit": _commit(), "platform": sys.platform,
               "self_check": results,
               "onedir_mib": round(size / 1_048_576, 1),
               "package": package.name if package else None,
               "package_sha256": _sha256(package) if package else None}  # fmt: skip
    (OUT / "release.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                      encoding="utf-8")  # fmt: skip
    print(json.dumps(summary, ensure_ascii=False))
    print(f"checksums: {sums.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
