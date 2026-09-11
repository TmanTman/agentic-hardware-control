"""Tests for hwctl.viz (render, Recorder) and hwctl.camera.sim.

Builds a WorldSnapshot by hand from configs/workspace.yaml so it does not
depend on hwctl.world or hwctl.config (those are owned by another role and
may not exist yet).
"""

from __future__ import annotations

from pathlib import Path

import yaml
from PIL import Image as PILImage

from hwctl.camera.sim import SimCamera
from hwctl.schemas import (
    ArmStatus,
    BoardGeometry,
    CartridgeRef,
    CartridgeSpec,
    CircuitResult,
    HoleRef,
    PinState,
    PlacedCartridge,
    TraySlot,
    WorldSnapshot,
)
from hwctl.viz import Recorder, render
from hwctl.viz.render import _bbox, _hole_xy, _transform

WORKSPACE_YAML = Path(__file__).resolve().parents[1] / "configs" / "workspace.yaml"


def _load_workspace() -> dict:
    return yaml.safe_load(WORKSPACE_YAML.read_text())


def _board(cfg: dict) -> BoardGeometry:
    return BoardGeometry(**cfg["board"])


def _cartridge_specs(cfg: dict) -> dict[str, CartridgeSpec]:
    specs = {}
    for name, spec in cfg["cartridges"].items():
        specs[name] = CartridgeSpec(
            type=name,
            pins=[tuple(p) for p in spec["pins"]],
            spice=spec["spice"],
            pin_names=spec.get("pin_names"),
        )
    return specs


def _tray(cfg: dict) -> list[TraySlot]:
    y = cfg["tray"]["y_mm"]
    return [
        TraySlot(id=s["id"], x_mm=s["x_mm"], y_mm=y, cartridge=s["cartridge"])
        for s in cfg["tray"]["slots"]
    ]


def _build_snapshot() -> tuple[WorldSnapshot, dict[str, CartridgeSpec], dict]:
    cfg = _load_workspace()
    board = _board(cfg)
    cartridges = _cartridge_specs(cfg)
    tray = _tray(cfg)

    r_x, r_y = _hole_xy(board, 5, "c")
    resistor = PlacedCartridge(
        ref=CartridgeRef(id="c1", type="resistor_330"),
        state="inserted",
        x_mm=r_x,
        y_mm=r_y,
        pin0=HoleRef(row=5, col="c"),
        pin_holes=[HoleRef(row=5, col="c"), HoleRef(row=9, col="c")],
    )
    led = PlacedCartridge(
        ref=CartridgeRef(id="c4", type="led_red"),
        state="inserted",
        x_mm=_hole_xy(board, 9, "d")[0],
        y_mm=_hole_xy(board, 9, "d")[1],
        pin0=HoleRef(row=9, col="d"),
        pin_holes=[HoleRef(row=9, col="d"), HoleRef(row=10, col="d")],
    )
    jumper = PlacedCartridge(
        ref=CartridgeRef(id="c8", type="jumper_rail"),
        state="inserted",
        x_mm=_hole_xy(board, 10, "a")[0],
        y_mm=_hole_xy(board, 10, "a")[1],
        pin0=HoleRef(row=10, col="a"),
        pin_holes=[HoleRef(row=10, col="a"), HoleRef(row=10, col="RAIL_T_NEG")],
    )
    tray_led = PlacedCartridge(
        ref=CartridgeRef(id="c5b", type="led_red"),
        state="tray",
        x_mm=70.0,
        y_mm=cfg["tray"]["y_mm"],
    )
    held_led = PlacedCartridge(
        ref=CartridgeRef(id="c5", type="led_red"),
        state="held",
        x_mm=55.0,
        y_mm=cfg["tray"]["y_mm"],
    )

    arm = ArmStatus(
        x_mm=55.0,
        y_mm=cfg["tray"]["y_mm"],
        lifted=True,
        gripper="closed",
        held=CartridgeRef(id="c5", type="led_red"),
        event="picked",
    )
    pins = [PinState(gpio=17, mode="out", level=1, net="R5L")]
    circuit = CircuitResult(
        backend="python",
        node_voltages={"R5L": 3.1},
        led_currents_ma={"c4": 4.4},
        leds={"c4": "on"},
    )
    snap = WorldSnapshot(
        board=board,
        tray=tray,
        cartridges=[resistor, led, jumper, tray_led, held_led],
        arm=arm,
        pins=pins,
        circuit=circuit,
        caption="test snapshot",
    )
    return snap, cartridges, cfg


