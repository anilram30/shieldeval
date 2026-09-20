"""
Physics of the triaxial (tube-in-tube) and line-injection shield measurements.

Geometry and circuit
--------------------
The cable under test is the *inner* circuit: a coaxial (or screened) line of
characteristic impedance Z_1 and propagation constant gamma_1, driven at
z = 0 by a generator of source impedance R_1 and terminated at z = L_c in
R_1 (matched), so the inner current is  I_1(z) = I_0 e^{-gamma_1 z},
I_0 = V_gen / (2 R_1).

The *outer* circuit is formed by the outside of the shield and the tube
(triaxial) or the injection wire (line injection): a second line of
characteristic impedance Z_2 and propagation constant gamma_2 (air, v_2 ~
c_0).  At z = 0 it is connected to the receiver R_2; at z = L_c it is
short-circuited (triaxial, IEC 62153-4-3/-4-4) or terminated in R_2 (line
injection, IEC 62153-4-6).

Coupling
--------
The transfer impedance Z_T(f) (ohm/m) of the shield acts as a distributed
series EMF in the outer circuit,  dE(z) = Z_T I_1(z) dz.  By superposition
the receiver voltage is

    V_2 = R_2 * integral_0^{L_c}  Z_T I_1(z) T(z) / (Z_near(z) + Z_far(z)) dz ,

where Z_near(z) is the impedance seen from z toward the receiver (a line of
length z terminated in R_2), Z_far(z) the impedance toward the far end (a
line of length L_c - z terminated in a short or in R_2), and
T(z) = 1 / (cosh(gamma_2 z) + (R_2/Z_2) sinh(gamma_2 z)) the current
transfer from z to the receiver.  With a uniform Z_T the measured
transmission factorises,

    S_21(f) = 2 V_2 / V_gen = Z_T(f) K(f),

into the shield property Z_T and a *coupling function* K(f) that depends
only on the fixture (Z_2, gamma_2, L_c, R_1, R_2, the far-end condition)
and on the inner line's gamma_1.  In the electrically short limit
K -> L_c / R_1, which gives the textbook  Z_T = R_1 |S_21| / L_c; the
modern evaluation divides by the full K(f) instead and thereby extends the
transfer-impedance regime beyond the classic cut-off, except close to the
zeros of K.

Transfer impedance of a braid (synthetic data only)
---------------------------------------------------
Z_T(f) = Z_R(f) + j omega M_T  with the diffusion term
Z_R = R_dc (1+j) d/delta / sinh((1+j) d/delta)  (delta = skin depth in the
strand material, d = strand diameter) and the net coupling inductance
M_T = L_hole - L_braid, which can be negative for optimised braids
(Vance 1978; Tyni 1976).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

C0 = 299_792_458.0
MU0 = 4e-7 * np.pi

__all__ = ["Fixture", "coupling_function", "BraidShield", "measured_s21", "C0"]


@dataclass
class Fixture:
    name: str
    length_m: float            # coupling length L_c
    z2: float                  # outer-circuit characteristic impedance
    v2_rel: float = 1.0        # outer-circuit velocity / c0
    r1: float = 50.0           # generator / inner termination
    r2: float = 50.0           # receiver impedance
    far_end: str = "short"     # "short" (triaxial) or "matched" (line injection)
    alpha2_np_per_m_at_1ghz: float = 0.02   # outer-circuit loss (sqrt f)
    z1: float = 50.0           # inner (cable) impedance
    v1_rel: float = 0.66       # inner velocity / c0
    alpha1_np_per_m_at_1ghz: float = 0.15   # inner cable loss (sqrt f)
    per_metre: bool = True     # report Z_T per metre (cables) or absolute (connectors)

    def gamma1(self, f: np.ndarray) -> np.ndarray:
        return self.alpha1_np_per_m_at_1ghz * np.sqrt(f / 1e9) + 2j * np.pi * f / (self.v1_rel * C0)

    def gamma2(self, f: np.ndarray) -> np.ndarray:
        return self.alpha2_np_per_m_at_1ghz * np.sqrt(f / 1e9) + 2j * np.pi * f / (self.v2_rel * C0)


def coupling_function(fix: Fixture, f: np.ndarray, n_seg: int = 400) -> np.ndarray:
    """K(f) = S_21 / Z_T for a uniform transfer impedance (units: m/ohm)."""
    f = np.asarray(f, float)
    g1 = fix.gamma1(f)[:, None]
    g2 = fix.gamma2(f)[:, None]
    z = (np.arange(n_seg) + 0.5) / n_seg * fix.length_m
    dz = fix.length_m / n_seg
    z = z[None, :]
    L = fix.length_m
    Z2, R2 = fix.z2, fix.r2
    th_near = np.tanh(g2 * z)
    z_near = Z2 * (R2 + Z2 * th_near) / (Z2 + R2 * th_near)
    th_far = np.tanh(g2 * (L - z))
    if fix.far_end == "short":
        z_far = Z2 * th_far
    elif fix.far_end == "matched":
        z_far = Z2 * (R2 + Z2 * th_far) / (Z2 + R2 * th_far)
    elif fix.far_end == "open":
        z_far = Z2 / th_far
    else:
        raise ValueError("far_end must be short, matched or open")
    T = 1.0 / (np.cosh(g2 * z) + (R2 / Z2) * np.sinh(g2 * z))
    i1 = np.exp(-g1 * z) / (2 * fix.r1)          # I_1(z) / V_gen
    integrand = i1 * T / (z_near + z_far)
    v2_over_vgen = R2 * np.sum(integrand, axis=1) * dz
    return 2.0 * v2_over_vgen                       # S21 / Z_T


@dataclass
class BraidShield:
    """Transfer impedance model of a braided (or braid + foil) shield."""
    r_dc_ohm_per_m: float = 5e-3
    strand_d_m: float = 0.15e-3
    m_t_h_per_m: float = 0.5e-9        # net coupling inductance (can be negative)
    rho: float = 1.72e-8               # copper
    mu_r: float = 1.0

    def z_t(self, f: np.ndarray) -> np.ndarray:
        f = np.asarray(f, float)
        w = 2 * np.pi * f
        delta = np.sqrt(2 * self.rho / (w * MU0 * self.mu_r))
        k = (1 + 1j) * self.strand_d_m / delta
        zr = self.r_dc_ohm_per_m * k / np.sinh(k)
        return zr + 1j * w * self.m_t_h_per_m


def measured_s21(fix: Fixture, shield: BraidShield, f: np.ndarray, cal_loss_db: np.ndarray | None = None,
                 noise_db: float = -110.0, seed: int = 0) -> np.ndarray:
    """Synthetic analyser reading (complex S21) including the setup's insertion
    loss (what the calibration run measures) and receiver noise."""
    k = coupling_function(fix, f)
    s = shield.z_t(f) * k
    if cal_loss_db is not None:
        s = s * 10 ** (-cal_loss_db / 20)
    rng = np.random.default_rng(seed)
    sigma = 10 ** (noise_db / 20) / np.sqrt(2)
    return s + sigma * (rng.standard_normal(f.size) + 1j * rng.standard_normal(f.size))
