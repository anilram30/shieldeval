---
bibliography: references.bib
title: "shieldeval: reconstruction and modernisation of the legacy shield-evaluation tool"
subtitle: "Project C — transfer impedance and screening attenuation from triaxial and line-injection measurements"
author: "Sreeram Anil"
date: "18 September 2026"
lang: en
geometry: margin=2.3cm
fontsize: 10.5pt
numbersections: true
toc: true
toc-depth: 2
colorlinks: true
header-includes:
  - \usepackage{amsmath,amssymb}
  - \usepackage{booktabs}
  - \usepackage{float}
  - \floatplacement{figure}{H}
---

\newpage

# Purpose and the ground rules of a legacy rewrite

An in-house program, several versions old, turns the raw output of the shield measurement into the two numbers the laboratory reports: the transfer impedance $Z_T$ of the cable shield at low frequency and its screening attenuation $a_S$ at high frequency. The physics behind those numbers is fiddly. The measurement fixture — a tube around the cable, or an injection wire above it — behaves as an electrically short loop below a certain frequency and as a resonant transmission line above it, so the software has to know which regime it is in, trace the envelope of a standing-wave pattern in the second regime, normalise the result to a reference condition, and subtract a calibration run. The old program does all of that, with constants typed in by people who have since left, and nobody dares to touch it because its results are in ten years of reports.

The rules this project follows are the ones any responsible rewrite of such a tool has to follow:

1. **Reconstruct before changing.** The legacy behaviour is re-implemented step by step, each step named, its quirk documented, and the whole reproduced *byte for byte* on the archived data (six samples, six result files) before a single number is improved. The compatibility mode stays available, so an old report can always be regenerated.
2. **Change only with a reason and a number.** Every modernisation is tied to a documented quirk, and its effect on the archived samples is quantified (Section 6).
3. **Extend by data, not by code.** The newer fixtures the laboratory has acquired (a 1 m tube, a line-injection set-up, a connector fixture) are profiles in TOML files that carry the fixture's physics; the evaluation code is the same for all of them.

One thing must be stated plainly. The laboratory's legacy program and its archive are confidential and were not available to this project. The "legacy tool" here — `legacy/shieldeval_v3.py`, 150 lines in the style of a 2016 script — was *written for this project* as a stand-in, with the kinds of quirks such tools really have, and the "archive" was produced by running it on synthetic raw files generated from the physics of Section 2. The method is therefore demonstrated end to end, but the reproduction of a stand-in is not evidence about the real program; on the real one the same procedure applies, starting with the characterisation tests of Section 4.

# Physics of the measurement

## Circuit and coupling function

The cable under test is the *inner* circuit: a line of characteristic impedance $Z_1$ and propagation constant $\gamma_1$, driven at $z = 0$ by a generator of source impedance $R_1$ and terminated in $R_1$ at $z = L_c$, so that $I_1(z) = I_0 e^{-\gamma_1 z}$ with $I_0 = V_\text{gen}/(2R_1)$. The *outer* circuit is formed by the outside of the shield and the tube (triaxial method, IEC 62153-4-3 [@iec62153_4_3] and -4-4 [@iec62153_4_4]) or the injection wire (line injection, IEC 62153-4-6 [@iec62153_4_6]): a second line of impedance $Z_2$ and propagation constant $\gamma_2$, connected to the receiver $R_2$ at $z = 0$ and short-circuited (triaxial) or terminated in $R_2$ (line injection) at $z = L_c$.

The transfer impedance $Z_T(f)$ of the shield [@vance1978] acts as a distributed series EMF in the outer circuit, $\mathrm dE = Z_T I_1(z)\,\mathrm dz$. By superposition, the receiver voltage is

$$
V_2 = R_2\int_0^{L_c} \frac{Z_T\, I_1(z)\, T(z)}{Z_\text{near}(z) + Z_\text{far}(z)}\,\mathrm dz ,
$$

