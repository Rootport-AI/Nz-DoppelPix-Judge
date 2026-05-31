from __future__ import annotations

import base64
import html
from io import BytesIO
from pathlib import Path

import gradio as gr
from PIL import Image

from nz_doppelpix_judge.compare import compare_images
from nz_doppelpix_judge.config import APP_TITLE


INITIAL_ROWS = [
    ["LPIPS - AlexNet", "-", "lower is more similar"],
    ["LPIPS - VGG", "-", "lower is more similar"],
    ["SSIM - win size 7 (skimage)", "-", "higher is more similar"],
    ["SSIM - win size 11 (Wang)", "-", "higher is more similar"],
    ["PSNR", "-", "higher is more similar"],
    ["Experimental / FID-like", "-", "lower is more similar"],
    ["CLIP Score", "-", "higher is more prompt-aligned"],
    ["ImageReward", "-", "higher is more preferred/aligned"],
]


UI_CSS = """
.preview-card img { width: 100%; max-height: 360px; object-fit: contain; display: block; }
.preview-name { margin-top: 0.5rem; font-size: 0.9rem; opacity: 0.75; overflow-wrap: anywhere; }
.preview-empty, .preview-error { min-height: 220px; display: flex; align-items: center; justify-content: center; opacity: 0.7; border: 1px dashed var(--border-color-primary); border-radius: 8px; padding: 1rem; }
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


def judge(
    reference_path: str | None,
    candidate_path: str | None,
    enable_clip: bool,
    enable_image_reward: bool,
) -> tuple[list[list[str]], str, str]:
    if not reference_path or not candidate_path:
        raise gr.Error("Please drop two PNG images.")

    result = compare_images(reference_path, candidate_path, enable_clip, enable_image_reward)
    rows = [[row.name, row.score, row.direction] for row in result.rows]
    prompt = result.prompt_info.prompt if enable_clip or enable_image_reward else ""
    return rows, "\n".join(result.notes), prompt


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
        results = gr.Dataframe(
            value=INITIAL_ROWS,
            headers=["Metric", "Score", "Direction"],
            datatype=["str", "str", "str"],
            interactive=False,
        )
        notes = gr.Textbox(label="Notes", lines=9, interactive=False)
        prompt = gr.Textbox(label="Extracted prompt used for prompt fidelity metrics", lines=5, interactive=False)
        run.click(judge, [reference, candidate, enable_clip, enable_image_reward], [results, notes, prompt])
        reference.change(preview_png, reference, reference_preview)
        candidate.change(preview_png, candidate, candidate_preview)
    return demo
