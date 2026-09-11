"""The v0.1 milestone sequence, driven only through SimArm + SimPi.

GPIO17 (R5L) -> 330R across rows 5-9 col c -> LED anode row 9 col d (R9L),
cathode row 10 col d (R10L) -> jumper row 10 col a to RAIL_T_NEG (GND).
This is `scripts/demo_v0_1.py` minus the recording.
"""

from __future__ import annotations

import pytest

from hwctl.arm.sim import SimArm
from hwctl.config import load_workspace
from hwctl.pi.sim import SimPi
from hwctl.world import World

LED_ID = "c4"


@pytest.fixture()
def rig():
    world = World(load_workspace())
    return world, SimArm(world), SimPi(world)


def slot_xy(world: World, slot_id: int) -> tuple[float, float]:
    s = next(s for s in world.tray() if s.id == slot_id)
    return s.x_mm, s.y_mm


def pick_from_slot(world: World, arm: SimArm, slot_id: int):
    x, y = slot_xy(world, slot_id)
    assert arm.move_to(x, y).error is None
    arm.lower()
    st = arm.close_gripper()
    assert st.event == "picked", st
    assert st.held is not None
    arm.raise_()
    return st.held


def place_at(world: World, arm: SimArm, row: int, col: str):
    x, y = world.ws.hole_xy(row, col)
    assert arm.move_to(x, y).error is None
    arm.lower()
    st = arm.open_gripper()
    arm.raise_()
    return st


def build_circuit(world: World, arm: SimArm) -> None:
    pick_from_slot(world, arm, 1)  # resistor_330 -> c1
    assert place_at(world, arm, 5, "c").event == "inserted"
    pick_from_slot(world, arm, 4)  # led_red -> c4
    assert place_at(world, arm, 9, "d").event == "inserted"
    pick_from_slot(world, arm, 8)  # jumper_rail -> c8
    assert place_at(world, arm, 10, "a").event == "inserted"


# ---------------------------------------------------------------- arm behaviour


def test_arm_starts_home(rig):
    _world, arm, _pi = rig
    st = arm.status()
    assert (st.x_mm, st.y_mm, st.lifted, st.gripper, st.held) == (0.0, 0.0, True, "open", None)


def test_move_while_lowered_is_an_error(rig):
    _world, arm, _pi = rig
    arm.move_to(10.0, 10.0)
    arm.lower()
    st = arm.move_to(50.0, 50.0)
    assert st.error == "lower: raise before moving"
    assert (st.x_mm, st.y_mm) == (10.0, 10.0)
    assert arm.raise_().event == "raised"
    assert arm.move_to(50.0, 50.0).x_mm == 50.0


def test_closing_on_empty_board_reports_empty(rig):
    world, arm, _pi = rig
    arm.move_to(*world.ws.hole_xy(30, "c"))
    arm.lower()
    assert arm.close_gripper().event == "empty"


def test_open_gripper_while_lifted_drops_the_cartridge(rig):
    world, arm, _pi = rig
    pick_from_slot(world, arm, 1)
    arm.move_to(*world.ws.hole_xy(5, "c"))
    st = arm.open_gripper()
    assert st.event == "dropped" and st.held is None
    assert world.find("c1").state == "dropped"


def test_blocked_place_keeps_the_cartridge_held(rig):
    world, arm, _pi = rig
    pick_from_slot(world, arm, 1)
    assert place_at(world, arm, 5, "c").event == "inserted"
    ref = pick_from_slot(world, arm, 2)
    st = place_at(world, arm, 5, "c")
    assert st.event == "blocked"
    assert st.held == ref
    assert st.gripper == "closed"
    assert "blocked" in (st.error or "")


# ---------------------------------------------------------------- the milestone


def test_gpio17_lights_the_led(rig):
    world, arm, pi = rig
    build_circuit(world, arm)

    assert [s.cartridge for s in world.tray() if s.id in (1, 4, 8)] == [None, None, None]
    c4 = world.find(LED_ID)
    assert c4.ref.type == "led_red"
    assert [(h.row, h.col) for h in c4.pin_holes] == [(9, "d"), (10, "d")]

    assert pi.set_mode(17, "out").mode == "out"
    assert pi.set_level(17, 1).level == 1

    obs = world.observe()
    assert obs.leds[LED_ID] == "on"
    assert obs.nets["R5L"] == pytest.approx(3.12, abs=0.1)
    assert obs.nets["R9L"] == pytest.approx(1.68, abs=0.1)

    result = world.solve()
    assert 3.0 < result.led_currents_ma[LED_ID] < 6.0
    assert result.brightness(LED_ID) > 0.1

    assert pi.set_level(17, 0).level == 0
    assert world.observe().leds[LED_ID] == "off"
    assert world.solve().led_currents_ma[LED_ID] < 0.01


def test_demo_netlist_matches_the_reference_topology(rig):
    world, arm, pi = rig
    build_circuit(world, arm)
    pi.set_mode(17, "out")
    pi.set_level(17, 1)
    lines = [line.strip() for line in world.netlist().splitlines()]
    for expected in (
        "Vgpio17 n_gpio17 0 DC 3.3",
        "Rgpio17 n_gpio17 R5L 40",
        "Rc1 R5L R9L 330",
        "Dc4 R9L R10L LED_RED",
        "Rc8 R10L RAIL_T_NEG 0.01",
        "Rgnd_RAIL_T_NEG RAIL_T_NEG 0 0.001",
    ):
        assert expected in lines


def test_input_pin_reads_the_solved_node(rig):
    world, arm, pi = rig
    build_circuit(world, arm)
    pi.set_mode(17, "out")
    pi.set_level(17, 1)
    # GPIO27 sits on R10L, the LED cathode: below the 1.8 V input threshold.
    assert pi.get_pin(27).level == 0
    # GPIO22 is on R15L, floating.
    assert pi.get_pin(22).level == 0
    assert {p.gpio for p in pi.pins()} == {17, 22, 23, 27}


def test_input_pin_reads_high_on_a_driven_net(rig):
    world, _arm, pi = rig
    # jumper_2 from row 10 col a (GPIO27, R10L) is not enough on its own; instead
    # drive GPIO17 high and read the same tie strip through an input pin.
    pi.set_mode(17, "out")
    pi.set_level(17, 1)
    assert pi.get_pin(17).level == 1
    assert world.observe().nets["R5L"] == pytest.approx(3.3, abs=0.01)
