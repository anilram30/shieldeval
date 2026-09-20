import json

import numpy as np
import pytest

from shieldeval.core import evaluate
from shieldeval.fixtures import list_fixtures, load_fixture
from shieldeval.io import read_measurement
from shieldeval.legacy import legacy_evaluate
from shieldeval.physics import BraidShield, Fixture, coupling_function


def test_coupling_function_low_frequency_limits():
    f = np.array([1e4, 1e5])
    short = Fixture("t", 0.5, z2=100.0)
    matched = Fixture("l", 0.5, z2=100.0, far_end="matched")
    assert np.allclose(np.abs(coupling_function(short, f)), 0.5 / 50, rtol=2e-3)
    assert np.allclose(np.abs(coupling_function(matched, f)), 0.5 / 100, rtol=2e-3)   # EMF splits over both terminations


def test_braid_model_has_minimum_and_inductive_rise():
    sh = BraidShield(5e-3, 0.15e-3, 0.5e-9)
    f = np.logspace(4, 9, 200)
    z = np.abs(sh.z_t(f))
    assert z[0] == pytest.approx(5e-3, rel=1e-3)
    assert z.min() < 1e-3 and z[-1] > 1.0


def test_all_fixture_profiles_load():
    ids = {fx.id for fx in list_fixtures()}
    assert ids >= {"TUBE500", "TUBE1000", "LINEINJ", "CONN"}
    assert load_fixture("CONN").per_metre is False and load_fixture("TUBE500").per_metre is True


def _truth(archive, name):
    man = json.loads((archive / "manifest.json").read_text())
    return BraidShield(**man["samples"][name]["shield"])


@pytest.mark.parametrize("name", ["S01_single_braid", "S04_loose_braid", "S05_thin_strands"])
def test_modern_zt_matches_truth_beyond_legacy_cutoff(archive, name):
    m = read_measurement(archive / "raw" / f"{name}.dat")
    fx = load_fixture(m.fixture_id)
    ev = evaluate(m, fx)
    zt_true = np.abs(_truth(archive, name).z_t(ev.f))
    v = ev.zt_valid
    assert ev.f[v].max() > 300e6                                  # far beyond the 30 MHz legacy cut-off
    err = np.abs(20 * np.log10(np.abs(ev.zt_model[v]) / zt_true[v]))
    assert np.median(err) < 0.3 and np.percentile(err, 90) < 1.0
    # summary within 3 % of the truth at 10 MHz
    z10 = np.abs(_truth(archive, name).z_t(np.array([1e7]))[0]) * 1e3
    assert abs(ev.summary["zt_10mhz_mohm"] / z10 - 1) < 0.03
    # legacy under-reads by its nearest-point-below quirk (Q8)
    leg = legacy_evaluate(str(archive / "raw" / f"{name}.dat"))
    assert leg.zt_10mhz < z10


def test_screening_attenuation_minimum_agrees_with_legacy(archive):
    for name in ["S01_single_braid", "S02_optimised_braid", "S04_loose_braid"]:
        m = read_measurement(archive / "raw" / f"{name}.dat")
        ev = evaluate(m, load_fixture("TUBE500"))
        leg = legacy_evaluate(str(archive / "raw" / f"{name}.dat"))
        assert abs(ev.summary["as_min_db"] - leg.as_min) < 0.05   # same global minimum, different envelope elsewhere


def test_noise_floor_gives_bound_not_number(archive):
    m = read_measurement(archive / "raw" / "S06_double_braid.dat")
    ev = evaluate(m, load_fixture("TUBE500"))
    assert ev.summary["zt_10mhz_mohm"] is None
    assert ev.summary["zt_10mhz_upper_bound_mohm"] < 5.0
    assert ev.verdict == "PASS" and any("floor" in w for w in ev.warnings)
    # the legacy tool reported the noise as a (flattering) number
    leg = legacy_evaluate(str(archive / "raw" / "S06_double_braid.dat"))
    assert leg.zt_10mhz is not None and leg.zt_10mhz < 0.5


def test_line_injection_needs_the_fixture_model(archive):
    m = read_measurement(archive / "raw" / "N02_optimised_lineinj.dat")
    ev = evaluate(m, load_fixture("LINEINJ"))
    zt_true = np.abs(_truth(archive, "N02_optimised_lineinj").z_t(ev.f))
    lf = (ev.f < 30e6) & ~ev.near_noise
    err_classic = np.abs(20 * np.log10(ev.zt_classic[lf] / zt_true[lf]))
    err_model = np.abs(20 * np.log10(np.abs(ev.zt_model[lf & ev.zt_valid]) / zt_true[lf & ev.zt_valid]))
    assert np.median(err_classic) > 5.0 and np.median(err_model) < 0.5


def test_connector_absolute_units(archive):
    m = read_measurement(archive / "raw" / "N03_connector.dat")
    fx = load_fixture("CONN")
    ev = evaluate(m, fx)
    z10 = np.abs(_truth(archive, "N03_connector").z_t(np.array([1e7]))[0]) * fx.physics.length_m * 1e3
    assert fx.zt_unit == "mOhm" and abs(ev.summary["zt_10mhz_mohm"] / z10 - 1) < 0.02


def test_fixture_mismatch_is_flagged(archive):
    """Evaluating a TUBE1000 measurement with the TUBE500 profile: the resonance cross-check fires."""
    m = read_measurement(archive / "raw" / "N01_single_braid_tube1000.dat")
    ev = evaluate(m, load_fixture("TUBE500"))
    assert any("check the fixture profile" in w for w in ev.warnings)
