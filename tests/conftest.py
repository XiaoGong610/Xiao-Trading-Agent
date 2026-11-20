"""Shared helpers: load scripts with hyphenated names as modules."""
import importlib.util
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def load_script(filename, name=None):
    spec = importlib.util.spec_from_file_location(name or filename.replace("-", "_")[:-3], SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def ccb():
    return load_script("cc-backtest.py")


@pytest.fixture(scope="session")
def ccc():
    return load_script("cc-compare.py")
