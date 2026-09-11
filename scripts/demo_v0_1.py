"""v0.1.0 demo: a scripted (no LLM) build that lights an LED from GPIO17.

    uv run python scripts/demo_v0_1.py --record recordings/v0.1.0/

Picks a 330R resistor, places it at rows 5-9 (col c); picks a red LED, places
it at rows 9-10 (col d); places a rail jumper from row 10 to the GND rail;
drives GPIO17 high and asserts the LED is on via observe(); then low and off.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hwctl.session import Session

LED_ID = "c4"


def pick(s: Session, slot_id: int) -> None:
    slot = next(t for t in s.ws.tray if t.id == slot_id)
    s.call("arm", "move_to", x_mm=slot.x_mm, y_mm=slot.y_mm)
    s.call("arm", "lower")
    st = s.call("arm", "close_gripper")
    assert st.event == "picked", st
    s.call("arm", "raise_")


def place(s: Session, row: int, col: str) -> None:
    x, y = s.ws.hole_xy(row, col)
    s.call("arm", "move_to", x_mm=x, y_mm=y)
    s.call("arm", "lower")
    st = s.call("arm", "open_gripper")
    assert st.event == "inserted", st
    s.call("arm", "raise_")


def run(record_dir: str | None) -> None:
    s = Session(record_dir=record_dir, name="led-from-gpio17")
    s.hold("start: empty board, full tray")

    pick(s, 1)  # resistor_330
    place(s, 5, "c")  # pins at R5L (GPIO17) and R9L
    pick(s, 4)  # led_red
    place(s, 9, "d")  # anode R9L, cathode R10L
    pick(s, 8)  # jumper_rail
    place(s, 10, "a")  # R10L -> RAIL_T_NEG (GND)

    s.call("pi", "set_mode", gpio=17, mode="out")
    s.call("pi", "set_level", gpio=17, level=1)
    obs = s.call("observe", "observe")
    assert obs.leds[LED_ID] == "on", obs
    s.hold(f"GPIO17 high: LED {LED_ID} on ({obs.backend})", frames=3)

    s.call("pi", "set_level", gpio=17, level=0)
    obs = s.call("observe", "observe")
    assert obs.leds[LED_ID] == "off", obs
    s.hold(f"GPIO17 low: LED {LED_ID} off", frames=3)

    s.call("pi", "set_level", gpio=17, level=1)
    obs = s.call("observe", "observe")
    assert obs.leds[LED_ID] == "on", obs
    s.hold(f"GPIO17 high again: LED {LED_ID} on", frames=3)

    gif = s.close()
    print(f"ok: LED {LED_ID} toggles with GPIO17 (backend={obs.backend})")
    if gif is not None:
        print(f"recording: {gif} ({gif.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", default=None, help="directory to write the gif + commands.jsonl")
    run(ap.parse_args().record)
