"""DC circuit solving: ngspice is the reference, the python solver the fallback.

`solve(deck)` returns `(backend, node_voltages, element_currents)` -- the raw
material `World.solve()` wraps into a `CircuitResult`. Element keys are
lowercase SPICE element names (`vgpio17`, `dc4`); source currents follow the
SPICE sign convention, diode currents are positive forward.
"""

from __future__ import annotations

import os

from hwctl.circuit import ngspice, pysolver

Solution = tuple[str, dict[str, float], dict[str, float]]

__all__ = ["Solution", "ngspice", "pysolver", "solve"]


def solve(deck: str, prefer: str = "ngspice") -> Solution:
    """Solve `deck`, falling back to the python solver when ngspice is absent.

    `HWCTL_SOLVER=python|ngspice` overrides `prefer`.
    """
    choice = os.environ.get("HWCTL_SOLVER", prefer).lower()
    if choice == "ngspice" and ngspice.available():
        voltages, currents = ngspice.run_op(deck)
        return "ngspice", voltages, currents
    voltages, currents = pysolver.run_op(deck)
    return "python", voltages, currents
