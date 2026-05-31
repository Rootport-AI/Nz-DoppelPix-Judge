from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np
import torch
from PIL import Image

from nz_doppelpix_judge.config import DEVICE


def _image_tensor(image: Image.Image) -> torch.Tensor:
    arr = np.asarray(image).astype(np.float32) / 255.0
    tensor = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)
    return tensor


def _lpips_tensor(image: Image.Image) -> torch.Tensor:
    return _image_tensor(image).mul(2.0).sub(1.0).to(DEVICE)


@lru_cache(maxsize=1)
def _lpips_model() -> Any:
    try:
        import lpips
    except ImportError as exc:
        raise RuntimeError("LPIPS requires the `lpips` package. Install requirements.txt.") from exc

    model = lpips.LPIPS(net="alex")
    return model.to(DEVICE).eval()


def compute_lpips(a: Image.Image, b: Image.Image) -> float:
    with torch.no_grad():
        score = _lpips_model()(_lpips_tensor(a), _lpips_tensor(b))
    return float(score.detach().cpu().item())