def test_build_snapshot_sane():
    snap, cartridges, _cfg = _build_snapshot()
    assert snap.cartridges[0].x_mm == 10.16
    assert snap.cartridges[0].y_mm == 5.08
    assert "led_red" in cartridges


def test_render_size_and_type():
    snap, cartridges, _ = _build_snapshot()
    img = render(snap, cartridges)
    assert img.mode == "RGB"

    bbox = _bbox(snap)
    _, expected_w, expected_h = _transform(bbox, margin_mm=8.0, px_per_mm=5.0)
    assert img.size == (expected_w, expected_h)


def test_led_glows_when_on():
    snap, cartridges, _ = _build_snapshot()
    off_circuit = snap.circuit.model_copy(
        update={"leds": {"c4": "off"}, "led_currents_ma": {"c4": 0.0}}
    )
    snap_off = snap.model_copy(update={"circuit": off_circuit})

    img_on = render(snap, cartridges)
    img_off = render(snap_off, cartridges)
    assert img_on.size == img_off.size

    board = snap.board
    ax, ay = _hole_xy(board, 9, "d")
    bx, by = _hole_xy(board, 10, "d")
    mid_mm = ((ax + bx) / 2, (ay + by) / 2)
    to_px, _, _ = _transform(_bbox(snap), margin_mm=8.0, px_per_mm=5.0)
    cx, cy = to_px(*mid_mm)
    # sample just outside the solid LED disc, inside the glow halo
    sample = (int(cx) + 12, int(cy))

    on_px = img_on.getpixel(sample)
    off_px = img_off.getpixel(sample)
    on_redness = on_px[0] - on_px[2]
    off_redness = off_px[0] - off_px[2]
    assert on_redness > off_redness


def test_recorder_writes_log_and_gif(tmp_path):
    snap, cartridges, _ = _build_snapshot()
    n = 4
    with Recorder(tmp_path, name="test", fps=2.0) as rec:
        for i in range(n):
            status = ArmStatus(x_mm=float(i), y_mm=0.0, lifted=True, gripper="open", event="moved")
            # vary the frame content per call -- Pillow's GIF encoder collapses
            # runs of pixel-identical frames, so a static snap would under-count.
            frame_snap = snap.model_copy(update={"caption": f"frame {i}"})
            rec.record(
                "arm", "move_to", {"x_mm": float(i), "y_mm": 0.0}, status, frame_snap, cartridges
            )
        gif_path = rec.close()

    commands_path = tmp_path / "commands.jsonl"
    lines = commands_path.read_text().strip().splitlines()
    assert len(lines) == n

    assert gif_path.exists()
    assert gif_path.stat().st_size < 5_000_000
    with PILImage.open(gif_path) as gif:
        assert gif.n_frames == n

    frame_files = list((tmp_path / "frames").glob("*.png"))
    assert len(frame_files) == n


def test_sim_camera_capture():
    snap, cartridges, _ = _build_snapshot()
    camera = SimCamera(lambda: snap, cartridges, px_per_mm=4.0)
    img = camera.capture()
    assert img.note == "sim"
    assert img.t > 0
    assert len(img.png) > 0

    from io import BytesIO

    decoded = PILImage.open(BytesIO(img.png))
    assert decoded.size == (img.width, img.height)
