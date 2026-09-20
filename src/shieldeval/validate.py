"""Validation of the modern evaluation (and the legacy one where it applies)
against the shield model that generated the synthetic archive."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .core import evaluate
from .fixtures import load_fixture
from .io import read_measurement
from .legacy import legacy_evaluate
from .physics import BraidShield
from .report import figure


def run_validation(archive: str | Path, out_dir: str | Path) -> str:
    archive, out = Path(archive), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    man = json.loads((archive / "manifest.json").read_text())
    rows = ["| sample | fixture | Z_T(10 MHz) true | legacy v3 | modern | modern err median / 90 % (dB), valid to | classic err median / 90 % below f_cut | a_S,min legacy / modern | verdict legacy / modern |",
            "|---|---|---|---|---|---|---|---|---|"]
    csv = ["sample,fixture,zt10_true,zt10_legacy,zt10_modern,zt10_bound,err_model_max_db,valid_to_mhz,err_classic_max_db,as_legacy,as_modern,verdict_legacy,verdict_modern"]
    import matplotlib.pyplot as plt
    for name, e in man["samples"].items():
        m = read_measurement(archive / "raw" / e["file"])
        fx = load_fixture(m.fixture_id)
        ev = evaluate(m, fx)
        sh = BraidShield(**e["shield"])
        scale = 1.0 if fx.per_metre else fx.physics.length_m
        zt_true = np.abs(sh.z_t(ev.f)) * scale
        v = ev.zt_valid
        err = 20 * np.log10(np.abs(ev.zt_model[v]) / zt_true[v]) if v.any() else np.array([np.nan])
        lf = (ev.f < fx.legacy.get("fcut_hz", ev.f_transition_model)) & ~ev.near_noise
        errc = 20 * np.log10(ev.zt_classic[lf] / zt_true[lf]) if lf.any() else np.array([np.nan])
        zt10_true = float(np.abs(sh.z_t(np.array([1e7]))[0]) * scale * 1e3)
        leg = legacy_evaluate(str(archive / "raw" / e["file"])) if fx.id == "TUBE500" else None
        s = ev.summary
        z_mod = s["zt_10mhz_mohm"]
        z_mod_s = f"{z_mod:.3f}" if z_mod is not None else f"< {s['zt_10mhz_upper_bound_mohm']:.3f} (floor)"
        rows.append(f"| {name} | {fx.id} | {zt10_true:.3f} | {leg.zt_10mhz if leg else float('nan'):.3f} | {z_mod_s} | "
                    f"{np.nanmedian(np.abs(err)):.2f} / {np.nanpercentile(np.abs(err), 90):.2f}, {ev.f[v].max() / 1e6 if v.any() else 0:.0f} MHz | "
                    f"{np.nanmedian(np.abs(errc)):.2f} / {np.nanpercentile(np.abs(errc), 90):.2f} | "
                    f"{leg.as_min if leg else float('nan'):.1f} / {s['as_min_db']:.1f} | {leg.verdict if leg else '–'} / {ev.verdict} |")
        csv.append(f"{name},{fx.id},{zt10_true},{leg.zt_10mhz if leg else ''},{z_mod if z_mod is not None else ''},"
                   f"{s['zt_10mhz_upper_bound_mohm']},{np.nanmax(np.abs(err))},{ev.f[v].max() / 1e6 if v.any() else 0},"
                   f"{np.nanmax(np.abs(errc))},{leg.as_min if leg else ''},{s['as_min_db']},{leg.verdict if leg else ''},{ev.verdict}")
        fig = figure(ev, leg, zt_true)
        fig.savefig(out / f"validation_{name}.png", dpi=130)
        plt.close(fig)
    md = "\n".join(rows)
    (out / "validation_table.md").write_text(md)
    (out / "validation_table.csv").write_text("\n".join(csv) + "\n")
    return md
