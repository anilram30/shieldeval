"""
Synthetic archive: raw analyser files in the legacy v3 format, the calibration
run, and a manifest with the shield parameters that generated them.

The archive stands in for the laboratory's archived measurements.  Every
file is produced from :mod:`shieldeval.physics` with a fixed seed, written
exactly as the old analyser export did (frequency in Hz, attenuation in dB
with two decimals, phase in degrees with one decimal), so the legacy tool
and the modern module read the same bytes.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from .physics import BraidShield, Fixture, measured_s21

__all__ = ["SAMPLES", "FIXTURES", "cal_loss_db", "write_dat", "write_cal", "generate_archive"]

FIXTURES = {
    "TUBE500": Fixture("TUBE500", 0.5, z2=100.0),
    "TUBE1000": Fixture("TUBE1000", 1.0, z2=90.0, alpha2_np_per_m_at_1ghz=0.03),
    "LINEINJ": Fixture("LINEINJ", 0.4, z2=150.0, far_end="matched", v2_rel=0.95),
    "CONN": Fixture("CONN", 0.05, z2=80.0, per_metre=False),
}

SAMPLES = {
    "S01_single_braid": dict(shield=BraidShield(5e-3, 0.15e-3, 0.5e-9), fixture="TUBE500"),
    "S02_optimised_braid": dict(shield=BraidShield(4e-3, 0.15e-3, -0.15e-9), fixture="TUBE500"),
    "S03_braid_foil": dict(shield=BraidShield(3e-3, 0.12e-3, 0.03e-9), fixture="TUBE500"),
    "S04_loose_braid": dict(shield=BraidShield(9e-3, 0.20e-3, 2.5e-9), fixture="TUBE500"),
    "S05_thin_strands": dict(shield=BraidShield(12e-3, 0.08e-3, 0.8e-9), fixture="TUBE500"),
    "S06_double_braid": dict(shield=BraidShield(2e-3, 0.15e-3, 0.01e-9), fixture="TUBE500"),
    # measured on the newer fixtures (no v3 result exists for these)
    "N01_single_braid_tube1000": dict(shield=BraidShield(5e-3, 0.15e-3, 0.5e-9), fixture="TUBE1000"),
    "N02_optimised_lineinj": dict(shield=BraidShield(4e-3, 0.15e-3, -0.15e-9), fixture="LINEINJ"),
    "N03_connector": dict(shield=BraidShield(0.4, 0.15e-3, 40e-9), fixture="CONN"),   # 20 mOhm + 2 nH over the 50 mm coupling length
}


def sweep(n: int = 401, fmin: float = 1e5, fmax: float = 1e9) -> np.ndarray:
    return np.logspace(np.log10(fmin), np.log10(fmax), n)


def cal_loss_db(f: np.ndarray) -> np.ndarray:
    """Insertion loss of the connecting cables and adapters between analyser and fixture."""
    return 0.3 + 0.8 * np.sqrt(f / 1e9)


def write_dat(path: Path, f: np.ndarray, s21: np.ndarray, sample: str, fixture: str, lc: float, cal_name: str,
              date: str = "2021-04-12") -> Path:
    a = np.round(-20 * np.log10(np.abs(s21)), 2)
    ph = np.round(np.degrees(np.angle(s21)), 1)
    lines = ["# SHIELDEVAL RAW v3", f"# SAMPLE={sample}", f"# FIXTURE={fixture}", f"# LC={lc}", f"# DATE={date}",
             f"# CAL={cal_name}", "# COLUMNS=f[Hz] a[dB] phase[deg]"]
    for fi, ai, pi in zip(f, a, ph):
        lines.append(f"{fi:.6e} {ai:.2f} {pi:.1f}")
    path.write_text("\n".join(lines) + "\n")
    return path


def write_cal(path: Path, f: np.ndarray, a_db: np.ndarray, date: str = "2021-04-12") -> Path:
    lines = ["# SHIELDEVAL CAL v3", f"# DATE={date}", "# COLUMNS=f[Hz] a[dB]"]
    for fi, ai in zip(f, a_db):
        lines.append(f"{fi:.6e} {ai:.2f}")
    path.write_text("\n".join(lines) + "\n")
    return path


def generate_archive(root: str | Path, n_points: int = 401, seed: int = 100) -> dict:
    root = Path(root)
    raw = root / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    f = sweep(n_points)
    # the calibration run is measured on a coarser grid (101 points) - part of the archive's reality
    f_cal = sweep(101)
    cal_name = "cal_20210412.cal"
    write_cal(raw / cal_name, f_cal, cal_loss_db(f_cal))
    manifest = {"sweep": {"n": n_points, "fmin": 1e5, "fmax": 1e9}, "cal": cal_name, "samples": {}}
    for i, (name, cfg) in enumerate(SAMPLES.items()):
        fix = FIXTURES[cfg["fixture"]]
        s21 = measured_s21(fix, cfg["shield"], f, cal_loss_db(f), seed=seed + i)
        p = write_dat(raw / f"{name}.dat", f, s21, name, fix.name, fix.length_m, cal_name)
        manifest["samples"][name] = {"file": p.name, "fixture": fix.name, "shield": asdict(cfg["shield"]),
                                     "fixture_params": asdict(fix)}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=1))
    return manifest
