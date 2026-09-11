"""Smoke test: the reference LED deck from docs/01-architecture.md lights the LED."""

import re
import shutil
import subprocess
import tempfile

import pytest

DECK = """* GPIO17 -> 330R -> red LED -> GND
.model LED_RED D(IS=1e-18 N=1.8 RS=1 BV=5 CJO=10p)
Vgpio17 n_gpio17 0 DC {vgpio}
Rgpio17 n_gpio17 R5L 40
R1 R5L R9L 330
D1 R9L R12L LED_RED
Rj R12L 0 0.01
.control
op
print i(Vgpio17)
quit
.endc
.end
"""


def led_current_ma(vgpio: float) -> float:
    with tempfile.NamedTemporaryFile("w", suffix=".cir", delete=False) as f:
        f.write(DECK.format(vgpio=vgpio))
    out = subprocess.run(
        ["ngspice", "-b", f.name], capture_output=True, text=True, check=True
    ).stdout
    m = re.search(r"i\(vgpio17\)\s*=\s*([-+0-9.e]+)", out)
    assert m, out
    return -float(m.group(1)) * 1000


@pytest.mark.ngspice
@pytest.mark.skipif(shutil.which("ngspice") is None, reason="ngspice not installed")
def test_led_on_off():
    assert led_current_ma(3.3) > 1.0
    assert led_current_ma(0.0) < 0.01
