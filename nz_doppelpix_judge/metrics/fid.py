from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np
import torch
from PIL import Image
from scipy.linalg import sqrtm

from nz_doppelpix_judge.config import DEVICE


@lru_cache(maxsize=1)
def _fid_feature_extractor() -> Any:
    try:
        from torchvision.models import Inception_V3_Weights, inception_v3
    except ImportError as exc:
        raise RuntimeError("FID requires `torchvision`. Install requirements.txt.") from exc

    weights = Inception_V3_Weights.DEFAULT
    model = inception_v3(weights=weights, aux_logits=True, transform_input=False)
    model.fc = torch.nn.Identity()
    return model.to(DEVICE).eval(), weights.transforms()


def _fid_features(image: Image.Image) -> np.ndarray:
    model, transform = _fid_feature_extractor()
    tensor = transform(image).unsqueeze(0).to(DEVICE)
    with torch.no_grad():
        features = model(tensor)
    return features.detach().cpu().numpy().astype(np.float64)


def _frechet_distance(mu_a: np.ndarray, sigma_a: np.ndarray, mu_b: np.ndarray, sigma_b: np.ndarray) -> float:
    covmean = sqrtm(sigma_a.dot(sigma_b))
    if np.iscomplexobj(covmean):
        covmean = covmean.real
    diff = mu_a - mu_b
    return float(diff.dot(diff) + np.trace(sigma_a + sigma_b - 2.0 * covmean))


def compute_fid(a: Image.Image, b: Image.Image) -> float:
    # FID is designed for image sets. For a single pair, covariance is zero, so
    # this acts as an Inception-feature distance that remains useful for ranking.
    feat_a = _fid_features(a)
    feat_b = _fid_features(b)
    if feat_a.shape[0] == 1:
        diff = feat_a[0] - feat_b[0]
        return float(diff.dot(diff))
    mu_a = feat_a.mean(axis=0)
    mu_b = feat_b.mean(axis=0)
    sigma_a = np.atleast_2d(np.cov(feat_a, rowvar=False))
    sigma_b = np.atleast_2d(np.cov(feat_b, rowvar=False))
    return _frechet_distance(mu_a, sigma_a, mu_b, sigma_b)
