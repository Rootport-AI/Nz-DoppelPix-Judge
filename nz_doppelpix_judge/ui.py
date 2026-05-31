from __future__ import annotations

import gradio as gr

from nz_doppelpix_judge.compare import compare_images
from nz_doppelpix_judge.config import APP_TITLE


def judge(
    reference_path: str | None,
    candidate_path: str | None,
    enable_clip: bool,
    enable_image_reward: bool,
) -> tuple[list[list[str]], str]:
    if not reference_path or not candidate_path:
        raise gr.Error("Please drop two PNG images.")

    result = compare_images(reference_path, candidate_path, enable_clip, enable_image_reward)
    rows = [[row.name, row.score, row.direction] for row in result.rows]
    return rows, "\n".join(result.notes)


def build_demo() -> gr.Blocks:
    with gr.Blocks(title=APP_TITLE) as demo:
        gr.Markdown(f"# {APP_TITLE}")
        with gr.Row():
            reference = gr.File(label="Reference PNG", file_types=[".png"], type="filepath")
            candidate = gr.File(label="Candidate PNG", file_types=[".png"], type="filepath")
        with gr.Row():
            enable_clip = gr.Checkbox(label="Enable CLIP Score", value=False)
            enable_image_reward = gr.Checkbox(label="Enable ImageReward", value=False)
        run = gr.Button("Compare", variant="primary")
        results = gr.Dataframe(headers=["Metric", "Score", "Direction"], datatype=["str", "str", "str"], interactive=False)
        notes = gr.Textbox(label="Notes", lines=4, interactive=False)
        run.click(judge, [reference, candidate, enable_clip, enable_image_reward], [results, notes])
    return demo
