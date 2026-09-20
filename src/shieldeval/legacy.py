"""
Exact re-implementation of the legacy SHIELDEVAL v3.2 evaluation, quirk by quirk.

This module exists so that the modern package can reproduce the archived
results *byte for byte* (``tests/test_legacy_equivalence.py``).  Every step
is a named function whose docstring records the legacy behaviour (Q1..Q9),
the physical reason it is questionable, and what the modern evaluation
does instead.  The arithmetic is kept in the same order as the original
so that floating-point results are identical, not merely close.

Quirk register
--------------
Q1  Fixture table hard-coded (TUBE500 only): L_c = 0.5 m, Z_2 = 100 ohm,
    f_cut = 30 MHz.  Modern: fixture profiles in TOML, transition from the
    fixture's coupling function.
Q2  Calibration interpolated *linearly in linear frequency* onto the
    measurement grid (the .cal file has 101 log-spaced points, the
    measurement 401), then subtracted in dB.  Between 100 kHz and 1 MHz the
    cal grid is coarse and the linear-in-f interpolation over-estimates the
    loss by up to 0.02 dB.  Modern: interpolation in log frequency.
Q3  The first sweep point is dropped ("DC glitch").  Modern: keep it, flag
    points below the receiver noise floor instead.
Q4  Envelope = sliding minimum of attenuation over N = floor(n/40)+1 points
    with an *asymmetric, forward-looking* window [i, i+N): the envelope is
    shifted towards lower frequency by up to N points, and N depends on the
    number of sweep points rather than on the resonance spacing.  Modern:
    local minima of attenuation with prominence, PCHIP-interpolated, and a
    window defined in frequency from the fixture length.
Q5  Output on 61 fixed log-spaced frequencies by nearest neighbour; the
    reported frequency is the rounded nominal value, the raw frequency is
    printed alongside.  Modern: full-resolution curves plus summary values
    interpolated in log-log.
Q6  1e-12 added to Z_T (log guard that outlived its purpose).
Q7  a_S = a_env + 10 log10(300 / Z_2), i.e. k_norm = 2, Z_s = 150 ohm,
    baked into a literal.
Q8  "Z_T at 10 MHz" = the last raw point at or below 10 MHz (not
    interpolated); a_S,min = minimum of a_S over all points above f_cut.
Q9  Number formats: Z_T with 3 decimals in mOhm/m, a_S with 1 decimal;
    "-" where not applicable.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass

from .io import read_dat

__all__ = ["LegacyResult", "legacy_evaluate", "legacy_outfreqs", "LEGACY_FIXTURES"]

VERSION = "3.2"
LEGACY_FIXTURES = {"TUBE500": {"LC": 0.5, "Z2": 100.0, "FCUT": 30.0e6}}
R1 = 50.0
LIMIT_ZT_10MHZ = 10.0
LIMIT_AS_MIN = 55.0


def legacy_outfreqs() -> list[float]:
    """Q5: 61 points, 1 MHz..1 GHz, rounded to three significant digits."""
    fl = []
    for i in range(61):
        f = 10.0 ** (6.0 + 3.0 * i / 60.0)
        e = int(math.floor(math.log10(f)))
        m = round(f / 10 ** (e - 2)) * 10 ** (e - 2)
        fl.append(float(m))
    return fl


def _interp_lin(x: float, xp: list[float], fp: list[float]) -> float:
    """Q2: linear interpolation in linear frequency with constant extrapolation."""
    if x <= xp[0]:
        return fp[0]
    if x >= xp[-1]:
        return fp[-1]
    i = 0
    while xp[i + 1] < x:
        i += 1
    t = (x - xp[i]) / (xp[i + 1] - xp[i])
    return fp[i] + t * (fp[i + 1] - fp[i])


@dataclass
class LegacyResult:
    text: str
    f: list[float]
    a_corr: list[float]
    a_env: list[float]
    zt_mohm: list[float | None]
    as_db: list[float | None]
    zt_10mhz: float | None
    as_min: float | None
    verdict: str
    n_env: int


def legacy_evaluate(dat_path: str) -> LegacyResult:
    hdr, f, a, ph = read_dat(dat_path)
    f, a = list(map(float, f)), list(map(float, a))
    fix = LEGACY_FIXTURES[hdr.get("FIXTURE", "TUBE500")]
    LC, Z2, FCUT = fix["LC"], fix["Z2"], fix["FCUT"]
    f, a = f[1:], a[1:]                                            # Q3
    calfile = hdr.get("CAL", "")
    if calfile:
        chdr, fc, ac, _ = read_dat(os.path.join(os.path.dirname(dat_path), calfile))
        fc, ac = list(map(float, fc)), list(map(float, ac))
        for i in range(len(f)):
            a[i] = a[i] - _interp_lin(f[i], fc, ac)                 # Q2
    n = len(f)
    N = int(n / 40) + 1                                            # Q4
    aenv = []
    for i in range(n):
        m = a[i]
        for j in range(i, min(i + N, n)):
            if a[j] < m:
                m = a[j]
        aenv.append(m)
    zt, aS = [], []
    for i in range(n):
        if f[i] < FCUT:
            zt.append(R1 / LC * 10.0 ** (-a[i] / 20.0) * 1000.0 + 1e-12)   # Q6
            aS.append(None)
        else:
            zt.append(None)
            aS.append(aenv[i] + 10.0 * math.log10(300.0 / Z2))            # Q7
    fo = legacy_outfreqs()
    rows = []
    for fx in fo:
        best = 0
        for i in range(n):
            if abs(f[i] - fx) < abs(f[best] - fx):
                best = i
        rows.append((fx, zt[best], aS[best], f[best]))                    # Q5
    zt10 = None
    for i in range(n):
        if f[i] <= 10.0e6 and zt[i] is not None:
            zt10 = zt[i]                                                   # Q8
    asmin = None
    for i in range(n):
        if aS[i] is not None and (asmin is None or aS[i] < asmin):
            asmin = aS[i]
    verdict = "PASS"
    if zt10 is None or zt10 > LIMIT_ZT_10MHZ:
        verdict = "FAIL"
    if asmin is None or asmin < LIMIT_AS_MIN:
        verdict = "FAIL"
    out = ["# SHIELDEVAL v%s RESULT" % VERSION, "# SAMPLE=%s" % hdr.get("SAMPLE", "?"),
           "# FIXTURE=%s LC=%.3f Z2=%.1f FCUT=%.0f" % (hdr.get("FIXTURE", "TUBE500"), LC, Z2, FCUT),
           "# CAL=%s" % calfile, "# N_ENV=%d NPOINTS=%d" % (N, n),
           "# ZT_10MHZ=%.3f mOhm/m  AS_MIN=%.1f dB  VERDICT=%s" % (zt10 if zt10 is not None else -1.0,
                                                                 asmin if asmin is not None else -1.0, verdict),
           "f[Hz]  ZT[mOhm/m]  aS[dB]  f_raw[Hz]"]
    for (fx, z, s, fr) in rows:
        zs = ("%.3f" % z) if z is not None else "-"
        ss = ("%.1f" % s) if s is not None else "-"
        out.append("%.6e  %s  %s  %.6e" % (fx, zs, ss, fr))                # Q9
    return LegacyResult("\n".join(out) + "\n", f, a, aenv, zt, aS, zt10, asmin, verdict, N)
