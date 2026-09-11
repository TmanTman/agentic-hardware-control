"""Top-down 2D renderer: WorldSnapshot -> PIL.Image.

Millimetre world coordinates, PIL pixel coordinates. World y is flipped onto
screen y (world y up, screen y down). Origin is the centre of hole (row 1,
col a); see `hwctl/schemas.py` and `docs/01-architecture.md` for the full
coordinate contract.

This module must not import `hwctl.world` or `hwctl.circuit` -- its only
input is `hwctl.schemas`.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from PIL import Image, ImageDraw, ImageFont

from hwctl.schemas import BoardGeometry, CartridgeSpec, PlacedCartridge, WorldSnapshot

# ---------------------------------------------------------------- constants

CAPTION_H = 24
TRAY_SLOT_W = 12.0
TRAY_SLOT_H = 14.0
BBOX_PAD_MM = 6.0

BOARD_BG = (222, 203, 164)  # light tan
HOLE_COLOR = (70, 60, 45)
GAP_COLOR = (245, 245, 240)
GRID_BG = (250, 248, 244)
LABEL_COLOR = (90, 80, 65)
CAPTION_BG = (235, 235, 235)
CAPTION_FG = (20, 20, 20)
ARM_COLOR = (30, 30, 200)
TRAY_STRIP_COLOR = (210, 210, 210)
TRAY_SLOT_BG = (235, 235, 235)
TRAY_SLOT_EMPTY = (200, 200, 200)

RESISTOR_BODY = (222, 196, 150)
RESISTOR_BANDS = [(200, 100, 20), (200, 100, 20), (110, 70, 30)]
LED_COLOR = (200, 30, 30)
LED_GLOW = (255, 90, 40)
JUMPER_COLOR = (20, 30, 110)
DROPPED_COLOR = (120, 120, 120, 140)

# Pi harness -> breadboard row, col 'a' (see configs/workspace.yaml). Not present
# in WorldSnapshot, so hardcoded per the viz spec.
GPIO_ROW = {17: 5, 27: 10, 22: 15, 23: 20}
RAIL_LABEL = {"RAIL_T_POS": "3V3", "RAIL_T_NEG": "GND", "RAIL_B_NEG": "GND"}
RAIL_COLOR = {"3V3": (200, 30, 30), "GND": (40, 40, 40)}

_NET_RE = re.compile(r"^R(\d+)[LR]$")


def _font(size: int = 10) -> ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _hole_xy(board: BoardGeometry, row: int, col: str) -> tuple[float, float]:
    """Centre of a hole in mm. `col` is a column letter or a rail net name."""
    p = board.pitch_mm
    if col in board.columns:
        return ((row - 1) * p, board.columns[col] * p)
    if col in board.rails:
        return ((row - 1) * p, board.rails[col] * p)
    raise KeyError(f"unknown column or rail: {col}")


def _cartridge_pins_mm(
    c: PlacedCartridge, spec: CartridgeSpec | None, board: BoardGeometry
) -> list[tuple[float, float]]:
    """World mm position of every pin of a placed cartridge."""
    if c.pin_holes:
        return [_hole_xy(board, h.row, h.col) for h in c.pin_holes]
    if spec is None:
        return [(c.x_mm, c.y_mm)]
    p = board.pitch_mm
    return [(c.x_mm + ro * p, c.y_mm + co * p) for ro, co in spec.pins]


def _category(cartridge_type: str) -> str:
    if cartridge_type.startswith("resistor"):
        return "resistor"
    if cartridge_type.startswith("led"):
        return "led"
    if cartridge_type.startswith("jumper"):
        return "jumper"
    return "other"


def _bbox(snap: WorldSnapshot) -> tuple[float, float, float, float]:
    """World-mm bounding box (x0, y0, x1, y1) of everything drawn."""
    board = snap.board
    p = board.pitch_mm
    xs = [0.0, (board.rows - 1) * p]
    ys = [v * p for v in board.columns.values()] + [v * p for v in board.rails.values()]
    for slot in snap.tray:
        xs += [slot.x_mm - TRAY_SLOT_W / 2, slot.x_mm + TRAY_SLOT_W / 2]
        ys += [slot.y_mm - TRAY_SLOT_H / 2, slot.y_mm + TRAY_SLOT_H / 2]
    for c in snap.cartridges:
        xs.append(c.x_mm)
        ys.append(c.y_mm)
    xs.append(snap.arm.x_mm)
    ys.append(snap.arm.y_mm)
    return (
        min(xs) - BBOX_PAD_MM,
        min(ys) - BBOX_PAD_MM,
        max(xs) + BBOX_PAD_MM,
        max(ys) + BBOX_PAD_MM,
    )


def _transform(
    bbox: tuple[float, float, float, float], margin_mm: float, px_per_mm: float
) -> tuple[Callable[[float, float], tuple[float, float]], int, int]:
    x0, y0, x1, y1 = bbox
    width = round((x1 - x0 + 2 * margin_mm) * px_per_mm)
    height = round((y1 - y0 + 2 * margin_mm) * px_per_mm) + CAPTION_H

    def to_px(x_mm: float, y_mm: float) -> tuple[float, float]:
        sx = (x_mm - x0 + margin_mm) * px_per_mm
        sy = CAPTION_H + (y1 - y_mm + margin_mm) * px_per_mm
        return (sx, sy)

    return to_px, width, height


def render(
    snap: WorldSnapshot,
    cartridges: dict[str, CartridgeSpec],
    *,
    px_per_mm: float = 5.0,
    margin_mm: float = 8.0,
) -> Image.Image:
    """Render a top-down 2D frame of `snap`. Returns an RGB image."""
    board = snap.board
    p = board.pitch_mm
    bbox = _bbox(snap)
    to_px, width, height = _transform(bbox, margin_mm, px_per_mm)

    canvas = Image.new("RGB", (max(width, 1), max(height, 1)), GRID_BG)
    draw = ImageDraw.Draw(canvas)
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    font = _font(10)
    small_font = _font(8)

    # --- board outline (hole-grid extent, rails included) -----------------
    all_y = list(board.columns.values()) + list(board.rails.values())
    bx0, by0 = to_px(-p / 2, min(all_y) * p - p / 2)
    bx1, by1 = to_px((board.rows - 1) * p + p / 2, max(all_y) * p + p / 2)
    draw.rectangle([bx0, by1, bx1, by0], fill=BOARD_BG, outline=(150, 130, 95))

    # centre gap between column e and f
    e_off, f_off = board.columns.get("e"), board.columns.get("f")
    if e_off is not None and f_off is not None:
        gx0, gy0 = to_px(-p / 2, e_off * p + p / 2)
        gx1, gy1 = to_px((board.rows - 1) * p + p / 2, f_off * p - p / 2)
        draw.rectangle([gx0, gy1, gx1, gy0], fill=GAP_COLOR)

    # --- hole grid dots -----------------------------------------------------
    dot_r = max(0.5, 0.35 * px_per_mm)
    for row in range(1, board.rows + 1):
        for col in list(board.columns) + list(board.rails):
            x, y = _hole_xy(board, row, col)
            sx, sy = to_px(x, y)
            draw.ellipse([sx - dot_r, sy - dot_r, sx + dot_r, sy + dot_r], fill=HOLE_COLOR)

    # --- row / column labels ------------------------------------------------
    for row in range(5, board.rows + 1, 5):
        x, _ = _hole_xy(board, row, "a")
        sx, sy = to_px(x, min(all_y) * p - p / 2)
        draw.text((sx, sy - 10), str(row), fill=LABEL_COLOR, font=small_font, anchor="ms")
    for col in board.columns:
        _, y = _hole_xy(board, 1, col)
        sx, sy = to_px(-p / 2 - 2, y)
        draw.text((sx, sy), col, fill=LABEL_COLOR, font=small_font, anchor="rm")

    # --- harness: GPIO pads + rail pads -------------------------------------
    for pin in snap.pins:
        if pin.gpio not in GPIO_ROW or not pin.net:
            continue
        m = _NET_RE.match(pin.net)
        row = int(m.group(1)) if m else GPIO_ROW[pin.gpio]
        x, y = _hole_xy(board, row, "a")
        sx, sy = to_px(x, y)
        on = pin.mode == "out" and pin.level == 1
        color = (60, 180, 70) if on else (150, 150, 150)
        r = 1.4 * px_per_mm
        draw.ellipse([sx - r, sy - r, sx + r, sy + r], outline=color, width=2)
        draw.text((sx + r + 2, sy), f"GPIO{pin.gpio}", fill=color, font=small_font, anchor="lm")

    for rail_name, label in RAIL_LABEL.items():
        if rail_name not in board.rails:
            continue
        x, y = _hole_xy(board, 1, rail_name)
        sx, sy = to_px(x, y)
        color = RAIL_COLOR.get(label, (80, 80, 80))
        r = 1.2 * px_per_mm
        draw.ellipse([sx - r, sy - r, sx + r, sy + r], fill=color)
        draw.text((sx + r + 2, sy), label, fill=color, font=small_font, anchor="lm")

    # --- tray -----------------------------------------------------------
    if snap.tray:
        tx0, ty0 = to_px(
            min(s.x_mm for s in snap.tray) - TRAY_SLOT_W,
            snap.tray[0].y_mm - TRAY_SLOT_H / 2 - 2,
        )
        tx1, ty1 = to_px(
            max(s.x_mm for s in snap.tray) + TRAY_SLOT_W,
            snap.tray[0].y_mm + TRAY_SLOT_H / 2 + 2,
        )
        draw.rectangle([tx0, ty1, tx1, ty0], fill=TRAY_STRIP_COLOR)
    for slot in snap.tray:
        sx, sy = to_px(slot.x_mm, slot.y_mm)
        half_w, half_h = TRAY_SLOT_W / 2 * px_per_mm, TRAY_SLOT_H / 2 * px_per_mm
        bg = TRAY_SLOT_BG if slot.cartridge else TRAY_SLOT_EMPTY
        draw.rounded_rectangle(
            [sx - half_w, sy - half_h, sx + half_w, sy + half_h],
            radius=3,
            fill=bg,
            outline=(120, 120, 120),
        )
        label = slot.cartridge or "empty"
        draw.text((sx, sy), label, fill=(30, 30, 30), font=small_font, anchor="mm")

    # --- cartridges -----------------------------------------------------
    for c in snap.cartridges:
        spec = cartridges.get(c.ref.type)
        cat = _category(c.ref.type)
        pins_mm = _cartridge_pins_mm(c, spec, board)
        pins_px = [to_px(x, y) for x, y in pins_mm]

        if c.state == "dropped":
            sx, sy = to_px(c.x_mm, c.y_mm)
            r = 4 * px_per_mm
            odraw.ellipse([sx - r, sy - r, sx + r, sy + r], fill=DROPPED_COLOR)
            odraw.line([(sx - r, sy - r), (sx + r, sy + r)], fill=(200, 30, 30, 220), width=2)
            odraw.line([(sx - r, sy + r), (sx + r, sy - r)], fill=(200, 30, 30, 220), width=2)
            odraw.text((sx, sy + r + 2), c.ref.type, fill=(60, 60, 60, 220), font=small_font)
            continue

        p0, p1 = pins_px[0], pins_px[-1]
        if cat == "resistor":
            draw.line([p0, p1], fill=RESISTOR_BODY, width=int(2.2 * px_per_mm))
            for i, band in enumerate(RESISTOR_BANDS):
                t = 0.3 + 0.15 * i
                bx = p0[0] + (p1[0] - p0[0]) * t
                by = p0[1] + (p1[1] - p0[1]) * t
                draw.line(
                    [(bx, by - px_per_mm), (bx, by + px_per_mm)],
                    fill=band,
                    width=max(1, int(px_per_mm / 2)),
                )
        elif cat == "jumper":
            draw.line([p0, p1], fill=JUMPER_COLOR, width=max(1, int(0.8 * px_per_mm)))
        elif cat == "led":
            mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
            brightness = snap.circuit.brightness(c.ref.id) if snap.circuit else 0.0
            lit = bool(snap.circuit) and snap.circuit.leds.get(c.ref.id) == "on"
            if lit:
                # Any LED above the 1 mA "on" threshold gets an obvious glow; the
                # radius keeps growing with current so 4 mA and 20 mA still differ.
                glow = 0.6 + 0.4 * brightness
                max_r = (5 + 8 * brightness) * px_per_mm
                for i in range(8, 0, -1):
                    r = max_r * i / 8
                    alpha = int(160 * glow * (1 - i / 9) ** 1.5)
                    odraw.ellipse([mx - r, my - r, mx + r, my + r], fill=(*LED_GLOW, alpha))
            r = 1.3 * px_per_mm
            body = (255, 120, 60) if lit else LED_COLOR
            draw.ellipse([mx - r, my - r, mx + r, my + r], fill=body, outline=(90, 10, 10))
            if lit:
                r2 = 0.6 * px_per_mm
                draw.ellipse([mx - r2, my - r2, mx + r2, my + r2], fill=(255, 240, 200))

        for sx, sy in pins_px:
            r = 0.6 * px_per_mm
            fill = ARM_COLOR if c.state == "held" else (30, 30, 30)
            draw.ellipse([sx - r, sy - r, sx + r, sy + r], fill=fill)

    # --- arm --------------------------------------------------------------
    ax, ay = to_px(snap.arm.x_mm, snap.arm.y_mm)
    cross = 1.5 * px_per_mm
    draw.line([(ax - cross, ay), (ax + cross, ay)], fill=ARM_COLOR, width=2)
    draw.line([(ax, ay - cross), (ax, ay + cross)], fill=ARM_COLOR, width=2)
    if snap.arm.lifted:
        r = 2.2 * px_per_mm
        draw.ellipse([ax - r, ay - r, ax + r, ay + r], outline=ARM_COLOR, width=2)
    else:
        r = 0.9 * px_per_mm
        draw.rectangle([ax - r, ay - r, ax + r, ay + r], fill=ARM_COLOR)
    spread = 1.8 * px_per_mm if snap.arm.gripper == "open" else 0.6 * px_per_mm
    draw.line(
        [(ax - spread, ay - cross - 2), (ax - spread * 0.3, ay - cross - 6)],
        fill=ARM_COLOR,
        width=2,
    )
    draw.line(
        [(ax + spread, ay - cross - 2), (ax + spread * 0.3, ay - cross - 6)],
        fill=ARM_COLOR,
        width=2,
    )

    final = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    fdraw = ImageDraw.Draw(final)

    # --- caption bar (drawn last, on top) ----------------------------------
    fdraw.rectangle([0, 0, width, CAPTION_H], fill=CAPTION_BG)
    caption = snap.caption
    if snap.circuit is not None:
        led_bits = [
            f"{cid}: {state} {snap.circuit.led_currents_ma.get(cid, 0.0):.1f}mA"
            for cid, state in snap.circuit.leds.items()
        ]
        caption = f"{caption}  [{snap.circuit.backend}] " + ", ".join(led_bits)
    fdraw.text((4, CAPTION_H / 2), caption.strip(), fill=CAPTION_FG, font=font, anchor="lm")

    return final
