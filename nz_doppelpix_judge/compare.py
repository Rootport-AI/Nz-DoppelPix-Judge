from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PIL import Image

from nz_doppelpix_judge.image_io import load_rgb, resize_pair
from nz_doppelpix_judge.metrics import (
    compute_clip_score,
    compute_fid,
    compute_image_reward,
    compute_lpips_alex,
    compute_lpips_vgg,
    compute_psnr,
    compute_ssim_skimage,
    compute_ssim_wang,
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


def _metric_settings_notes(enable_clip: bool, enable_image_reward: bool) -> list[str]:
    notes = [
        "Image preprocessing: PNG opened as RGB; if sizes differ, both images are resized to the smaller shared width/height with PIL Lanczos.",
        "Metric settings: LPIPS - AlexNet=lpips.LPIPS(net='alex'), RGB [0,255] -> [0,1] -> [-1,1].",
        "Metric settings: LPIPS - VGG=lpips.LPIPS(net='vgg'), RGB [0,255] -> [0,1] -> [-1,1].",
        "Metric settings: SSIM - win size 7 (skimage)=skimage.structural_similarity(channel_axis=2, data_range=255, win_size=7).",
        "Metric settings: SSIM - win size 11 (Wang)=skimage.structural_similarity(channel_axis=2, data_range=255, gaussian_weights=True, sigma=1.5, use_sample_covariance=False).",
        "Metric settings: PSNR=skimage.peak_signal_noise_ratio(data_range=255).",
        "Metric settings: Experimental / FID-like=torchvision Inception_V3_Weights.DEFAULT, fc=Identity; single-pair score is squared L2 distance between Inception features.",
    ]
    if enable_clip:
        notes.append("Metric settings: CLIP Score=open_clip ViT-B-32 pretrained='openai', score=100*cosine(image,text).")
    if enable_image_reward:
        notes.append("Metric settings: ImageReward=ImageReward-v1.0.")
    return notes


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
        ("LPIPS - AlexNet", "lower is more similar", compute_lpips_alex),
        ("LPIPS - VGG", "lower is more similar", compute_lpips_vgg),
        ("SSIM - win size 7 (skimage)", "higher is more similar", compute_ssim_skimage),
        ("SSIM - win size 11 (Wang)", "higher is more similar", compute_ssim_wang),
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
    notes.extend(_metric_settings_notes(enable_clip, enable_image_reward))
    return ComparisonResult(rows=rows, notes=notes, prompt_info=prompt_info)
