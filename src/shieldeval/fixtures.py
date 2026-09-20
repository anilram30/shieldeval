"""Fixture profiles (TOML): physics of the setup, evaluation constants, limits."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from .physics import Fixture

__all__ = ["FixtureProfile", "load_fixture", "list_fixtures"]


@dataclass
class FixtureProfile:
    id: str
    title: str
    method: str
    status: str
    physics: Fixture
    zs_norm: float = 150.0
    k_norm: float = 2.0
    k_valid: float = 0.25
    transition_db: float = 1.0
    legacy: dict = field(default_factory=dict)
    limits: dict = field(default_factory=dict)
    path: str = ""

    @property
    def per_metre(self) -> bool:
        return self.physics.per_metre

    @property
    def zt_unit(self) -> str:
        return "mOhm/m" if self.per_metre else "mOhm"


def _dir() -> Path:
    return Path(str(resources.files("shieldeval") / "fixtures"))


def list_fixtures(extra_dirs: list[str | Path] | None = None) -> list[FixtureProfile]:
    out = []
    for d in [_dir()] + [Path(x) for x in (extra_dirs or [])]:
        if d.is_dir():
            for p in sorted(d.glob("*.toml")):
                out.append(load_fixture(p))
    return out


def load_fixture(ident: str | Path, extra_dirs: list[str | Path] | None = None) -> FixtureProfile:
    p = Path(ident)
    if not p.is_file():
        for d in [_dir()] + [Path(x) for x in (extra_dirs or [])]:
            c = d / f"{ident}.toml"
            if c.is_file():
                p = c
                break
        else:
            raise FileNotFoundError(f"fixture profile {ident!r} not found")
    doc = tomllib.loads(p.read_text())
    meta, ph, ev = doc["meta"], doc["physics"], doc.get("evaluation", {})
    fix = Fixture(name=meta["id"], length_m=ph["length_m"], z2=ph["z2"], v2_rel=ph.get("v2_rel", 1.0),
                  r1=ph.get("r1", 50.0), r2=ph.get("r2", 50.0), far_end=ph.get("far_end", "short"),
                  alpha2_np_per_m_at_1ghz=ph.get("alpha2_np_per_m_at_1ghz", 0.02), z1=ph.get("z1", 50.0),
                  v1_rel=ph.get("v1_rel", 0.66), alpha1_np_per_m_at_1ghz=ph.get("alpha1_np_per_m_at_1ghz", 0.15),
                  per_metre=ph.get("per_metre", True))
    return FixtureProfile(meta["id"], meta.get("title", meta["id"]), meta.get("method", ""), meta.get("status", ""),
                          fix, ev.get("zs_norm", 150.0), ev.get("k_norm", 2.0), ev.get("k_valid", 0.25),
                          ev.get("transition_db", 1.0), doc.get("legacy_v3", {}), doc.get("limits", {}), str(p))
