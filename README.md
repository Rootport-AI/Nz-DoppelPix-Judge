# Nz DoppelPix Judge

Local Gradio Web GUI for comparing two PNG images with objective image similarity metrics.

The initial target is evaluating DiT inference acceleration techniques such as TeaCache and Spectrum, but the tool is intentionally generic: drop two images into the browser and compare them.

## Metrics

- LPIPS: lower is more similar
- SSIM: higher is more similar
- FID: lower is more similar
- PSNR: higher is more similar
- CLIP Score: optional, enabled only when checked
- ImageReward: optional, enabled only when checked

CLIP Score and ImageReward use the prompt embedded in PNG metadata. Forge neo/A1111-style `parameters` metadata is parsed by taking the positive prompt before `Negative prompt:` or `Steps:`.

Prompt extraction lives in `nz_doppelpix_judge/prompt_metadata.py`, separate from the Gradio app and metric code. Add a new `PromptExtractor` implementation there when supporting another metadata format such as ComfyUI.

## Project layout

- `app.py`: minimal local entry point
- `nz_doppelpix_judge/ui.py`: Gradio interface
- `nz_doppelpix_judge/compare.py`: comparison workflow and result shaping
- `nz_doppelpix_judge/image_io.py`: image loading and pair resizing
- `nz_doppelpix_judge/prompt_metadata.py`: PNG metadata prompt extraction
- `nz_doppelpix_judge/metrics/`: LPIPS, SSIM, FID, PSNR, CLIP Score, and ImageReward implementations
- `tests/`: focused regression tests

Note: FID is designed for image sets, not a single image pair. For one pair this app reports a degenerate FID/Inception-feature distance. It is still useful as a consistent ranking signal across the same experiment setup, but should not be compared directly with dataset-level FID numbers from papers.

## Setup

Recommended on Windows:

```bat
setup.bat
```

To skip optional CLIP Score and ImageReward dependencies:

```bat
setup.bat --core-only
```

Manual setup:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Optional prompt-alignment metrics:

```powershell
pip install -r requirements-optional.txt
```

The first run may download model weights for LPIPS, Inception, CLIP, or ImageReward.

## Run

Recommended on Windows:

```bat
run.bat
```

Manual run:

```powershell
python app.py
```

Open the local Gradio URL shown in the terminal. The app binds to `127.0.0.1`.

Result tables can be copied as TSV or downloaded as CSV. The CSV contains the same columns and rows as the copied table.

## License

Apache License 2.0. See [LICENSE](LICENSE).
