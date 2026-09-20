"""Figures and a self-contained HTML report for one evaluation (optionally with the legacy result and the truth)."""
from __future__ import annotations

import html
import io
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .core import Evaluation  # noqa: E402

C_MEAS, C_MOD, C_LEG, C_TRUE, C_ENV, C_GREY = "#2a78d6", "#008300", "#eb6834", "#0b0b0b", "#e34948", "#9a9a96"


def _style(ax):
    ax.grid(True, which="both", color="#e6e6e3", lw=0.7)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def figure(ev: Evaluation, legacy=None, zt_true=None):
    fig, axes = plt.subplots(2, 1, figsize=(9, 7.2))
    f = ev.f / 1e6
    ax = axes[0]
    ax.semilogx(f, ev.a_meas, color=C_GREY, lw=0.8, label="raw a_meas")
    ax.semilogx(f, ev.a, color=C_MEAS, lw=1.2, label="calibrated a")
    m = np.isfinite(ev.a_env)
    ax.semilogx(f[m], ev.a_env[m], color=C_ENV, lw=1.4, label="lower envelope (modern)")
    if legacy is not None:
        ax.semilogx(np.array(legacy.f) / 1e6, legacy.a_env, color=C_LEG, lw=1.0, ls="--", label="envelope (legacy v3 sliding min)")
    ax.axvline(ev.f_transition_model / 1e6, color=C_GREY, ls=":", lw=1)
    ax.text(ev.f_transition_model / 1e6, ax.get_ylim()[0] if False else np.nanmax(ev.a_meas), f" transition {ev.f_transition_model / 1e6:.0f} MHz", fontsize=8, va="top")
    if ev.f_resonance_model:
        ax.axvline(ev.f_resonance_model / 1e6, color=C_GREY, ls="-.", lw=1)
    ax.axhline(ev.noise_floor_db, color=C_GREY, lw=0.8, ls="--")
    ax.invert_yaxis()
    ax.set_ylabel("attenuation / dB")
    ax.set_title(f"{ev.sample} on {ev.fixture.id}: coupling attenuation", loc="left", fontsize=10)
    ax.legend(fontsize=8, frameon=False, loc="lower left")
    _style(ax)
    ax = axes[1]
    v = ev.zt_valid
    zv = np.where(v, np.abs(ev.zt_model) * 1e3, np.nan)
    ax.loglog(f, zv, color=C_MOD, lw=1.6, label="|Z_T| model-based (modern)")
    ax.loglog(f[~v], np.abs(ev.zt_model[~v]) * 1e3, ".", color=C_MOD, ms=2, alpha=0.4, label="masked (ill-conditioned / noise)")
    lf = f * 1e6 < ev.f_transition_model
    ax.loglog(f[lf], ev.zt_classic[lf] * 1e3, color=C_MEAS, lw=1.0, ls="--", label="|Z_T| classic formula (below transition)")
    if legacy is not None:
        lz = np.array([np.nan if z is None else z for z in legacy.zt_mohm])
        ax.loglog(np.array(legacy.f) / 1e6, lz, color=C_LEG, lw=1.0, ls=":", label="legacy v3")
    if zt_true is not None:
        ax.loglog(f, zt_true * 1e3, color=C_TRUE, lw=1.0, label="model truth")
    ax.set_xlabel("frequency / MHz")
    ax.set_ylabel(f"|Z_T| / {ev.fixture.zt_unit}")
    ax.legend(fontsize=8, frameon=False, loc="upper left")
    _style(ax)
    fig.tight_layout()
    return fig


def fig_svg(fig) -> str:
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def write_html(ev: Evaluation, path: str | Path, legacy=None, zt_true=None) -> Path:
    s = ev.summary
    e = lambda x: html.escape(str(x))
    rows = "".join(f"<tr><td>{e(k)}</td><td>{'–' if v is None else (f'{v:.4g}' if isinstance(v, float) else e(v))}</td></tr>"
                   for k, v in s.items())
    warn = "".join(f"<div class='warn'>{e(w)}</div>" for w in ev.warnings)
    css = ("body{font-family:Segoe UI,Helvetica,Arial,sans-serif;max-width:1000px;margin:auto;padding:24px;color:#0b0b0b}"
           "table{border-collapse:collapse;font-size:13px}td{padding:4px 10px;border-bottom:1px solid #e6e6e3}"
           ".v{font-size:26px;font-weight:700;color:#fff;display:inline-block;padding:4px 16px;border-radius:6px}"
           ".PASS{background:#008300}.FAIL{background:#e34948}.INCONCLUSIVE{background:#eda100}.NO{background:#52514e}"
           ".warn{background:#fff6e5;border-left:4px solid #eda100;padding:6px 10px;margin:6px 0;font-size:13px}.small{color:#52514e;font-size:12px}")
    body = (f"<h1>Shield evaluation — {e(ev.sample)}</h1><div class='small'>{e(ev.fixture.title)} · {e(ev.fixture.status)}</div>"
            f"<p><span class='v {ev.verdict.split()[0]}'>{e(ev.verdict)}</span></p>{warn}<h2>Summary</h2><table>{rows}</table>"
            f"<h2>Curves</h2>{fig_svg(figure(ev, legacy, zt_true))}"
            f"<h2>Fixture profile</h2><div class='small'>{e(ev.fixture.path)}</div>")
    if legacy is not None:
        body += f"<h2>Legacy v3 result (for comparison)</h2><pre class='small'>{e(legacy.text)}</pre>"
    Path(path).write_text(f"<!doctype html><html><head><meta charset='utf-8'><title>shieldeval {e(ev.sample)}</title>"
                          f"<style>{css}</style></head><body>{body}</body></html>", encoding="utf-8")
    return Path(path)
