"""The compatibility mode must reproduce every archived v3 result byte for byte."""
import subprocess
import sys
from pathlib import Path

import pytest

from shieldeval.legacy import legacy_evaluate, legacy_outfreqs

ARCHIVED = sorted((Path(__file__).resolve().parents[1] / "archive" / "results_v3").glob("*.res"))


@pytest.mark.parametrize("res", ARCHIVED, ids=[p.stem for p in ARCHIVED])
def test_byte_identical(res, archive):
    dat = archive / "raw" / (res.stem + ".dat")
    assert legacy_evaluate(str(dat)).text == res.read_text()


def test_original_script_still_agrees(archive, tmp_path):
    """The archived legacy script itself (kept read-only) produces the same bytes - guards the archive."""
    script = Path(__file__).resolve().parents[1] / "legacy" / "shieldeval_v3.py"
    dat = archive / "raw" / "S01_single_braid.dat"
    out = subprocess.run([sys.executable, str(script), str(dat)], capture_output=True, text=True, check=True).stdout
    assert out == (archive / "results_v3" / "S01_single_braid.res").read_text()


def test_outfreqs_quirk():
    fo = legacy_outfreqs()
    assert len(fo) == 61 and fo[0] == 1e6 and fo[-1] == 1e9 and fo[1] == 1.12e6
