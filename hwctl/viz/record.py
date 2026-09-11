"""Recorder: turns a sequence of device calls into `commands.jsonl` + a GIF.

One frame is rendered (via `hwctl.viz.render.render`) per `record()` call so a
run can be watched back or replayed from `commands.jsonl`. See
`docs/01-architecture.md` ("Visualisation and recording") and `CLAUDE.md`
("Recordings") for what a `recordings/vX.Y.Z/` directory must contain.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Self

from PIL import Image
from pydantic import BaseModel

from hwctl.schemas import CartridgeSpec, CommandRecord, WorldSnapshot

from .render import render

_BLANK = Image.new("RGB", (2, 2), (255, 255, 255))


def _dump_result(result: Any) -> dict[str, Any] | str | None:
    if isinstance(result, BaseModel):
        return result.model_dump(mode="json")
    if result is None or isinstance(result, (dict, str)):
        return result
    return str(result)


class Recorder:
    """Collects rendered frames + a command log, and writes the GIF on close()."""

    def __init__(
        self,
        out_dir: str | Path,
        name: str = "run",
        *,
        keep_frames: bool = True,
        max_gif_bytes: int = 5_000_000,
        fps: float = 2.0,
    ) -> None:
        self.out_dir = Path(out_dir)
        self.name = name
        self.keep_frames = keep_frames
        self.max_gif_bytes = max_gif_bytes
        self.fps = fps

        self.out_dir.mkdir(parents=True, exist_ok=True)
        if self.keep_frames:
            (self.out_dir / "frames").mkdir(parents=True, exist_ok=True)

        self.seq = 0
        self._frames: list[Image.Image] = []
        self._closed = False
        self._gif_path = self.out_dir / f"{self.name}.gif"
        self._commands_path = self.out_dir / "commands.jsonl"
        self._commands_file = self._commands_path.open("w", encoding="utf-8")

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ frames

    def _render(
        self, snap: WorldSnapshot | None, cartridges: dict[str, CartridgeSpec] | None
    ) -> Image.Image | None:
        if snap is None:
            return None
        return render(snap, cartridges or {})

    def _stash_frame(self, img: Image.Image) -> str | None:
        self._frames.append(img)
        if not self.keep_frames:
            return None
        name = f"frames/{self.seq:04d}.png"
        img.save(self.out_dir / name)
        return name

    # ------------------------------------------------------------------ public

    def record(
        self,
        device: str,
        call: str,
        args: dict[str, Any],
        result: Any,
        snap: WorldSnapshot | None,
        cartridges: dict[str, CartridgeSpec] | None = None,
    ) -> CommandRecord:
        """Log one device call and, if `snap` is given, render + stash a frame."""
        self.seq += 1
        img = self._render(snap, cartridges)
        frame_name = self._stash_frame(img) if img is not None else None
        rec = CommandRecord(
            seq=self.seq,
            t=time.time(),
            device=device,  # type: ignore[arg-type]
            call=call,
            args=dict(args or {}),
            result=_dump_result(result),
            frame=frame_name,
        )
        self._commands_file.write(rec.model_dump_json() + "\n")
        self._commands_file.flush()
        return rec

    def frame(
        self,
        snap: WorldSnapshot,
        cartridges: dict[str, CartridgeSpec] | None = None,
        caption: str | None = None,
    ) -> Image.Image | None:
        """Stash an extra frame not tied to a device call (e.g. the final hold)."""
        self.seq += 1
        if caption is not None:
            snap = snap.model_copy(update={"caption": caption})
        img = self._render(snap, cartridges)
        if img is not None:
            self._stash_frame(img)
        return img

    def close(self) -> Path:
        """Write the GIF (shrinking it until it fits `max_gif_bytes`) and close the log."""
        if self._closed:
            return self._gif_path
        self._closed = True
        self._commands_file.close()

        frames = self._frames or [_BLANK]
        use_frames = frames
        scale = 1.0
        for _ in range(24):
            imgs = use_frames
            if scale < 1.0:
                imgs = [
                    im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))))
                    for im in use_frames
                ]
            imgs[0].save(
                self._gif_path,
                save_all=True,
                append_images=imgs[1:],
                duration=max(1, int(1000 / self.fps)),
                loop=0,
            )
            if self._gif_path.stat().st_size <= self.max_gif_bytes:
                break
            if scale > 0.15:
                scale *= 0.75
            elif len(use_frames) > 1:
                use_frames = use_frames[::2]
            else:
                break
        return self._gif_path
