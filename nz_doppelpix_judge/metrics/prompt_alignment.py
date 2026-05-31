from __future__ import annotations

from functools import lru_cache
from typing import Any

import torch
from PIL import Image

from nz_doppelpix_judge.config import DEVICE


@lru_cache(maxsize=1)
def _clip_model() -> Any:
    try:
        import open_clip
    except ImportError as exc:
        raise RuntimeError("CLIP Score requires `open_clip_torch`. Install requirements-optional.txt.") from exc

    model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="openai", device=DEVICE)
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    return model.eval(), preprocess, tokenizer


def compute_clip_score(image: Image.Image, prompt: str) -> float | None:
    if not prompt:
        return None
    model, preprocess, tokenizer = _clip_model()
    image_input = preprocess(image).unsqueeze(0).to(DEVICE)
    text_input = tokenizer([prompt]).to(DEVICE)
    with torch.no_grad():
        image_features = model.encode_image(image_input)
        text_features = model.encode_text(text_input)
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        score = (100.0 * image_features @ text_features.T).squeeze()
    return float(score.detach().cpu().item())


@lru_cache(maxsize=1)
def _image_reward_model() -> Any:
    try:
        import ImageReward as RM
    except ImportError as exc:
        raise RuntimeError("ImageReward requires the `ImageReward` package. Install requirements-optional.txt.") from exc
    return RM.load("ImageReward-v1.0")


def compute_image_reward(image: Image.Image, prompt: str) -> float | None:
    if not prompt:
        return None
    return float(_image_reward_model().score(prompt, image))
