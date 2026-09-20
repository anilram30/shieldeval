#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  SHIELDEVAL v3.2  -  Auswertung Kopplungsdaempfung / Transferimpedanz (Triaxial TUBE500)
#
#  NOTE FOR THIS PROJECT: this file is a *reconstruction* of a legacy in-house
#  evaluation tool, written for Project C as the stand-in for the archived
#  software.  It is intentionally kept in the style of the original (procedural,
#  hard-coded constants, no tests) and it is treated as read-only from here on:
#  the modern package reproduces its numbers exactly in compatibility mode and
#  documents every quirk (marked Q1..Q9 below) before changing anything.
#
#  usage:  python shieldeval_v3.py  messung.dat  [-o ergebnis.res]
#
#  Aenderungen:
#    v3.0  2016-03  erste Python-Version (Port von Excel-Makro)
#    v3.1  2017-11  Kalibrierabzug aus .cal Datei, 61 Frequenzpunkte
#    v3.2  2019-06  Grenzwerte Klasse A, Huellkurve N=len/40
#
import sys, os, math

VERSION = "3.2"

# Q1: fixture table hard-coded; only TUBE500 was ever used with v3
FIXTURES = {
    "TUBE500": {"LC": 0.5, "Z2": 100.0, "FCUT": 30.0e6},
}
R1 = 50.0
ZS = 150.0          # Normierungsimpedanz Schirmdaempfung
LIMIT_ZT_10MHZ = 10.0   # mOhm/m, Klasse A
LIMIT_AS_MIN = 55.0     # dB, Klasse A

# Q5: fixed output frequency list: 61 points, 1 MHz .. 1 GHz, log spaced, rounded to 3 sig. digits
def outfreqs():
    fl = []
    for i in range(61):
        f = 10.0 ** (6.0 + 3.0 * i / 60.0)
        # round to 3 significant digits
        e = int(math.floor(math.log10(f)))
        m = round(f / 10 ** (e - 2)) * 10 ** (e - 2)
        fl.append(float(m))
    return fl


def readdat(fn):
    hdr = {}
    f = []
    a = []
    ph = []
    fh = open(fn, "r")
    for line in fh:
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
    fh.close()
    return hdr, f, a, ph


def readcal(fn):
    hdr, f, a, ph = readdat(fn)
    return f, a


def interp_lin(x, xp, fp):
    # Q2: linear interpolation in *linear* frequency, constant extrapolation
    if x <= xp[0]:
        return fp[0]
    if x >= xp[-1]:
        return fp[-1]
    i = 0
    while xp[i + 1] < x:
        i += 1
    t = (x - xp[i]) / (xp[i + 1] - xp[i])
    return fp[i] + t * (fp[i + 1] - fp[i])


def evaluate(datfile, outfile=None):
    hdr, f, a, ph = readdat(datfile)
    fix = FIXTURES[hdr.get("FIXTURE", "TUBE500")]
    LC = fix["LC"]
    Z2 = fix["Z2"]
    FCUT = fix["FCUT"]

    # Q3: first point dropped ("DC glitch of the old analyser")
    f = f[1:]
    a = a[1:]

    # calibration subtraction (Q2) in dB, cal file next to the measurement
    calfile = hdr.get("CAL", "")
    if calfile:
        cp = os.path.join(os.path.dirname(datfile), calfile)
        fc, ac = readcal(cp)
        for i in range(len(f)):
            a[i] = a[i] - interp_lin(f[i], fc, ac)

    n = len(f)
    # Q4: envelope = sliding maximum of the coupling (minimum of attenuation) over
    #     N = n/40 + 1 points, window [i, i+N) (asymmetric, point based)
    N = int(n / 40) + 1
    aenv = []
    for i in range(n):
        m = a[i]
        for j in range(i, min(i + N, n)):
            if a[j] < m:
                m = a[j]
        aenv.append(m)

    zt = []      # mOhm/m, only below FCUT
    aS = []      # dB, only above FCUT
    for i in range(n):
        if f[i] < FCUT:
            # Q6: 1e-12 guard; LF formula with R1 only
            zt.append(R1 / LC * 10.0 ** (-a[i] / 20.0) * 1000.0 + 1e-12)
            aS.append(None)
        else:
            zt.append(None)
            # Q7: normalisation 10*log10(2*ZS/Z2) written as 300/Z2
            aS.append(aenv[i] + 10.0 * math.log10(300.0 / Z2))

    # Q5: results on the fixed frequency list by nearest neighbour
    fo = outfreqs()
    rows = []
    for fx in fo:
        # nearest point
        best = 0
        for i in range(n):
            if abs(f[i] - fx) < abs(f[best] - fx):
                best = i
        rows.append((fx, zt[best], aS[best], f[best]))

    # summary values (Q8: "ZT at 10 MHz" = nearest raw point below or at 10 MHz)
    zt10 = None
    for i in range(n):
        if f[i] <= 10.0e6 and zt[i] is not None:
            zt10 = zt[i]
    asmin = None
    for i in range(n):
        if aS[i] is not None and (asmin is None or aS[i] < asmin):
            asmin = aS[i]
    verdict = "PASS"
    if zt10 is None or zt10 > LIMIT_ZT_10MHZ:
        verdict = "FAIL"
    if asmin is None or asmin < LIMIT_AS_MIN:
        verdict = "FAIL"

    out = []
    out.append("# SHIELDEVAL v%s RESULT" % VERSION)
    out.append("# SAMPLE=%s" % hdr.get("SAMPLE", "?"))
    out.append("# FIXTURE=%s LC=%.3f Z2=%.1f FCUT=%.0f" % (hdr.get("FIXTURE", "TUBE500"), LC, Z2, FCUT))
    out.append("# CAL=%s" % calfile)
    out.append("# N_ENV=%d NPOINTS=%d" % (N, n))
    out.append("# ZT_10MHZ=%.3f mOhm/m  AS_MIN=%.1f dB  VERDICT=%s" % (zt10 if zt10 is not None else -1.0,
                                                                     asmin if asmin is not None else -1.0, verdict))
    out.append("f[Hz]  ZT[mOhm/m]  aS[dB]  f_raw[Hz]")
    for (fx, z, s, fr) in rows:
        # Q9: 3 decimals for ZT, 1 decimal for aS, "-" when not applicable
        zs = ("%.3f" % z) if z is not None else "-"
        ss = ("%.1f" % s) if s is not None else "-"
        out.append("%.6e  %s  %s  %.6e" % (fx, zs, ss, fr))
    txt = "\n".join(out) + "\n"
    if outfile:
        fh = open(outfile, "w")
        fh.write(txt)
        fh.close()
    return txt


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: shieldeval_v3.py messung.dat [-o ergebnis.res]")
        sys.exit(1)
    outfile = None
    if "-o" in sys.argv:
        outfile = sys.argv[sys.argv.index("-o") + 1]
    txt = evaluate(sys.argv[1], outfile)
    if not outfile:
        sys.stdout.write(txt)
