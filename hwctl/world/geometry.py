"""Breadboard hole lookup: mm <-> (row, col).

Origin is the centre of hole (row 1, col a). x = (row - 1) * pitch,
y = offset(col) * pitch where the offsets come from `BoardGeometry`.
Rails are treated as extra columns with a hole on every row 1..rows.
"""

from __future__ import annotations

import math

from hwctl.schemas import BoardGeometry, HoleRef, Workspace


def hole_offsets(board: BoardGeometry) -> dict[str, int]:
    """Column letter / rail name -> y offset in pitches."""
    return {**board.columns, **board.rails}


def col_at_offset(board: BoardGeometry, offset: int) -> str | None:
    """Inverse of `hole_offsets`; None if no column sits at that offset."""
    for name, off in hole_offsets(board).items():
        if off == offset:
            return name
    return None


def nearest_hole(ws: Workspace, x_mm: float, y_mm: float) -> tuple[HoleRef, float] | None:
    """Nearest hole centre and its distance in mm, or None if x is off the board."""
    p = ws.board.pitch_mm
    row = round(x_mm / p) + 1
    if row < 1 or row > ws.board.rows:
        return None

    offsets = hole_offsets(ws.board)
    target = y_mm / p
    col = min(offsets, key=lambda name: (abs(offsets[name] - target), name))
    hx, hy = ws.hole_xy(row, col)
    return HoleRef(row=row, col=col), math.hypot(x_mm - hx, y_mm - hy)


def snap(ws: Workspace, x_mm: float, y_mm: float) -> HoleRef | None:
    """Nearest hole, but only within the board's placement tolerance."""
    found = nearest_hole(ws, x_mm, y_mm)
    if found is None:
        return None
    hole, dist = found
    return hole if dist <= ws.board.placement_tolerance_mm else None
