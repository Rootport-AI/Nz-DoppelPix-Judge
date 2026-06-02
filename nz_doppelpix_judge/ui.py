from __future__ import annotations

import base64
import html
from io import BytesIO
from pathlib import Path
from typing import Iterator

import gradio as gr
from PIL import Image

from nz_doppelpix_judge.compare import compare_images
from nz_doppelpix_judge.config import APP_TITLE


RESULT_METRICS = [
    ("LPIPS - AlexNet", "LPIPS\n- AlexNet"),
    ("LPIPS - VGG", "LPIPS\n- VGG"),
    ("SSIM - win size 7 (skimage)", "SSIM\n- window 7\n(skimage)"),
    ("SSIM - win size 11 (Wang)", "SSIM\n- window 11\n(Wang)"),
    ("PSNR", "PSNR"),
    ("Experimental / FID-like", "Experimental\n/ FID-like"),
    ("CLIP Score (reference)", "CLIP Score\n(reference)"),
    ("CLIP Score (candidate)", "CLIP Score\n(candidate)"),
    ("ImageReward (reference)", "ImageReward\n(reference)"),
    ("ImageReward (candidate)", "ImageReward\n(candidate)"),
]


UI_CSS = """
.preview-card img { width: 100%; max-height: 360px; object-fit: contain; display: block; }
.preview-name { margin-top: 0.5rem; font-size: 0.9rem; opacity: 0.75; overflow-wrap: anywhere; }
.preview-empty, .preview-error { min-height: 220px; display: flex; align-items: center; justify-content: center; opacity: 0.7; border: 1px dashed var(--border-color-primary); border-radius: 8px; padding: 1rem; }
.results-wrap { overflow-x: auto; width: 100%; }
.results-table { border-collapse: collapse; width: 100%; min-width: 980px; table-layout: fixed; }
.results-table th, .results-table td { border: 1px solid var(--border-color-primary); padding: 0.65rem 0.5rem; text-align: center; vertical-align: middle; }
.results-table th { font-weight: 700; line-height: 1.2; white-space: normal; }
.results-table td { font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.results-table th:first-child, .results-table td:first-child { text-align: left; width: 14rem; }
.hidden-copy-source { display: none !important; }
.candidate-upload-spacer { min-height: 3.25rem; }
.copy-pulse { animation: copy-pulse 0.9s ease-out; }
@keyframes copy-pulse {
  0% { transform: scale(1); filter: brightness(1); }
  35% { transform: scale(1.02); filter: brightness(1.35); }
  100% { transform: scale(1); filter: brightness(1); }
}
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


def render_results(rows: list[dict[str, str]] | None = None) -> str:
    result_rows = rows or [{"File name": "-", **{metric_name: "-" for metric_name, _ in RESULT_METRICS}}]
    headers = "<th>File name</th>" + "".join(f"<th>{_header_html(label)}</th>" for _, label in RESULT_METRICS)
    body_rows = []
    for row in result_rows:
        cells = [f"<td>{html.escape(row.get('File name', '-'))}</td>"]
        cells.extend(f"<td>{html.escape(row.get(metric_name, '-'))}</td>" for metric_name, _ in RESULT_METRICS)
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    return (
        "<div class='results-wrap'>"
        "<table class='results-table'>"
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
        "</div>"
    )


def render_results_tsv(rows: list[dict[str, str]] | None = None) -> str:
    result_rows = rows or [{"File name": "-", **{metric_name: "-" for metric_name, _ in RESULT_METRICS}}]
    headers = ["File name", *[metric_name for metric_name, _ in RESULT_METRICS]]
    lines = ["\t".join(headers)]
    for row in result_rows:
        values = [row.get("File name", "-")]
        values.extend(row.get(metric_name, "-") for metric_name, _ in RESULT_METRICS)
        lines.append("\t".join(value.replace("\t", " ").replace("\r", " ").replace("\n", " ") for value in values))
    return "\n".join(lines)


def _candidate_directory(path: str) -> Path:
    cleaned = path.strip().strip('"').strip("'")
    directory = Path(cleaned).expanduser()
    if not directory.is_dir():
        raise gr.Error("Candidate PNG path must be a directory.")
    return directory


def _candidate_pngs(directory: Path) -> list[Path]:
    files = sorted(
        (path for path in directory.iterdir() if path.is_file() and path.suffix.lower() == ".png"),
        key=lambda path: path.name.lower(),
    )
    if not files:
        raise gr.Error("Candidate PNG directory does not contain PNG files.")
    return files


def _result_row(candidate_path: str | Path, scores_by_metric: dict[str, str], auto_mode: bool) -> dict[str, str]:
    row = {"File name": Path(candidate_path).name}
    for metric_name, _ in RESULT_METRICS:
        score = scores_by_metric.get(metric_name, "-")
        row[metric_name] = "error" if auto_mode and score.startswith("error:") else score
    return row


def _error_row(candidate_path: str | Path) -> dict[str, str]:
    return {"File name": Path(candidate_path).name, **{metric_name: "error" for metric_name, _ in RESULT_METRICS}}


def _mode_notes(mode: str, notes: list[str]) -> str:
    return "\n".join([f"Mode: {mode}", *notes])


def _console_progress(done: int, total: int, label: str, finished: bool = False) -> None:
    percent = int(done * 100 / total) if total else 100
    width = 28
    filled = round(width * done / total) if total else width
    bar = "#" * filled + "-" * (width - filled)
    suffix = label[:90]
    print(f"Auto Compare [{bar}] {percent:3d}% ({done}/{total}) {suffix}", end="\n" if finished else "\r", flush=True)


def judge(
    reference_path: str | None,
    candidate_path: str | None,
    candidate_directory_path: str,
    enable_clip: bool,
    enable_image_reward: bool,
) -> Iterator[tuple[str, str, str, str, str]]:
    if not reference_path:
        raise gr.Error("Please drop a Reference PNG image.")

    candidate_directory_path = candidate_directory_path.strip()
    auto_mode = bool(candidate_directory_path)
    prompt = ""

    if auto_mode:
        directory = _candidate_directory(candidate_directory_path)
        png_files = _candidate_pngs(directory)
        result_rows: list[dict[str, str]] = []
        total = len(png_files)
        print(f"Auto Compare started: {total} PNG files in {directory}", flush=True)
        _console_progress(0, total, "starting")

        for index, png_path in enumerate(png_files, start=1):
            _console_progress(index - 1, total, f"processing {png_path.name}")
            progress_note = f"Mode: Auto Compare\nProcessing {index}/{len(png_files)}: {png_path.name}"
            yield render_results(result_rows), render_results_tsv(result_rows), progress_note, prompt, preview_png(str(png_path))
            try:
                result = compare_images(reference_path, str(png_path), enable_clip, enable_image_reward)
                scores_by_metric = {row.name: row.score for row in result.rows}
                result_rows.append(_result_row(png_path, scores_by_metric, auto_mode=True))
                if enable_clip or enable_image_reward:
                    prompt = result.prompt_info.prompt
                notes = [
                    f"Auto Compare complete: {index}/{len(png_files)} files processed."
                    if index == len(png_files)
                    else f"Auto Compare progress: {index}/{len(png_files)} files processed.",
                    *result.notes,
                ]
                _console_progress(index, total, f"completed {png_path.name}", finished=index == total)
            except Exception as exc:
                result_rows.append(_error_row(png_path))
                notes = [
                    f"Auto Compare progress: {index}/{len(png_files)} files processed.",
                    f"Error while processing {png_path.name}: {exc}",
                ]
                _console_progress(index, total, f"error {png_path.name}", finished=index == total)
            yield render_results(result_rows), render_results_tsv(result_rows), _mode_notes("Auto Compare", notes), prompt, preview_png(str(png_path))
        return

    if not candidate_path:
        raise gr.Error("Please drop a Candidate PNG image or enter a Candidate PNG directory path.")

    result = compare_images(reference_path, candidate_path, enable_clip, enable_image_reward)
    scores_by_metric = {row.name: row.score for row in result.rows}
    rows = [_result_row(candidate_path, scores_by_metric, auto_mode=False)]
    prompt = result.prompt_info.prompt if enable_clip or enable_image_reward else ""
    yield render_results(rows), render_results_tsv(rows), _mode_notes("Manual Compare", result.notes), prompt, preview_png(candidate_path)


def lock_candidate_path(candidate_path: str | None) -> gr.update:
    return gr.update(interactive=not bool(candidate_path))


def lock_candidate_upload(candidate_directory_path: str) -> gr.update:
    path_is_set = bool(candidate_directory_path.strip())
    return gr.update(interactive=not path_is_set, visible=not path_is_set)


def candidate_upload_spacer(candidate_directory_path: str) -> str:
    if candidate_directory_path.strip():
        return "<div class='candidate-upload-spacer'></div>"
    return ""


def candidate_upload_spacer_visibility(candidate_directory_path: str) -> gr.update:
    return gr.update(value=candidate_upload_spacer(candidate_directory_path), visible=bool(candidate_directory_path.strip()))


def build_demo() -> gr.Blocks:
    with gr.Blocks(title=APP_TITLE) as demo:
        gr.Markdown(f"# {APP_TITLE}")
        with gr.Row():
            with gr.Column():
                gr.Textbox(label="Reference PNG path", value="", interactive=False, placeholder="Reserved for future use")
                reference = gr.File(label="Reference PNG", file_types=[".png"], type="filepath")
                reference_preview = gr.HTML(preview_png(None), label="Reference preview")
            with gr.Column():
                candidate_directory = gr.Textbox(label="Candidate PNG directory path", placeholder="Paste a directory path for Auto Compare mode")
                candidate = gr.File(label="Candidate PNG", file_types=[".png"], type="filepath")
                candidate_spacer = gr.HTML("", visible=False)
                candidate_preview = gr.HTML(preview_png(None), label="Candidate preview")
        with gr.Group():
            gr.Markdown("Prompt fidelity metrics")
            with gr.Row(equal_height=True):
                enable_clip = gr.Checkbox(label="Enable CLIP Score", value=False, scale=1)
                enable_image_reward = gr.Checkbox(label="Enable ImageReward", value=False, scale=1)
        run = gr.Button("Compare", variant="primary")
        results = gr.HTML(render_results())
        results_tsv = gr.Textbox(value=render_results_tsv(), visible=False, elem_classes=["hidden-copy-source"])
        copy_results = gr.Button("Copy table", elem_id="copy-table-button")
        notes = gr.Textbox(label="Notes", lines=9, interactive=False)
        prompt = gr.Textbox(label="Extracted prompt used for prompt fidelity metrics", lines=5, interactive=False)
        run.click(judge, [reference, candidate, candidate_directory, enable_clip, enable_image_reward], [results, results_tsv, notes, prompt, candidate_preview])
        copy_results.click(
            None,
            inputs=[results_tsv],
            outputs=None,
            js="""
            async (text) => {
                await navigator.clipboard.writeText(text || "");
                const root = document.querySelector("#copy-table-button");
                const button = root?.querySelector("button") || root;
                if (button) {
                    const original = button.textContent;
                    button.textContent = "Copied";
                    button.classList.remove("copy-pulse");
                    void button.offsetWidth;
                    button.classList.add("copy-pulse");
                    setTimeout(() => {
                        button.textContent = original;
                        button.classList.remove("copy-pulse");
                    }, 1200);
                }
                return [];
            }
            """,
        )
        reference.change(preview_png, reference, reference_preview)
        candidate.change(preview_png, candidate, candidate_preview)
        candidate.change(lock_candidate_path, candidate, candidate_directory)
        candidate_directory.change(lock_candidate_upload, candidate_directory, candidate)
        candidate_directory.change(candidate_upload_spacer_visibility, candidate_directory, candidate_spacer)
    return demo
