from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PIL import Image

from nz_doppelpix_judge.image_io import load_rgb, resize_pair
from nz_doppelpix_judge.metrics import (
    compute_clip_score,
    compute_fid,
    compute_image_reward,
    compute_lpips,
    compute_psnr,
    compute_ssim,
)
from nz_doppelpix_judge.prompt_metadata import PromptInfo, extract_prompt


@dataclass(frozen=True)
class MetricRow:
    name: str
    score: str
    direction: str


@dataclass(frozen=True)
class ComparisonResult:
    rows: list[MetricRow]
    notes: list[str]
    prompt_info: PromptInfo


ImageMetric = Callable[[Image.Image, Image.Image], float]


def _fmt(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value == float("inf"):
        return "inf"
    return f"{value:.6f}"


def compare_images(
    reference_path: str,
    candidate_path: str,
    enable_clip: bool,
    enable_image_reward: bool,
) -> ComparisonResult:
    reference = load_rgb(reference_path)
    candidate = load_rgb(candidate_path)
    reference, candidate = resize_pair(reference, candidate)
    prompt_info = extract_prompt(reference_path)
    prompt_image_label = "Reference PNG"
    if not prompt_info.prompt:
        prompt_info = extract_prompt(candidate_path)
        prompt_image_label = "Candidate PNG"
    prompt = prompt_info.prompt

    rows: list[MetricRow] = []
    notes: list[str] = []
    if prompt:
        notes.append(f"Prompt source: {prompt_image_label} {prompt_info.source} ({prompt_info.extractor}). Reference PNG is preferred; Candidate PNG is used only if Reference has no prompt.")
    else:
        notes.append("Prompt source: none. CLIP Score and ImageReward need PNG prompt metadata.")

    metric_calls: list[tuple[str, str, ImageMetric]] = [
        ("LPIPS", "lower is more similar", compute_lpips),
        ("SSIM", "higher is more similar", compute_ssim),
        ("PSNR", "higher is more similar", compute_psnr),
        ("Experimental / FID-like", "lower is more similar", compute_fid),
    ]

    for name, direction, func in metric_calls:
        try:
            rows.append(MetricRow(name, _fmt(func(reference, candidate)), direction))
        except Exception as exc:
            rows.append(MetricRow(name, f"error: {exc}", direction))

    if enable_clip:
        for label, image in (("CLIP Score (reference)", reference), ("CLIP Score (candidate)", candidate)):
            try:
                rows.append(MetricRow(label, _fmt(compute_clip_score(image, prompt)), "higher is more prompt-aligned"))
            except Exception as exc:
                rows.append(MetricRow(label, f"error: {exc}", "higher is more prompt-aligned"))

    if enable_image_reward:
        for label, image in (("ImageReward (reference)", reference), ("ImageReward (candidate)", candidate)):
            try:
                rows.append(MetricRow(label, _fmt(compute_image_reward(image, prompt)), "higher is more preferred/aligned"))
            except Exception as exc:
                rows.append(MetricRow(label, f"error: {exc}", "higher is more preferred/aligned"))

    notes.append("FID for a single pair is a degenerate FID/Inception-feature distance; compare it consistently across experiments.")
    return ComparisonResult(rows=rows, notes=notes, prompt_info=prompt_info)
