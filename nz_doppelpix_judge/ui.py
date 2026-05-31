from __future__ import annotations

import gradio as gr

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
            reference = gr.Image(label="Reference PNG", sources=["upload"], type="filepath", height=360)
            candidate = gr.Image(label="Candidate PNG", sources=["upload"], type="filepath", height=360)
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
    return demo
