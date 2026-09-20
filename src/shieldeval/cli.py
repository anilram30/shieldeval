"""Command line: ``shieldeval evaluate | legacy | compare | validate | fixtures``."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__


def _load(path, fixture_id=None, extra=None):
    from .fixtures import load_fixture
    from .io import read_measurement
    m = read_measurement(path)
    fx = load_fixture(fixture_id or m.fixture_id, extra)
    return m, fx


def cmd_evaluate(args):
    from .core import Settings, evaluate
    from .report import write_html
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rc = 0
    for p in args.files:
        m, fx = _load(p, args.fixture, args.fixture_dir)
        st = Settings(noise_floor_db=args.noise_floor, prominence_db=args.prominence, limit_class=args.limit_class)
        ev = evaluate(m, fx, st)
        legacy = None
        if args.with_legacy and fx.id == "TUBE500":
            from .legacy import legacy_evaluate
            legacy = legacy_evaluate(p)
        stem = out / Path(p).stem
        (stem.with_suffix(".json")).write_text(json.dumps(ev.to_dict(), indent=1))
        write_html(ev, stem.with_suffix(".html"), legacy)
        s = ev.summary
        z = s["zt_10mhz_mohm"]
        zt = f"{z:.3f}" if z is not None else f"< {s['zt_10mhz_upper_bound_mohm']:.3f} (floor)"
        print(f"{ev.sample:28s} {fx.id:8s} Z_T(10 MHz) {zt} {fx.zt_unit}  a_S,min {s['as_min_db']:.1f} dB  "
              f"transition {s['f_transition_model_mhz']:.0f} MHz  -> {ev.verdict}")
        for w in ev.warnings:
            print(f"    warning: {w}")
        rc |= 0 if ev.verdict == "PASS" else 1
    return rc


def cmd_legacy(args):
    from .legacy import legacy_evaluate
    r = legacy_evaluate(args.file)
    if args.out:
        Path(args.out).write_text(r.text)
    else:
        sys.stdout.write(r.text)
    return 0


def cmd_compare(args):
    """Byte-exact equivalence of the compatibility mode against archived v3 results."""
    from .legacy import legacy_evaluate
    raw, res = Path(args.archive) / "raw", Path(args.archive) / "results_v3"
    n_ok = n = 0
    for p in sorted(raw.glob("*.dat")):
        ref = res / (p.stem + ".res")
        if not ref.exists():
            continue
        n += 1
        same = legacy_evaluate(str(p)).text == ref.read_text()
        n_ok += same
        print(f"{p.stem:28s} {'IDENTICAL' if same else 'DIFFERS'}")
    print(f"{n_ok}/{n} archived results reproduced byte for byte")
    return 0 if n_ok == n else 1


def cmd_validate(args):
    from .validate import run_validation
    md = run_validation(args.archive, args.out)
    print(md)
    return 0


def cmd_demo(args):
    """Both halves of the project: byte-exact equivalence with the legacy tool, then the
    modern method validated against the physics that generated the archive."""
    from .validate import run_validation
    print("==> legacy compatibility: byte-exact equivalence against the archived v3 results")
    rc = cmd_compare(args)
    print("\n==> modern method against the generating model")
    print(run_validation(args.archive, args.out))
    return rc


def cmd_fixtures(args):
    from .fixtures import list_fixtures
    for fx in list_fixtures(args.fixture_dir):
        ph = fx.physics
        print(f"{fx.id:10s} {fx.method:15s} L={ph.length_m:g} m Z2={ph.z2:g} ohm far_end={ph.far_end:8s} "
              f"{'per metre' if fx.per_metre else 'absolute '}  {fx.status}")
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="shieldeval", description="Shield transfer impedance / screening attenuation evaluation")
    p.add_argument("--version", action="version", version=f"shieldeval {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("evaluate", help="modern evaluation of one or more raw files")
    a.add_argument("files", nargs="+"), a.add_argument("--fixture"), a.add_argument("--fixture-dir", action="append")
    a.add_argument("--noise-floor", type=float, default=105.0), a.add_argument("--prominence", type=float, default=3.0)
    a.add_argument("--limit-class", default="class_A"), a.add_argument("--with-legacy", action="store_true")
    a.add_argument("--out", default="shieldeval_out")
    a.set_defaults(func=cmd_evaluate)
    l = sub.add_parser("legacy", help="legacy v3 compatibility mode (byte-identical output)")
    l.add_argument("file"), l.add_argument("-o", "--out")
    l.set_defaults(func=cmd_legacy)
    c = sub.add_parser("compare", help="prove equivalence against an archive of v3 results")
    c.add_argument("archive")
    c.set_defaults(func=cmd_compare)
    v = sub.add_parser("validate", help="modern evaluation vs the generating model on the synthetic archive")
    v.add_argument("--archive", default="archive"), v.add_argument("--out", default="validation")
    v.set_defaults(func=cmd_validate)
    dm = sub.add_parser("demo", help="legacy equivalence proof and modern validation, end to end")
    dm.add_argument("out", nargs="?", default="demo_out")
    dm.add_argument("--archive", default="archive")
    dm.set_defaults(func=cmd_demo)

    x = sub.add_parser("fixtures", help="list fixture profiles")
    x.add_argument("--fixture-dir", action="append")
    x.set_defaults(func=cmd_fixtures)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
