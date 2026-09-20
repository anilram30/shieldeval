"""
Modern evaluation of a shield measurement.

Steps (each replaces one legacy quirk, see :mod:`shieldeval.legacy`):

1. **Calibration.**  The calibration run a_cal(f) (insertion loss of the
   connecting cables and adapters, measured with a through connection) is
   interpolated onto the measurement grid in *log frequency* (the sweeps
   are logarithmic) and subtracted in dB:  a(f) = a_meas(f) - a_cal(f).
   Points within ``noise_margin_db`` of the receiver noise floor (from the
   instrument specification, lowered if the raw trace is visibly noisy)
   are flagged.

2. **Regime detection.**  Two independent estimates are reported.
   *Model*: the frequency at which the fixture's coupling function |K(f)|
   has dropped ``transition_db`` below its low-frequency value L_c/R_1 -
   the point where the textbook Z_T formula starts to be wrong by that
   amount.  *Data*: the first standing-wave maximum of the coupling
   (minimum of attenuation with a prominence above ``prominence_db``),
   which is where the outer circuit becomes resonant.  The transition used
   is the model estimate; the data estimate is a cross-check that catches a
   wrong fixture profile or a mis-connected far end.

3. **Transfer impedance.**  Instead of the electrically-short formula
   Z_T = R_1 |S_21| / L_c (valid only well below the transition) the
   measured S_21 is divided by the full coupling function of the fixture,
       Z_T(f) = S_21(f) / K(f),
   which is exact for a uniform Z_T and extends the usable range up to the
   first zero of K; points where |K| < k_valid |K(0)| are masked as
   ill-conditioned.  Both the classic and the model-based Z_T are kept so
   that the difference is visible.

4. **Screening attenuation.**  Above the transition the attenuation's lower
   envelope (upper envelope of the coupling) is the minimum over a centred
   window of one resonance spacing v_2/(2 L_c), applied only where the
   window contains a standing-wave modulation of at least ``prominence_db``
   (elsewhere the envelope is the curve); the screening attenuation is
       a_S(f) = a_env(f) + 10 log10(k_norm Z_s / Z_2),
   normalised to the environment impedance Z_s (150 ohm) as in IEC
   62153-4-4, with k_norm and Z_s in the fixture profile (verify against
   the controlled document).

5. **Summary and verdict.**  Z_T at 1, 10 and 30 MHz interpolated in
   log-log; a_S,min over the band; limits from the fixture profile.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.signal import find_peaks

from .fixtures import FixtureProfile
from .io import Measurement
from .physics import coupling_function

__all__ = ["Settings", "Evaluation", "evaluate", "envelope_lower", "detect_transition"]


@dataclass
class Settings:
    prominence_db: float = 3.0
    noise_floor_db: float = 105.0            # receiver noise floor in attenuation terms (instrument spec)
    noise_margin_db: float = 10.0
    limit_class: str = "class_A"
    envelope_window_hz: float | None = None  # None: one resonance spacing of the outer circuit
    classic_zt: bool = True


@dataclass
class Evaluation:
    sample: str
    fixture: FixtureProfile
    f: np.ndarray
    a_meas: np.ndarray
    a_cal: np.ndarray
    a: np.ndarray                       # corrected attenuation
    s21: np.ndarray                     # corrected complex S21
    k: np.ndarray                       # coupling function
    zt_model: np.ndarray                # complex, ohm or ohm/m (per fixture)
    zt_classic: np.ndarray              # magnitude, LF formula
    zt_valid: np.ndarray                # mask
    a_env: np.ndarray                   # lower envelope of a (nan below transition)
    a_s: np.ndarray                     # screening attenuation (nan below transition)
    f_transition_model: float
    f_transition_data: float | None
    f_first_null: float | None
    f_resonance_model: float | None
    noise_floor_db: float
    near_noise: np.ndarray
    summary: dict = field(default_factory=dict)
    verdict: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"sample": self.sample, "fixture": self.fixture.id, "summary": self.summary, "verdict": self.verdict,
                "f_transition_model_hz": self.f_transition_model, "f_transition_data_hz": self.f_transition_data,
                "f_first_null_hz": self.f_first_null, "f_resonance_model_hz": self.f_resonance_model,
                "noise_floor_db": self.noise_floor_db, "warnings": self.warnings,
                "curves": {"f_hz": self.f.tolist(), "a_corr_db": self.a.tolist(),
                           "zt_model_mag": np.abs(self.zt_model).tolist(), "zt_classic_mag": self.zt_classic.tolist(),
                           "zt_valid": self.zt_valid.tolist(), "a_env_db": _nanlist(self.a_env), "a_s_db": _nanlist(self.a_s)}}


def _nanlist(a):
    return [None if not np.isfinite(v) else float(v) for v in a]


def interp_cal_log(f: np.ndarray, f_cal: np.ndarray, a_cal: np.ndarray) -> np.ndarray:
    return np.interp(np.log(f), np.log(f_cal), a_cal)


def detect_transition(f: np.ndarray, k: np.ndarray, transition_db: float) -> tuple[float, float | None, float | None]:
    """(model transition frequency, first null of |K|, first resonance = first local maximum of |K|)."""
    ka = np.abs(k)
    kdb = 20 * np.log10(ka / ka[0])
    below = np.flatnonzero(kdb < -transition_db)
    f_t = float(f[below[0]]) if below.size else float(f[-1])
    mins, _ = find_peaks(-ka, prominence=0.3 * ka[0])
    f_null = float(f[mins[0]]) if mins.size else None
    maxs, _ = find_peaks(ka, prominence=0.1 * ka[0])
    f_res = float(f[maxs[0]]) if maxs.size else None
    return f_t, f_null, f_res


def envelope_lower(f: np.ndarray, a: np.ndarray, f_start: float, prominence_db: float,
                   window_hz: float) -> tuple[np.ndarray, np.ndarray]:
    """Lower envelope of the attenuation above ``f_start``.

    For every point the minimum of a(f) over a *centred* window of width
    ``window_hz`` (one resonance spacing of the outer circuit, v_2/(2 L_c))
    is taken - but only where the window actually contains a standing-wave
    modulation (max - min >= prominence); where the curve is smooth the
    envelope is the curve itself.  This is the frequency-domain, centred
    version of the legacy sliding minimum: the window no longer depends on
    the number of sweep points and no longer lags in frequency.
    Returns (envelope with nan below f_start, mask of window-minimum points)."""
    env = np.full(f.size, np.nan)
    knots = np.zeros(f.size, bool)
    idx = np.flatnonzero(f >= f_start)
    if idx.size < 4:
        return env, knots
    half = window_hz / 2
    for i in idx:
        lo = np.searchsorted(f, f[i] - half)
        hi = np.searchsorted(f, f[i] + half, side="right")
        seg = a[lo:hi]
        if seg.max() - seg.min() >= prominence_db:
            env[i] = seg.min()
            knots[i] = True
        else:
            env[i] = a[i]
    return env, knots


def evaluate(meas: Measurement, fixture: FixtureProfile, settings: Settings | None = None) -> Evaluation:
    st = settings or Settings()
    f = meas.f
    a_meas = meas.a_db
    warnings: list[str] = []
    if meas.a_cal is not None:
        a_cal = interp_cal_log(f, meas.f_cal, meas.a_cal)
    else:
        a_cal = np.zeros_like(f)
        warnings.append("no calibration run referenced; setup insertion loss not removed")
    a = a_meas - a_cal
    s21 = 10 ** (-a / 20) * (np.exp(1j * np.radians(meas.phase_deg)) if meas.phase_deg is not None else 1.0)
    # noise floor from the instrument specification; a data estimate (roughness of
    # the raw trace where it is very high) is used if it is *lower*
    rough = np.abs(np.diff(a_meas, prepend=a_meas[0]))
    hi = a_meas > 90
    noise_floor = st.noise_floor_db
    if hi.sum() > 5 and np.median(rough[hi]) > 3.0:
        noise_floor = min(noise_floor, float(np.percentile(a_meas[hi], 50)))
    near_noise = a_meas > noise_floor - st.noise_margin_db
    fix = fixture.physics
    k = coupling_function(fix, f)
    f_t, f_null, f_res = detect_transition(f, k, fixture.transition_db)
    # data-based cross-check: first standing-wave maximum of the coupling (minimum of
    # attenuation with prominence) above the model transition, compared with the
    # fixture model's first resonance
    mins, _ = find_peaks(-a, prominence=st.prominence_db)
    f_t_data = None
    if f_res is not None and mins.size:
        # the prominent attenuation minimum closest (in log f) to the predicted first resonance
        j = int(np.argmin(np.abs(np.log(f[mins] / f_res))))
        f_t_data = float(f[mins[j]])
        if not (0.7 * f_res <= f_t_data <= 1.4 * f_res):
            warnings.append(f"no standing-wave maximum near the fixture model's first resonance ({f_res / 1e6:.1f} MHz); "
                            f"closest prominent minimum of attenuation at {f_t_data / 1e6:.1f} MHz: check the fixture "
                            "profile / far-end connection")
    elif mins.size:
        cand = [i for i in mins if f[i] > 0.8 * f_t]
        f_t_data = float(f[cand[0]]) if cand else None
    # second cross-check: spacing of the standing-wave pattern vs the fixture's v_2 / (2 L_c)
    above = [i for i in mins if f[i] > 0.8 * f_t]
    if len(above) >= 3:
        sp_data = float(np.median(np.diff(f[above])))
        sp_model = fix.v2_rel * 299_792_458.0 / (2 * fix.length_m)
        if not (0.7 <= sp_data / sp_model <= 1.4):
            warnings.append(f"standing-wave spacing {sp_data / 1e6:.0f} MHz does not match the fixture's "
                            f"v2/(2 Lc) = {sp_model / 1e6:.0f} MHz: check the fixture profile")
    scale = 1.0 if fixture.per_metre else fix.length_m       # absolute Z_T for connectors
    zt_model = s21 / k * scale
    zt_classic = fix.r1 / fix.length_m * np.abs(s21) * scale
    valid = (np.abs(k) >= fixture.k_valid * np.abs(k[0]))
    if f_null is not None:
        valid &= f < f_null
    valid &= ~near_noise
    # envelope above the transition
    spacing = fix.v2_rel * 299_792_458.0 / (2 * fix.length_m)   # resonance spacing of the outer circuit
    env, knots = envelope_lower(f, a, f_t, st.prominence_db, st.envelope_window_hz or spacing)
    a_s = env + 10 * np.log10(fixture.k_norm * fixture.zs_norm / fix.z2)
    # summary
    def zt_at(f0):
        m = valid & (f > 0)
        i0 = int(np.argmin(np.abs(np.log(f / f0))))
        if m.sum() < 2 or f0 < f[m].min() or f0 > f[m].max() or not valid[i0]:
            return None                     # never bridge across a masked region
        return float(np.exp(np.interp(np.log(f0), np.log(f[m]), np.log(np.abs(zt_model[m])))) * 1e3)
    def zt_bound(f0):
        """Upper bound on Z_T at f0 when the reading is at the noise floor: the Z_T that would
        put the coupling exactly at the (floor - margin) level."""
        kk = np.interp(np.log(f0), np.log(f), np.abs(k))
        return float(10 ** (-(noise_floor - st.noise_margin_db - np.interp(np.log(f0), np.log(f), a_cal)) / 20) / kk * scale * 1e3)
    a_s_valid = a_s[np.isfinite(a_s)]
    summ = {"zt_1mhz_mohm": zt_at(1e6), "zt_10mhz_mohm": zt_at(10e6), "zt_30mhz_mohm": zt_at(30e6),
            "zt_10mhz_upper_bound_mohm": zt_bound(10e6),
            "zt_unit": fixture.zt_unit, "as_min_db": float(np.min(a_s_valid)) if a_s_valid.size else None,
            "as_min_at_hz": float(f[np.nanargmin(a_s)]) if a_s_valid.size else None,
            "f_transition_model_mhz": f_t / 1e6, "f_transition_data_mhz": None if f_t_data is None else f_t_data / 1e6,
            "f_resonance_model_mhz": None if f_res is None else f_res / 1e6,
            "n_valid_zt": int(valid.sum()), "n_near_noise": int(near_noise.sum())}
    lim = fixture.limits.get(st.limit_class, {})
    verdict = "PASS"
    key = "zt_10mhz_max_mohm_per_m" if fixture.per_metre else "zt_10mhz_max_mohm"
    if key in lim:
        v = summ["zt_10mhz_mohm"]
        if v is None:
            # at the noise floor: the measurement only gives an upper bound
            if summ["zt_10mhz_upper_bound_mohm"] <= lim[key]:
                warnings.append(f"Z_T at 10 MHz is below the measurement floor "
                                f"(< {summ['zt_10mhz_upper_bound_mohm']:.3f} {fixture.zt_unit}), which is inside the limit")
            else:
                verdict = "INCONCLUSIVE"
                warnings.append("Z_T at 10 MHz is at the measurement floor and the floor is above the limit")
        elif v > lim[key]:
            verdict = "FAIL"
    if "as_min_db" in lim:
        v = summ["as_min_db"]
        if v is None or v < lim["as_min_db"]:
            verdict = "FAIL" if verdict != "INCONCLUSIVE" else verdict
    if not lim:
        verdict = "NO LIMITS"
    if valid.sum() == 0:
        warnings.append("no valid transfer-impedance points: measurement at the noise floor or fixture mismatch")
    return Evaluation(meas.sample, fixture, f, a_meas, a_cal, a, s21, k, zt_model, zt_classic, valid, env, a_s,
                      f_t, f_t_data, f_null, f_res, noise_floor, near_noise, summ, verdict, warnings)
