"""SPICE deck builder.

Walks the harness and every inserted cartridge and emits an `.op` deck in the
shape of the verified reference deck in `docs/01-architecture.md`.
"""

from __future__ import annotations

from hwctl.schemas import PinState, PlacedCartridge, Workspace

TIE_OHM = "1G"
"""Every net gets a 1 Gohm tie to ground so a floating node cannot stall `.op`."""


def element_name(spice_template: str, cartridge_id: str) -> str:
    """The SPICE element name a cartridge's template will produce (e.g. `Rc1`)."""
    return spice_template.strip().split()[0].format(id=cartridge_id)


def cartridge_nets(ws: Workspace, placed: PlacedCartridge) -> list[str]:
    return [ws.net_of(h.row, h.col) for h in placed.pin_holes]


def build_deck(
    ws: Workspace,
    cartridges: list[PlacedCartridge],
    pins: list[PinState],
) -> str:
    """Build the `.op` deck for the current world state."""
    body: list[str] = ["* hwctl world netlist"]
    body += [m for m in ws.spice_models]

    nets: set[str] = set()
    sources: list[str] = []
    diodes: list[str] = []

    def use(*names: str) -> None:
        for n in names:
            if n != "0":
                nets.add(n)

    # --- harness: driven GPIO pins, the 3V3 supply, the ground rails
    by_gpio = {p.gpio: p for p in pins}
    for key, harness_nets in ws.harness.items():
        if key.upper().startswith("GPIO"):
            pin = by_gpio.get(int(key[4:]))
            if pin is None or pin.mode != "out":
                continue
            name = key.lower()
            node = f"n_{name}"
            volts = pin.level * ws.gpio_model.high_v
            body.append(f"V{name} {node} 0 DC {volts:g}")
            sources.append(f"V{name}")
            use(node)
            for i, net in enumerate(harness_nets):
                suffix = "" if len(harness_nets) == 1 else f"_{i}"
                body.append(f"R{name}{suffix} {node} {net} {ws.gpio_model.series_ohm:g}")
                use(net)
        elif key.upper() in ("3V3", "5V"):
            volts = 3.3 if key.upper() == "3V3" else 5.0
            for i, net in enumerate(harness_nets):
                suffix = "" if len(harness_nets) == 1 else f"_{i}"
                body.append(f"V{key}{suffix} {net} 0 DC {volts:g}")
                sources.append(f"V{key}{suffix}")
                use(net)
        elif key.upper() == "GND":
            for net in harness_nets:
                body.append(f"Rgnd_{net} {net} 0 0.001")
                use(net)

    # --- inserted cartridges
    for placed in cartridges:
        if placed.state != "inserted":
            continue
        spec = ws.cartridges[placed.ref.type]
        pin_nets = cartridge_nets(ws, placed)
        kwargs = {f"n{i}": net for i, net in enumerate(pin_nets)}
        line = spec.spice.format(id=placed.ref.id, **kwargs)
        body.append(line)
        use(*pin_nets)
        if line.strip()[0].upper() == "D":
            diodes.append(line.strip().split()[0])

    # --- floating-net ties so .op always converges
    for net in sorted(nets):
        body.append(f"Rtie_{net} {net} 0 {TIE_OHM}")

    # --- control block
    body.append(".control")
    body.append("op")
    if nets:
        body.append("print " + " ".join(f"v({n})" for n in sorted(nets)))
    if sources:
        body.append("print " + " ".join(f"i({s})" for s in sources))
    for d in diodes:
        body.append(f"print @{d}[id]")
    body += ["quit", ".endc", ".end", ""]
    return "\n".join(body)