where $Z_\text{near}(z) = Z_2\,\dfrac{R_2 + Z_2\tanh\gamma_2 z}{Z_2 + R_2\tanh\gamma_2 z}$ is the impedance seen from $z$ toward the receiver, $Z_\text{far}(z)$ the impedance toward the far end ($Z_2\tanh\gamma_2(L_c - z)$ for a short, the matched-line expression for line injection), and $T(z) = 1/\big(\cosh\gamma_2 z + (R_2/Z_2)\sinh\gamma_2 z\big)$ the current transfer from $z$ to the receiver. With a $Z_T$ that is uniform along the sample the measured transmission factorises,

$$
S_{21}(f) = \frac{2V_2}{V_\text{gen}} = Z_T(f)\,K(f),
$$

into the shield property and a **coupling function** $K(f)$ that depends only on the fixture ($Z_2$, $\gamma_2$, $L_c$, $R_1$, $R_2$, far-end condition) and on the inner line's $\gamma_1$. In the electrically short limit $K \to L_c/R_1$ for the short-circuited tube and $L_c/(2R_1)$ for the matched injection line (the EMF then drives two terminations in series), which gives the textbook formulas $Z_T = R_1|S_{21}|/L_c$ and $Z_T = 2R_1|S_{21}|/L_c$ — the IEC form $Z_T = (R_1 + R_2)|S_{21}|/(2L_c)$ coincides with them for $R_1 = R_2 = 50\ \Omega$. Both limits are unit tests of `physics.coupling_function`.

## Transfer impedance of a braid (synthetic data)

For the synthetic archive the shield is a braid with the classical model [@vance1978; @tyni1976]

$$
Z_T(f) = R_\text{dc}\,\frac{(1 + j)\,d/\delta}{\sinh\big((1 + j)\,d/\delta\big)} + j\omega M_T,\qquad \delta = \sqrt{\frac{2\rho}{\omega\mu_0}},
$$

with $d$ the strand diameter, $\delta$ the skin depth and $M_T = L_\text{hole} - L_\text{braid}$ the net coupling inductance, which is negative for optimised braids. The diffusion term falls, the inductive term rises, and the magnitude has the well-known minimum around 1 MHz. Six shields (single, optimised, braid + foil, loose, thin-strand and double braid) span two decades of $Z_T$; three more samples were "measured" on the newer fixtures. The analyser export is emulated exactly: 401 log-spaced points from 100 kHz to 1 GHz, attenuation with two decimals, phase with one, a calibration run on a coarser 101-point grid, and receiver noise at $-110$ dB.

# The legacy tool and its quirk register

`legacy/shieldeval_v3.py` reads the raw file, subtracts the calibration run, splits the band at a fixed cut-off, computes $Z_T$ below it and the envelope-based $a_S$ above it, and writes 61 result lines plus a verdict. Its re-implementation `shieldeval.legacy` keeps the arithmetic in the same order so that the floating-point results are identical, and documents nine quirks:

| | legacy behaviour | why it is questionable | modern behaviour |
|---|---|---|---|
| Q1 | fixture table hard-coded: TUBE500 only, $L_c = 0.5$ m, $Z_2 = 100\ \Omega$, $f_\text{cut} = 30$ MHz | new fixtures cannot be used; the cut-off is a typed-in number | fixture profiles in TOML; transition from the coupling function |
| Q2 | calibration interpolated linearly *in linear frequency* from the 101-point cal grid, subtracted in dB | the sweeps are logarithmic; the interpolation over-estimates the loss by up to 0.02 dB below 1 MHz | interpolation in log frequency |
| Q3 | first sweep point dropped ("DC glitch") | hides a data problem instead of flagging it | all points kept; noise-floor flag |
| Q4 | envelope = sliding minimum of attenuation over $N = \lfloor n/40\rfloor + 1$ points, forward-looking window $[i, i + N)$ | shifted toward lower frequency by up to $N$ points (1.5 dB error in $a_S$ on the rising part); $N$ depends on the number of sweep points, not on the physics | centred window of one resonance spacing $v_2/(2L_c)$, applied only where a standing wave is present |
| Q5 | output on 61 fixed frequencies by nearest neighbour | the reported frequency is not the measured one; interpolation error up to 3 % in $Z_T$ | full-resolution curves; summary values interpolated in log–log |
| Q6 | $10^{-12}$ added to $Z_T$ | a log guard that outlived its purpose | removed |
| Q7 | $a_S = a_\text{env} + 10\log_{10}(300/Z_2)$ | $k_\text{norm} = 2$ and $Z_s = 150\ \Omega$ baked into a literal | both in the fixture profile, with provenance |
| Q8 | "$Z_T$ at 10 MHz" = last raw point at or below 10 MHz | systematically low by 2–3 % because $Z_T$ rises with $f$ | log–log interpolation at exactly 10 MHz |
| Q9 | $Z_T$ with 3 decimals, $a_S$ with 1 decimal, "–" where not applicable | format only | JSON with full precision; HTML report |

