"""End-to-end: the v0.1 scripted demo runs, records, and the LED toggles."""

import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import demo_v0_1


def test_demo_records(tmp_path: Path) -> None:
    demo_v0_1.run(str(tmp_path))
    gif = tmp_path / "led-from-gpio17.gif"
    assert gif.exists() and gif.stat().st_size < 5_000_000
    assert Image.open(gif).n_frames > 10
    lines = [json.loads(line) for line in (tmp_path / "commands.jsonl").read_text().splitlines()]
    observes = [r for r in lines if r["device"] == "observe"]
    assert [o["result"]["leds"]["c4"] for o in observes] == ["on", "off", "on"]
    assert all(r["frame"] for r in lines)
