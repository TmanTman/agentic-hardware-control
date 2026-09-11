"""The two DC solvers on the reference deck from docs/01-architecture.md."""

from __future__ import annotations

import pytest

from hwctl.circuit import ngspice, pysolver

DECK = """* GPIO17 -> 330R -> red LED -> GND
.model LED_RED D(IS=1e-18 N=1.8 RS=1 BV=5 CJO=10p)
Vgpio17 n_gpio17 0 DC {vgpio}
Rgpio17 n_gpio17 R5L 40
R1 R5L R9L 330
D1 R9L R12L LED_RED
Rj R12L 0 0.01
Rtie_R5L R5L 0 1G
Rtie_R9L R9L 0 1G
Rtie_R12L R12L 0 1G
.control
op
print v(R5L) v(R9L) v(R12L)
print i(Vgpio17)
print @D1[id]
quit
.endc
.end
"""

needs_ngspice = pytest.mark.skipif(not ngspice.available(), reason="ngspice not installed")


def deck(vgpio: float) -> str:
    return DECK.format(vgpio=vgpio)


# ---------------------------------------------------------------- value parsing


@pytest.mark.parametrize(
    ("token", "expected"),
    [("330", 330.0), ("1k", 1e3), ("1G", 1e9), ("10p", 1e-11), ("0.01", 0.01), ("1e-18", 1e-18)],
)
def test_parse_value(token, expected):
    assert pysolver.parse_value(token) == pytest.approx(expected)


def test_parse_deck_reads_the_model():
    d = pysolver.parse_deck(deck(3.3))
    model = d.models["led_red"]
    assert (model.is_, model.n, model.rs) == (1e-18, 1.8, 1.0)
    assert len(d.resistors) == 6
    assert len(d.sources) == 1
    assert len(d.diodes) == 1


# ---------------------------------------------------------------- python solver


def test_python_solver_lights_the_led():
    volts, currents = pysolver.run_op(deck(3.3))
    led_ma = currents["d1"] * 1000
    assert 3.0 < led_ma < 6.0
    assert volts["R9L"] - volts["R12L"] == pytest.approx(1.68, abs=0.05)
    # the source sinks what the LED draws (SPICE sign convention)
    assert currents["vgpio17"] == pytest.approx(-currents["d1"], rel=1e-3)


def test_python_solver_off():
    _volts, currents = pysolver.run_op(deck(0.0))
    assert abs(currents["d1"]) * 1000 < 0.01


def test_python_solver_hides_the_internal_rs_node():
    volts, _ = pysolver.run_op(deck(3.3))
    assert not any("#" in name for name in volts)


# ---------------------------------------------------------------- ngspice


@pytest.mark.ngspice
@needs_ngspice
def test_ngspice_lights_the_led():
    volts, currents = ngspice.run_op(deck(3.3))
    assert 3.0 < currents["d1"] * 1000 < 6.0
    assert volts["R5L"] == pytest.approx(3.12, abs=0.05)


@pytest.mark.ngspice
@needs_ngspice
def test_ngspice_off():
    _volts, currents = ngspice.run_op(deck(0.0))
    assert abs(currents["d1"]) * 1000 < 0.01


@pytest.mark.ngspice
@needs_ngspice
def test_solvers_agree_within_ten_percent():
    nv_ng, ic_ng = ngspice.run_op(deck(3.3))
    nv_py, ic_py = pysolver.run_op(deck(3.3))
    assert ic_py["d1"] == pytest.approx(ic_ng["d1"], rel=0.10)
    for net in ("R5L", "R9L"):
        assert nv_py[net] == pytest.approx(nv_ng[net], rel=0.10)


# ---------------------------------------------------------------- dispatch


def test_solve_honours_the_solver_override(monkeypatch):
    from hwctl import circuit

    monkeypatch.setenv("HWCTL_SOLVER", "python")
    backend, _volts, currents = circuit.solve(deck(3.3))
    assert backend == "python"
    assert currents["d1"] * 1000 > 1.0


def test_solve_falls_back_when_ngspice_is_missing(monkeypatch):
    from hwctl import circuit

    monkeypatch.delenv("HWCTL_SOLVER", raising=False)
    monkeypatch.setattr(circuit.ngspice, "available", lambda: False)
    backend, _volts, _currents = circuit.solve(deck(3.3))
    assert backend == "python"
