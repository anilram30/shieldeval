"""Readers for the legacy raw format (.dat / .cal) and a generic CSV export."""
from __future__ import annotations

from pathlib import Path

import numpy as np

__all__ = ["read_dat", "read_measurement", "Measurement"]


def read_dat(path: str | Path):
    """Legacy v3 raw file: '# KEY=VALUE' header lines, then 'f a [phase]' rows.
    Returns (header dict, f list, a list, phase list) with values as floats."""
    hdr: dict[str, str] = {}
    f: list[float] = []
    a: list[float] = []
    ph: list[float] = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        if line[0] == "#":
            if "=" in line:
                k, v = line[1:].split("=", 1)
                hdr[k.strip()] = v.strip()
            continue
        parts = line.split()
        f.append(float(parts[0]))
        a.append(float(parts[1]))
        if len(parts) > 2:
            ph.append(float(parts[2]))
    return hdr, f, a, ph


class Measurement:
    """A shield measurement: attenuation a(f) = -20 log10 |S21| (dB), optional phase,
    header metadata, and the calibration run if referenced."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        hdr, f, a, ph = read_dat(self.path)
        self.header = hdr
        self.f = np.array(f, float)
        self.a_db = np.array(a, float)
        self.phase_deg = np.array(ph, float) if ph else None
        self.sample = hdr.get("SAMPLE", self.path.stem)
        self.fixture_id = hdr.get("FIXTURE", "TUBE500")
        self.cal_name = hdr.get("CAL", "")
        self.f_cal = self.a_cal = None
        if self.cal_name:
            cp = self.path.parent / self.cal_name
            if cp.exists():
                _, fc, ac, _ = read_dat(cp)
                self.f_cal, self.a_cal = np.array(fc, float), np.array(ac, float)

    @property
    def s21(self) -> np.ndarray:
        mag = 10 ** (-self.a_db / 20)
        if self.phase_deg is not None:
            return mag * np.exp(1j * np.radians(self.phase_deg))
        return mag.astype(complex)


def read_measurement(path: str | Path) -> Measurement:
    return Measurement(path)
