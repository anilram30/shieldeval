# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.0.0] — 2026-09-18

The version number continues the lineage of the legacy tool this package replaces (`shieldeval_v3`),
so that a result can be attributed to a named method version rather than to "the old script".

### Added
- `shieldeval demo`: the legacy equivalence proof and the modern validation, end to end.
- `shieldeval.legacy`: a step-by-step reconstruction of the v3 method with its quirk register Q1–Q9,
  producing byte-identical output on the archived result set.
- `shieldeval.modern`: the modern method — full triaxial and line-injection models, proper coupling
  transfer function, correct termination handling and an uncertainty budget.
- `shieldeval.compare`: quantitative comparison of the two methods across the archive, so the cost of
  migrating from v3 is a number rather than an argument.
- Archive of raw measurement and calibration files with a manifest recording the shield parameters
  that generated them, replay of the legacy results, CLI, reports, 13 tests and a 10-page technical
  report.
