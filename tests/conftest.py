import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# 測試一律以 offscreen 執行，不需實體顯示器（CI 與本機一致）
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _load_gen_fixtures():
    spec = importlib.util.spec_from_file_location(
        "gen_fixtures", ROOT / "scripts" / "gen_fixtures.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def gen_fixtures():
    return _load_gen_fixtures()


@pytest.fixture(scope="session")
def generated_dir(tmp_path_factory, gen_fixtures):
    out = tmp_path_factory.mktemp("fixtures")
    gen_fixtures.generate(out)
    return out