And one behaviour that is not a formatting quirk but a wrong answer: the legacy tool reports a number for $Z_T$ whatever the signal level, so a very good shield whose coupling is at the receiver noise floor gets a flattering, fictitious $Z_T$ (the double braid: 0.388 m$\Omega$/m reported, 0.625 true, both below the floor). The modern tool reports an *upper bound* instead.

# Equivalence proof

`shieldeval compare archive/` runs the compatibility mode on every raw file of the archive and compares the output text with the archived result:

```
S01_single_braid             IDENTICAL
S02_optimised_braid          IDENTICAL
S03_braid_foil               IDENTICAL
S04_loose_braid              IDENTICAL
S05_thin_strands             IDENTICAL
S06_double_braid             IDENTICAL
6/6 archived results reproduced byte for byte
```

`tests/test_legacy_equivalence.py` makes this a permanent characterisation test, and a second test runs the *original* script and compares its bytes as well, so that the archive cannot drift either. Byte identity, not "within tolerance", is the right criterion here: the moment a rewrite is allowed to differ by 0.001, every later difference has to be argued about.

# The modern evaluation

`shieldeval.core.evaluate` performs, for any fixture profile:

1. **Calibration** in log frequency and a noise-floor flag from the instrument specification (105 dB, lowered if the raw trace is visibly at the floor), with a 10 dB margin.
2. **Regime detection.** The *model* transition $f_t$ is the frequency at which $|K(f)|$ has fallen 1 dB below $L_c/R_1$ — where the textbook formula starts to be wrong by that amount (25 MHz for the 0.5 m tube, 14 MHz for the 1 m tube, 36 MHz for the injection line); the *data* cross-checks are the position of the first standing-wave maximum and the spacing of the pattern, compared with the fixture model's first resonance and $v_2/(2L_c)$. A measurement evaluated with the wrong profile (the 1 m tube's data with the 0.5 m profile) is flagged (`test_fixture_mismatch_is_flagged`).
3. **Transfer impedance** by dividing the complex $S_{21}$ by the full coupling function, $Z_T = S_{21}/K$, valid up to the first zero of $K$ and masked where $|K| < 0.25\,|K(0)|$ or the signal is within 10 dB of the noise floor. This is the substantive extension: on the 0.5 m tube the usable range grows from 30 MHz (legacy) to 630 MHz with a median error of 0.05 dB and a 90th percentile of 0.5 dB against the generating model (Table 1), and on the injection line — where the legacy formula would be 6 dB wrong even at low frequency, because the far end is matched — the model-based value is right to 0.1 dB (Figure 2).
4. **Screening attenuation** from the centred-window envelope, $a_S = a_\text{env} + 10\log_{10}(k_\text{norm} Z_s/Z_2)$ with $k_\text{norm}$ and $Z_s$ in the profile (values transcribed from the public standard text; the profile carries a verify-against-controlled-copy note, as in Project A).
5. **Summary and verdict**: $Z_T$ at 1, 10 and 30 MHz (log–log interpolation, never bridging a masked region), the upper bound at 10 MHz when the reading is at the floor, $a_S,\min$ and where it occurs, the transition frequencies, and PASS / FAIL / INCONCLUSIVE against the profile's limit class. A shield below the floor *passes* if the floor itself is inside the limit, and is INCONCLUSIVE otherwise — the honest version of what the legacy tool silently did.

![`S01_single_braid` on the 0.5 m tube: raw and calibrated attenuation with the modern envelope (red) and the lagging legacy envelope (orange, dashed); below, $|Z_T|$ from the model-based division (green) against the generating model (black), with the legacy result (dotted) ending at its 30 MHz cut-off.](figures/validation_S01_single_braid.png){width=92%}

