from __future__ import annotations

import math

import numpy as np
from PIL import Image
from skimage.metrics import peak_signal_noise_ratio, structural_similarity


def compute_ssim(a: Image.Image, b: Image.Image) -> float:
    arr_a = np.asarray(a)
    arr_b = np.asarray(b)
    return float(structural_similarity(arr_a, arr_b, channel_axis=2, data_range=255))


def compute_psnr(a: Image.Image, b: Image.Image) -> float:
    arr_a = np.asarray(a)
    arr_b = np.asarray(b)
    score = peak_signal_noise_ratio(arr_a, arr_b, data_range=255)
    return float(score) if math.isfinite(score) else float("inf")
