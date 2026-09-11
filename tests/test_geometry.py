"""Hole lookup: mm <-> (row, col), net naming, and snapping."""

from __future__ import annotations

import pytest

from hwctl.config import load_workspace
from hwctl.world import nearest_hole, snap

PITCH = 2.54


@pytest.fixture(scope="module")
def ws():
    return load_workspace()


def test_origin_is_hole_1a(ws):
    assert ws.hole_xy(1, "a") == (0.0, 0.0)


def test_hole_xy_row_and_column(ws):
    x, y = ws.hole_xy(5, "c")
    assert x == pytest.approx(4 * PITCH)
    assert y == pytest.approx(2 * PITCH)


def test_hole_xy_right_bank_has_the_column_gap(ws):
    _, y = ws.hole_xy(5, "f")
    assert y == pytest.approx(7 * PITCH)


def test_rail_holes(ws):
    x, y = ws.hole_xy(10, "RAIL_T_NEG")
    assert x == pytest.approx(9 * PITCH)
    assert y == pytest.approx(-3 * PITCH)


def test_unknown_column_raises(ws):
    with pytest.raises(KeyError):
        ws.hole_xy(1, "z")


def test_net_of(ws):
    assert ws.net_of(5, "a") == "R5L"
    assert ws.net_of(5, "e") == "R5L"
    assert ws.net_of(5, "f") == "R5R"
    assert ws.net_of(9, "j") == "R9R"
    assert ws.net_of(10, "RAIL_T_NEG") == "RAIL_T_NEG"


def test_nearest_hole_snaps_to_the_closest_centre(ws):
    hx, hy = ws.hole_xy(5, "c")
    hole, dist = nearest_hole(ws, hx + 0.2, hy - 0.1)
    assert (hole.row, hole.col) == (5, "c")
    assert dist == pytest.approx(0.2236, abs=1e-3)


def test_nearest_hole_finds_rails(ws):
    hx, hy = ws.hole_xy(20, "RAIL_B_NEG")
    hole, dist = nearest_hole(ws, hx, hy + 0.3)
    assert (hole.row, hole.col) == (20, "RAIL_B_NEG")
    assert dist == pytest.approx(0.3)


def test_nearest_hole_off_the_board_is_none(ws):
    assert nearest_hole(ws, -5.0, 0.0) is None
    assert nearest_hole(ws, ws.board.rows * PITCH + 5.0, 0.0) is None


def test_snap_respects_the_placement_tolerance(ws):
    hx, hy = ws.hole_xy(5, "c")
    tol = ws.board.placement_tolerance_mm
    assert snap(ws, hx + tol - 0.01, hy) is not None
    assert snap(ws, hx + tol + 0.01, hy) is None
