from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "archive"


@pytest.fixture(scope="session")
def archive():
    return ARCHIVE
