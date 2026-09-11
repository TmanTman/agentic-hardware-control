"""Placement physics and the netlist the world emits."""

from __future__ import annotations

import pytest

from hwctl.config import load_workspace
from hwctl.world import World


@pytest.fixture()
def world():
    return World(load_workspace())


def slot(world: World, slot_id: int):
    return next(s for s in world.tray() if s.id == slot_id)


def pick(world: World, slot_id: int):
    s = slot(world, slot_id)
    result, ref = world.try_pick(s.x_mm, s.y_mm)
    assert result == "picked"
    return ref


def test_pick_from_tray_empties_the_slot(world):
    assert slot(world, 1).cartridge == "resistor_330"
    ref = pick(world, 1)
    assert ref.id == "c1" and ref.type == "resistor_330"
    assert slot(world, 1).cartridge is None
    assert world.find("c1").state == "held"


def test_pick_over_nothing_is_empty(world):
    assert world.try_pick(200.0, 200.0) == ("empty", None)


def test_inserted_cartridges_cannot_be_picked(world):
    ref = pick(world, 1)
    x, y = world.ws.hole_xy(5, "c")
    assert world.try_place(ref, x, y)[0] == "inserted"
    assert world.try_pick(x, y) == ("empty", None)


def test_place_resistor_spans_rows_5_and_9(world):
    ref = pick(world, 1)
    x, y = world.ws.hole_xy(5, "c")
    result, holes = world.try_place(ref, x, y)
    assert result == "inserted"
    assert [(h.row, h.col) for h in holes] == [(5, "c"), (9, "c")]
    assert [world.ws.net_of(h.row, h.col) for h in holes] == ["R5L", "R9L"]
    placed = world.find("c1")
    assert placed.state == "inserted"
    assert (placed.pin0.row, placed.pin0.col) == (5, "c")


def test_place_off_by_one_millimetre_is_misaligned(world):
    ref = pick(world, 1)
    x, y = world.ws.hole_xy(5, "c")
    result, holes = world.try_place(ref, x + 1.0, y)
    assert result == "misaligned"
    assert holes == []
    placed = world.find("c1")
    assert placed.state == "dropped"
    assert placed.pin_holes == []
    assert placed.x_mm == pytest.approx(x + 1.0)


def test_a_dropped_cartridge_can_be_picked_up_again(world):
    ref = pick(world, 1)
    x, y = world.ws.hole_xy(5, "c")
    world.try_place(ref, x + 1.0, y)
    assert world.try_pick(x + 1.0, y)[0] == "picked"


def test_place_onto_an_occupied_hole_is_blocked(world):
    first = pick(world, 1)
    x, y = world.ws.hole_xy(5, "c")
    assert world.try_place(first, x, y)[0] == "inserted"

    second = pick(world, 2)
    result, holes = world.try_place(second, x, y)
    assert result == "blocked"
    assert holes == []
    assert world.find("c2").state == "held"


def test_jumper_rail_reaches_the_ground_rail(world):
    ref = pick(world, 8)
    x, y = world.ws.hole_xy(10, "a")
    result, holes = world.try_place(ref, x, y)
    assert result == "inserted"
    assert [(h.row, h.col) for h in holes] == [(10, "a"), (10, "RAIL_T_NEG")]


def build_demo(world: World) -> None:
    """resistor R5L-R9L, LED R9L-R10L, jumper R10L-RAIL_T_NEG."""
    world.try_place(pick(world, 1), *world.ws.hole_xy(5, "c"))
    world.try_place(pick(world, 4), *world.ws.hole_xy(9, "d"))
    world.try_place(pick(world, 8), *world.ws.hole_xy(10, "a"))


def test_netlist_of_the_demo_circuit(world):
    build_demo(world)
    world.set_pin_mode(17, "out")
    world.set_pin_level(17, 1)
    deck = world.netlist()
    lines = [line.strip() for line in deck.splitlines()]

    assert ".model LED_RED D(IS=1e-18 N=1.8 RS=1 BV=5 CJO=10p)" in lines
    assert "Vgpio17 n_gpio17 0 DC 3.3" in lines
    assert "Rgpio17 n_gpio17 R5L 40" in lines
    assert "Rc1 R5L R9L 330" in lines
    assert "Dc4 R9L R10L LED_RED" in lines
    assert "Rc8 R10L RAIL_T_NEG 0.01" in lines
    assert "Rgnd_RAIL_T_NEG RAIL_T_NEG 0 0.001" in lines
    assert "V3V3 RAIL_T_POS 0 DC 3.3" in lines
    assert "print @Dc4[id]" in lines
    # every net gets a tie so .op converges
    for net in ("R5L", "R9L", "R10L", "RAIL_T_NEG", "n_gpio17"):
        assert f"Rtie_{net} {net} 0 1G" in lines
    assert deck.rstrip().endswith("quit\n.endc\n.end")


def test_a_low_gpio_emits_a_zero_volt_source(world):
    build_demo(world)
    world.set_pin_mode(17, "out")
    world.set_pin_level(17, 0)
    assert "Vgpio17 n_gpio17 0 DC 0" in world.netlist()


def test_an_input_gpio_drives_nothing(world):
    build_demo(world)
    assert "Vgpio17" not in world.netlist()


def test_set_level_on_an_input_pin_raises(world):
    with pytest.raises(ValueError):
        world.set_pin_level(17, 1)


def test_pins_cover_the_harness(world):
    assert [p.gpio for p in world.pins()] == [17, 22, 23, 27]
    assert {p.net for p in world.pins()} == {"R5L", "R10L", "R15L", "R20L"}
    assert all(p.mode == "in" for p in world.pins())


def test_snapshot_carries_the_circuit(world):
    from hwctl.arm.sim import SimArm

    build_demo(world)
    world.set_pin_mode(17, "out")
    world.set_pin_level(17, 1)
    snap = world.snapshot(SimArm(world).status(), caption="demo")
    assert snap.caption == "demo"
    assert snap.circuit is not None and snap.circuit.leds["c4"] == "on"
    assert snap.circuit.brightness("c4") > 0.1
    assert len(snap.cartridges) == 8