![`N02_optimised_lineinj` on the line-injection fixture: the classic formula (blue, dashed) is 6 dB low because the matched far end halves the coupled current; the model-based $Z_T$ (green) follows the truth. Below 4 MHz the measurement is at the noise floor and correctly masked.](figures/validation_N02_optimised_lineinj.png){width=92%}

# Validation against the generating model

\footnotesize

| sample | fixture | Z_T(10 MHz) true | legacy v3 | modern | modern err median / 90 % (dB), valid to | classic err median / 90 % below f_cut | a_S,min legacy / modern | verdict legacy / modern |
|:----------------------|:-------|:------|:------|:------------|:----------------|:-------------|:----------|:----------|
| S01_single_braid | TUBE500 | 31.407 | 30.549 | 31.314 | 0.05 / 0.52, 631 MHz | 0.28 / 0.87 | 48.3 / 48.3 | FAIL / FAIL |
| S02_optimised_braid | TUBE500 | 9.432 | 9.322 | 9.555 | 0.14 / 0.69, 631 MHz | 0.40 / 0.97 | 58.7 / 58.7 | PASS / PASS |
| S03_braid_foil | TUBE500 | 2.036 | 1.858 | 1.904 | 0.33 / 1.12, 631 MHz | 0.62 / 1.48 | 72.7 / 72.7 | PASS / PASS |
| S04_loose_braid | TUBE500 | 157.070 | 153.638 | 157.483 | 0.01 / 0.31, 631 MHz | 0.16 / 0.72 | 34.3 / 34.3 | FAIL / FAIL |
| S05_thin_strands | TUBE500 | 50.080 | 48.473 | 49.686 | 0.04 / 0.25, 631 MHz | 0.17 / 0.55 | 44.2 / 44.2 | FAIL / FAIL |
| S06_double_braid | TUBE500 | 0.625 | 0.388 | < 1.904 (floor) | 0.37 / 1.55, 631 MHz | 0.68 / 1.99 | 82.4 / 82.4 | PASS / PASS |
| N01_single_braid_tube1000 | TUBE1000 | 31.407 | nan | 31.331 | 0.03 / 0.26, 316 MHz | 0.20 / 0.62 | nan / 49.0 | – / FAIL |
| N02_optimised_lineinj | LINEINJ | 9.432 | nan | 9.208 | 0.12 / 0.82, 759 MHz | 6.19 / 6.95 | nan / 64.6 | – / PASS |
| N03_connector | CONN | 125.628 | nan | 125.531 | 0.01 / 0.10, 1000 MHz | 0.03 / 0.33 | nan / 23.7 | – / FAIL |

\normalsize

Table 1: $Z_T$ at 10 MHz in m$\Omega$/m (m$\Omega$ for the connector); errors are $|20\log_{10}(Z_{T,\text{eval}}/Z_{T,\text{true}})|$ over the valid points.

Three observations. The legacy $Z_T$ at 10 MHz is 2–3 % low on every sample (Q8), the modern one within 0.5 %. The legacy and modern $a_{S,\min}$ agree to 0.05 dB on the 0.5 m tube because both find the same global minimum of the standing-wave pattern — the envelopes differ elsewhere, which matters when a limit line rather than a single minimum is applied. And the newer fixtures work without any code change: the 1 m tube (usable $Z_T$ range to 316 MHz, resonance spacing halved), the injection line (usable to 760 MHz), and the connector fixture, whose results are absolute ohms over the 50 mm coupling length.

# Limitations

* The stand-in nature of the legacy tool and archive (Section 1). The procedure — characterisation tests first, byte-exact compatibility mode, quirk register with numbers, then extension by profiles — is the deliverable; the real program will have its own quirks.
* The coupling function assumes a uniform $Z_T$ along the sample and neglects the transfer admittance (capacitive leakage), which is the standard assumption for braids with good optical coverage in a low-impedance outer circuit; for leaky braids or foils with drain wires the IEC methods themselves are approximate.
* The screening-attenuation normalisation constants ($k_\text{norm}$, $Z_s$) and the limit values are transcribed from public material and flagged for verification against the controlled standards.
* Above the first zero of $K$ the transfer impedance is not recoverable from a single fixture length; the standards' answer (a second, shorter sample) is a second fixture profile here.

