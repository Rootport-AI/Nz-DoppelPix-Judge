from __future__ import annotations

import base64
import html
from io import BytesIO
from pathlib import Path

import gradio as gr
from PIL import Image

from nz_doppelpix_judge.compare import compare_images
from nz_doppelpix_judge.config import APP_TITLE


RESULT_METRICS = [
    ("LPIPS - AlexNet", "LPIPS\n- AlexNet⏬"),
    ("LPIPS - VGG", "LPIPS\n- VGG⏬"),
    ("SSIM - win size 7 (skimage)", "SSIM\n- window 7p\n(skimage)⏫"),
    ("SSIM - win size 11 (Wang)", "SSIM\n- window 11p\n(Wang)⏫"),
    ("PSNR", "PSNR⏫"),
    ("Experimental / FID-like", "Experimental\n/ FID-like⏬"),
    ("CLIP Score (reference)", "CLIP Score\n(reference)⏫"),
    ("CLIP Score (candidate)", "CLIP Score\n(candidate)⏫"),
    ("ImageReward (reference)", "ImageReward\n(reference)⏫"),
    ("ImageReward (candidate)", "ImageReward\n(candidate)⏫"),
]


UI_CSS = """
.preview-card img { width: 100%; max-height: 360px; object-fit: contain; display: block; }
.preview-name { margin-top: 0.5rem; font-size: 0.9rem; opacity: 0.75; overflow-wrap: anywhere; }
.preview-empty, .preview-error { min-height: 220px; display: flex; align-items: center; justify-content: center; opacity: 0.7; border: 1px dashed var(--border-color-primary); border-radius: 8px; padding: 1rem; }
.results-wrap { overflow-x: auto; width: 100%; }
.results-table { border-collapse: collapse; width: 100%; min-width: 900px; table-layout: fixed; }
.results-table th, .results-table td { border: 1px solid var(--border-color-primary); padding: 0.65rem 0.5rem; text-align: center; vertical-align: middle; }
.results-table th { font-weight: 700; line-height: 1.2; white-space: normal; }
.results-table td { font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
"""


def preview_png(path: str | None) -> str:
    if not path:
        return "<div class='preview-empty'>No image selected</div>"

    image_path = Path(path)
    try:
        with Image.open(image_path) as image:
            image = image.convert("RGB")
            image.thumbnail((640, 640), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            image.save(buffer, format="PNG")
    except Exception as exc:
        return f"<div class='preview-error'>Preview failed: {html.escape(str(exc))}</div>"

    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    filename = html.escape(image_path.name)
    return (
        "<div class='preview-card'>"
        f"<img alt='{filename}' src='data:image/png;base64,{encoded}' />"
        f"<div class='preview-name'>{filename}</div>"
        "</div>"
    )


def _header_html(label: str) -> str:
    return "<br>".join(html.escape(part) for part in label.split("\n"))


def render_results(scores_by_metric: dict[str, str] | None = None) -> str:
    scores = scores_by_metric or {}
    headers = "".join(f"<th>{_header_html(label)}</th>" for _, label in RESULT_METRICS)
    cells = "".join(f"<td>{html.escape(scores.get(metric_name, '-'))}</td>" for metric_name, _ in RESULT_METRICS)
    return (
        "<div class='results-wrap'>"
        "<table class='results-table'>"
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody><tr>{cells}</tr></tbody>"
        "</table>"
        "</div>"
    )


def judge(
    reference_path: str | None,
    candidate_path: str | None,
    enable_clip: bool,
    enable_image_reward: bool,
) -> tuple[str, str, str]:
    if not reference_path or not candidate_path:
        raise gr.Error("Please drop two PNG images.")

    result = compare_images(reference_path, candidate_path, enable_clip, enable_image_reward)
    scores_by_metric = {row.name: row.score for row in result.rows}
    prompt = result.prompt_info.prompt if enable_clip or enable_image_reward else ""
    return render_results(scores_by_metric), "\n".join(result.notes), prompt


def build_demo() -> gr.Blocks:
    with gr.Blocks(title=APP_TITLE) as demo:
        gr.Markdown(f"# {APP_TITLE}")
        with gr.Row():
            with gr.Column():
                reference = gr.File(label="Reference PNG", file_types=[".png"], type="filepath")
                reference_preview = gr.HTML(preview_png(None), label="Reference preview")
            with gr.Column():
                candidate = gr.File(label="Candidate PNG", file_types=[".png"], type="filepath")
                candidate_preview = gr.HTML(preview_png(None), label="Candidate preview")
        with gr.Group():
            gr.Markdown("Prompt fidelity metrics")
            with gr.Row(equal_height=True):
                enable_clip = gr.Checkbox(label="Enable CLIP Score", value=False, scale=1)
                enable_image_reward = gr.Checkbox(label="Enable ImageReward", value=False, scale=1)
        run = gr.Button("Compare", variant="primary")
        results = gr.HTML(render_results())
        notes = gr.Textbox(label="Notes", lines=9, interactive=False)
        prompt = gr.Textbox(label="Extracted prompt used for prompt fidelity metrics", lines=5, interactive=False)
        run.click(judge, [reference, candidate, enable_clip, enable_image_reward], [results, notes, prompt])
        reference.change(preview_png, reference, reference_preview)
        candidate.change(preview_png, candidate, candidate_preview)
    return demo
