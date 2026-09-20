# shieldeval — legacy algorithm reconstruction

**Reconstructs a legacy-style cable-shielding tool from its outputs bit-for-bit, then modernises it.**

[![CI](https://github.com/anilram30/shieldeval/actions/workflows/ci.yml/badge.svg)](https://github.com/anilram30/shieldeval/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-13%20passing-brightgreen)](tests/)
[![Report](https://img.shields.io/badge/report-10%20pages-informational)](docs/report.pdf)

> **Part of the [HF cable toolchain](https://github.com/anilram30/hf-cable-toolchain)** — seven packages that take a high-frequency cable from a raw measurement to a predicted Ethernet link.
> 
> [A · cablecheck](https://github.com/anilram30/cablecheck)  ·  [B · labauto](https://github.com/anilram30/labauto)  ·  **C · shieldeval**  ·  [D · zprofile](https://github.com/anilram30/zprofile)  ·  [E · cableanalytics](https://github.com/anilram30/cableanalytics)  ·  [F · labplatform](https://github.com/anilram30/labplatform)  ·  [G · linktwin](https://github.com/anilram30/linktwin)

---

## The problem it solves

Every engineering department has one: a decades-old tool that everybody depends on, that nobody fully understands, and that cannot be replaced because its numbers are written into existing specifications. `shieldeval` is the disciplined way through that problem. The legacy method is reconstructed and reproduced exactly, so old results stay reproducible; a modern method is implemented alongside it with the physics the old one approximated; and the two are compared quantitatively so the cost of migrating is a number rather than an argument.

## At a glance

|  |  |
|---|---|
| **Takes** | Archived raw triaxial and line-injection measurement files |
| **Produces** | Transfer impedance and screening attenuation by both the legacy and the modern method, with the difference quantified |
| **Checked against** | Byte-identical reproduction of the legacy tool's archived results, and the modern method against analytic shield physics |
| **Technical report** | [`docs/report.pdf`](docs/report.pdf) — 10 pages, 8 references, every method stated with its mathematics and its limitations |
| **Tests** | 13, run against Python 3.11, 3.12 and 3.13 on every push |
| **Data** | Entirely synthetic. No proprietary or customer measurements are used anywhere in this toolchain. |

## Install

Python 3.11 or newer.

```sh
pip install "git+https://github.com/anilram30/shieldeval.git"
```

---

## Background

**Honesty note.** The real legacy program and archive were not available; `legacy/shieldeval_v3.py`
is a stand-in written for this project in the style of a 2016 script (with realistic quirks), and
`archive/` was produced by running it on synthetic raw files generated from the physics in
`shieldeval.physics`. The *method* — characterisation tests, byte-exact compatibility mode, quirk
register, then extension by fixture profiles — is the deliverable.

## What is in the box

| piece | purpose |
|---|---|
| `legacy/shieldeval_v3.py` | the (stand-in) legacy tool, read-only |
| `archive/raw/*.dat`, `archive/raw/*.cal`, `archive/results_v3/*.res` | archived raw files and legacy results; `manifest.json` records the shield parameters that generated them |
| `shieldeval.legacy` | step-by-step re-implementation of v3 with the quirk register Q1–Q9; **byte-identical** output |
| `shieldeval.physics` | coupling function `K(f)` of a fixture (short-circuited tube or matched injection line), braid transfer-impedance model |
| `shieldeval.fixtures` + `fixtures/*.toml` | fixture profiles: TUBE500 (legacy), TUBE1000, LINEINJ, CONN (new) |
| `shieldeval.core` | modern evaluation: log-f calibration, model/data regime detection with cross-checks, model-based `Z_T = S21/K` far beyond the classic cut-off, centred-window envelope, `a_S` normalisation, noise-floor bounds, PASS/FAIL/INCONCLUSIVE |
| `shieldeval.report`, `shieldeval.validate` | HTML report with figures; validation against the generating model |
| `shieldeval.cli` | `shieldeval evaluate | legacy | compare | validate | fixtures` |

## Install and test

```bash
pip install -e ".[dev]"
pytest              # 20 tests incl. byte-exact reproduction of every archived result
```

## Use

```bash
shieldeval compare archive/                              # 6/6 archived results reproduced byte for byte
shieldeval legacy archive/raw/S01_single_braid.dat       # compatibility mode (identical to the old tool)
shieldeval evaluate archive/raw/*.dat --with-legacy --out out/   # modern evaluation, HTML + JSON per file
shieldeval evaluate new.dat --fixture TUBE1000           # a newer fixture: just a profile
shieldeval validate --archive archive --out validation/  # modern vs truth, legacy vs truth
shieldeval fixtures
```

Python:

```python
from shieldeval import read_measurement, load_fixture, evaluate, legacy_evaluate
m = read_measurement("archive/raw/S02_optimised_braid.dat")
ev = evaluate(m, load_fixture(m.fixture_id))
ev.summary, ev.verdict, ev.warnings          # Z_T at 1/10/30 MHz, upper bound at the floor, a_S,min, transitions
legacy_evaluate("archive/raw/S02_optimised_braid.dat").text   # the old tool's exact text
```

## Documentation

`docs/report.md` / `docs/report.pdf`: physics (coupling function, braid model), the quirk
register with numbers, the equivalence proof, the modern evaluation, validation tables and
figures, limitations.
---

## Contributing

Bug reports, questions about the methods, and pull requests are all welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md). Numerical changes need a numerical test, and a change to a method
is also a change to `docs/report.md`.

## Licence and attribution

MIT — see [LICENSE](LICENSE). Author: Sreeram Anil.

Built with AI assistance; the commit history records it. The engineering decisions, the validation
strategy and the limitations stated in the report are the substance of the work.

Part of the **[HF cable toolchain](https://github.com/anilram30/hf-cable-toolchain)** · [Report an issue](https://github.com/anilram30/shieldeval/issues) ·
[Changelog](CHANGELOG.md)
