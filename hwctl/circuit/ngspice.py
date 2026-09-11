"""Reference DC solver: shell out to `ngspice -b` and parse the `print` output.

ngspice lowercases every name it echoes, so the deck is scanned for the names
it was given and the parsed results are mapped back to that casing.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

_PRINT_V = re.compile(r"\bv\(([^)]+)\)", re.IGNORECASE)
_PRINT_I = re.compile(r"\bi\(([^)]+)\)", re.IGNORECASE)
_PRINT_AT = re.compile(r"@([^\[\]\s]+)\[", re.IGNORECASE)
_RESULT = re.compile(r"^\s*([^\s=]+)\s*=\s*([-+0-9.eE]+)\s*$")


def available() -> bool:
    """True when the ngspice binary is on PATH."""
    return shutil.which("ngspice") is not None


def _deck_nodes(deck: str) -> dict[str, str]:
    """lowercase node name -> the casing the deck used."""
    nodes: dict[str, str] = {}
    for line in deck.splitlines():
        if not line.strip().lower().startswith("print"):
            continue
        for name in _PRINT_V.findall(line):
            nodes[name.lower()] = name
    return nodes


def run_op(deck: str) -> tuple[dict[str, float], dict[str, float]]:
    """Run one operating-point analysis.

    Returns `(node_voltages, element_currents)`. Node keys use the deck's
    casing; element keys (voltage sources and diodes) are lowercase.
    """
    nodes = _deck_nodes(deck)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "deck.cir"
        path.write_text(deck)
        proc = subprocess.run(
            ["ngspice", "-b", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    if proc.returncode != 0:
        raise RuntimeError(f"ngspice failed ({proc.returncode}):\n{proc.stderr or proc.stdout}")

    voltages: dict[str, float] = {}
    currents: dict[str, float] = {}
    for line in proc.stdout.splitlines():
        m = _RESULT.match(line)
        if not m:
            continue
        key, raw = m.group(1).lower(), m.group(2)
        try:
            value = float(raw)
        except ValueError:
            continue
        mv = _PRINT_V.fullmatch(key)
        mi = _PRINT_I.fullmatch(key)
        ma = _PRINT_AT.match(key)
        if mv:
            name = mv.group(1)
            voltages[nodes.get(name, name)] = value
        elif mi:
            currents[mi.group(1)] = value
        elif ma:
            currents[ma.group(1)] = value
    return voltages, currents
