from __future__ import annotations

from pathlib import Path

from PIL import Image


def load_rgb(path: str | Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def resize_pair(a: Image.Image, b: Image.Image) -> tuple[Image.Image, Image.Image]:
    if a.size == b.size:
        return a, b
    target = (min(a.width, b.width), min(a.height, b.height))
    return a.resize(target, Image.Resampling.LANCZOS), b.resize(target, Image.Resampling.LANCZOS)