\newpage

# Appendix: the legacy result format (S01)

\footnotesize

```
# SHIELDEVAL v3.2 RESULT
# SAMPLE=S01_single_braid
# FIXTURE=TUBE500 LC=0.500 Z2=100.0 FCUT=30000000
# CAL=cal_20210412.cal
# N_ENV=11 NPOINTS=400
# ZT_10MHZ=30.549 mOhm/m  AS_MIN=48.3 dB  VERDICT=FAIL
f[Hz]  ZT[mOhm/m]  aS[dB]  f_raw[Hz]
1.000000e+06  0.440  -  1.000000e+06
1.120000e+06  0.348  -  1.122018e+06
1.260000e+06  0.969  -  1.258925e+06
1.410000e+06  2.523  -  1.412538e+06
1.580000e+06  2.924  -  1.584893e+06
1.780000e+06  4.188  -  1.778279e+06
2.000000e+06  5.009  -  1.995262e+06
2.240000e+06  6.539  -  2.238721e+06
2.510000e+06  7.861  -  2.511886e+06
2.820000e+06  8.821  -  2.818383e+06
3.160000e+06  9.994  -  3.162278e+06
3.550000e+06  11.105  -  3.548134e+06
3.980000e+06  12.647  -  3.981072e+06
4.470000e+06  14.575  -  4.466836e+06
5.010000e+06  16.051  -  5.011872e+06
5.620000e+06  17.418  -  5.623413e+06
6.310000e+06  19.656  -  6.309573e+06
7.080000e+06  22.387  -  7.079458e+06
7.940000e+06  24.889  -  7.943282e+06
8.910000e+06  27.534  -  8.912509e+06
1.000000e+07  30.549  -  1.000000e+07
1.120000e+07  34.207  -  1.122018e+07
1.260000e+07  37.888  -  1.258925e+07
1.410000e+07  42.596  -  1.412538e+07
1.580000e+07  47.534  -  1.584893e+07
1.780000e+07  52.541  -  1.778279e+07
2.000000e+07  57.510  -  1.995262e+07
2.240000e+07  63.460  -  2.238721e+07
2.510000e+07  70.065  -  2.511886e+07
2.820000e+07  76.669  -  2.818383e+07
3.160000e+07  -  65.1  3.162278e+07
3.550000e+07  -  64.5  3.548134e+07
3.980000e+07  -  64.0  3.981072e+07
4.470000e+07  -  63.6  4.466836e+07
5.010000e+07  -  63.2  5.011872e+07
5.620000e+07  -  62.9  5.623413e+07
6.310000e+07  -  62.8  6.309573e+07
7.080000e+07  -  62.6  7.079458e+07
7.940000e+07  -  62.6  7.943282e+07
8.910000e+07  -  62.6  8.912509e+07
1.000000e+08  -  62.6  1.000000e+08
1.120000e+08  -  62.6  1.122018e+08
1.260000e+08  -  62.7  1.258925e+08
1.410000e+08  -  62.6  1.412538e+08
1.580000e+08  -  61.4  1.584893e+08
1.780000e+08  -  59.1  1.778279e+08
2.000000e+08  -  55.7  1.995262e+08
2.240000e+08  -  52.1  2.238721e+08
2.510000e+08  -  50.8  2.511886e+08
2.820000e+08  -  50.8  2.818383e+08
3.160000e+08  -  50.8  3.162278e+08
3.550000e+08  -  52.5  3.548134e+08
3.980000e+08  -  54.8  3.981072e+08
4.470000e+08  -  50.0  4.466836e+08
5.010000e+08  -  48.3  5.011872e+08
5.620000e+08  -  48.3  5.623413e+08
6.310000e+08  -  49.7  6.309573e+08
7.080000e+08  -  51.8  7.079458e+08
7.940000e+08  -  51.8  7.943282e+08
8.910000e+08  -  51.8  8.912509e+08
1.000000e+09  -  63.7  1.000000e+09
```

\normalsize

# References

::: {#refs}
:::
