import csv
import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"

# 測試一律以 offscreen 執行，不需實體顯示器（CI 與本機一致）
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def gen_fixtures():
    path = ROOT / "scripts" / "gen_fixtures.py"
    spec = importlib.util.spec_from_file_location("gen_fixtures", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["gen_fixtures"] = module  # dataclass 需要模組已註冊
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def manifest_rows():
    with (FIXTURES / "manifest.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture(scope="session")
def available_rows(manifest_rows):
    return [r for r in manifest_rows if r["status"] == "available"]
