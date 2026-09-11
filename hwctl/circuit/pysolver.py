"""Pure-Python DC operating-point solver (the fallback when ngspice is absent).

Handles the subset of SPICE the world emits: resistors, DC voltage sources and
diodes with a Shockley model (IS, N, RS). Modified nodal analysis plus
Newton-Raphson with the classic pn-junction voltage limiting so it converges
from a cold (all-zero) start.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import numpy as np

VT = 0.025852
"""Thermal voltage at 300.15 K (ngspice's TNOM = 27 C)."""

GMIN = 1e-12
MAX_ITER = 500
V_TOL = 1e-9

_SUFFIX = {
    "f": 1e-15,
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "m": 1e-3,
    "k": 1e3,
    "meg": 1e6,
    "g": 1e9,
    "t": 1e12,
}
_NUM = re.compile(r"^([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*([a-zA-Z]*)$")


def parse_value(token: str) -> float:
    """SPICE number with an optional engineering suffix (`330`, `1k`, `1G`, `10p`)."""
    m = _NUM.match(token.strip())
    if not m:
        raise ValueError(f"not a SPICE value: {token!r}")
    mantissa, suffix = float(m.group(1)), m.group(2).lower()
    if not suffix:
        return mantissa
    if suffix.startswith("meg"):
        return mantissa * _SUFFIX["meg"]
    return mantissa * _SUFFIX.get(suffix[0], 1.0)


@dataclass
class DiodeModel:
    name: str
    is_: float = 1e-14
    n: float = 1.0
    rs: float = 0.0


@dataclass
class Deck:
    resistors: list[tuple[str, str, str, float]] = field(default_factory=list)
    sources: list[tuple[str, str, str, float]] = field(default_factory=list)
    diodes: list[tuple[str, str, str, str]] = field(default_factory=list)
    models: dict[str, DiodeModel] = field(default_factory=dict)


_MODEL = re.compile(r"^\.model\s+(\S+)\s+d\s*\((.*)\)\s*$", re.IGNORECASE | re.DOTALL)


def parse_deck(deck: str) -> Deck:
    """Tiny SPICE reader: R / V / D element lines and `.model ... D(...)`."""
    out = Deck()
    for raw in deck.splitlines():
        line = raw.split(";")[0].strip()
        if not line or line.startswith("*"):
            continue
        low = line.lower()
        if low.startswith(".model"):
            m = _MODEL.match(line)
            if not m:
                continue
            model = DiodeModel(name=m.group(1))
            for key, value in re.findall(r"(\w+)\s*=\s*([^\s,]+)", m.group(2)):
                key = key.lower()
                if key == "is":
                    model.is_ = parse_value(value)
                elif key == "n":
                    model.n = parse_value(value)
                elif key == "rs":
                    model.rs = parse_value(value)
            out.models[model.name.lower()] = model
            continue
        if line.startswith("."):
            continue
        parts = line.split()
        kind = parts[0][0].upper()
        if kind == "R" and len(parts) >= 4:
            out.resistors.append((parts[0].lower(), parts[1], parts[2], parse_value(parts[3])))
        elif kind == "V" and len(parts) >= 4:
            tail = [p for p in parts[3:] if p.lower() != "dc"]
            out.sources.append((parts[0].lower(), parts[1], parts[2], parse_value(tail[0])))
        elif kind == "D" and len(parts) >= 4:
            out.diodes.append((parts[0].lower(), parts[1], parts[2], parts[3].lower()))
    return out


def _limit(vnew: float, vold: float, vt: float, vcrit: float) -> float:
    """Berkeley SPICE pnjlim: damp the diode step so Newton cannot overshoot."""
    if vnew > vcrit and abs(vnew - vold) > 2 * vt:
        if vold > 0.0:
            arg = 1.0 + (vnew - vold) / vt
            return vold + vt * math.log(arg) if arg > 0 else vcrit
        return vt * math.log(max(vnew, vt) / vt)
    return vnew


def _exp(x: float) -> float:
    return math.exp(min(x, 80.0))


def solve_deck(deck: str) -> tuple[dict[str, float], dict[str, float]]:
    """Operating point of `deck`.

    Returns `(node_voltages, element_currents)`; element keys are lowercase.
    Source currents follow the SPICE sign convention (into the `+` terminal);
    diode currents are positive in the forward (anode -> cathode) direction.
    """
    d = parse_deck(deck)

    names: list[str] = []
    index: dict[str, int] = {}

    def node(name: str) -> int:
        if name == "0":
            return -1
        if name not in index:
            index[name] = len(names)
            names.append(name)
        return index[name]

    for _, a, b, _ in d.resistors:
        node(a), node(b)
    for _, a, b, _ in d.sources:
        node(a), node(b)
    # A diode with series resistance gets an internal node between RS and the junction.
    junction: list[tuple[str, int, int, DiodeModel]] = []
    for name, a, k, model_name in d.diodes:
        model = d.models.get(model_name, DiodeModel(model_name))
        na, nk = node(a), node(k)
        if model.rs > 0:
            mid = node(f"{name}#internal")
            junction.append((name, na, mid, model))
            d.resistors.append((f"{name}#rs", f"{name}#internal", k, model.rs))
        else:
            junction.append((name, na, nk, model))

    n = len(names)
    m = len(d.sources)
    size = n + m
    if size == 0:
        return {}, {}

    x = np.zeros(size)
    vd = [0.0] * len(junction)

    for _ in range(MAX_ITER):
        A = np.zeros((size, size))
        z = np.zeros(size)

        for _, a, b, ohm in d.resistors:
            g = 1.0 / ohm if ohm != 0 else 1e12
            ia, ib = index.get(a, -1) if a != "0" else -1, index.get(b, -1) if b != "0" else -1
            if ia >= 0:
                A[ia, ia] += g
            if ib >= 0:
                A[ib, ib] += g
            if ia >= 0 and ib >= 0:
                A[ia, ib] -= g
                A[ib, ia] -= g

        for k, (_, a, b, volts) in enumerate(d.sources):
            r = n + k
            ia = index.get(a, -1) if a != "0" else -1
            ib = index.get(b, -1) if b != "0" else -1
            if ia >= 0:
                A[ia, r] += 1.0
                A[r, ia] += 1.0
            if ib >= 0:
                A[ib, r] -= 1.0
                A[r, ib] -= 1.0
            z[r] = volts

        for k, (_, ia, ib, model) in enumerate(junction):
            vt = model.n * VT
            i_d = model.is_ * (_exp(vd[k] / vt) - 1.0)
            gd = model.is_ / vt * _exp(vd[k] / vt) + GMIN
            ieq = i_d - gd * vd[k]
            if ia >= 0:
                A[ia, ia] += gd
                z[ia] -= ieq
            if ib >= 0:
                A[ib, ib] += gd
                z[ib] += ieq
            if ia >= 0 and ib >= 0:
                A[ia, ib] -= gd
                A[ib, ia] -= gd

        try:
            x_new = np.linalg.solve(A, z)
        except np.linalg.LinAlgError:
            x_new = np.linalg.lstsq(A, z, rcond=None)[0]

        converged = bool(np.max(np.abs(x_new - x)) < V_TOL)
        for k, (_, ia, ib, model) in enumerate(junction):
            vt = model.n * VT
            vcrit = vt * math.log(vt / (math.sqrt(2.0) * model.is_))
            raw = (x_new[ia] if ia >= 0 else 0.0) - (x_new[ib] if ib >= 0 else 0.0)
            limited = _limit(raw, vd[k], vt, vcrit)
            if abs(limited - vd[k]) > V_TOL:
                converged = False
            vd[k] = limited
        x = x_new
        if converged:
            break

    voltages = {name: float(x[i]) for i, name in enumerate(names) if "#internal" not in name}
    currents: dict[str, float] = {}
    for k, (name, _, _, _) in enumerate(d.sources):
        currents[name] = float(x[n + k])
    for k, (name, _, _, model) in enumerate(junction):
        vt = model.n * VT
        currents[name] = float(model.is_ * (_exp(vd[k] / vt) - 1.0))
    return voltages, currents


def available() -> bool:
    """Always true: this solver has no external dependency beyond numpy."""
    return True


def run_op(deck: str) -> tuple[dict[str, float], dict[str, float]]:
    """Same signature as `ngspice.run_op`."""
    return solve_deck(deck)
