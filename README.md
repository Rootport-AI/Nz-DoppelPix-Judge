# Nz DoppelPix Judge

Local Gradio Web GUI for comparing two PNG images with objective image similarity metrics.

The initial target is evaluating DiT inference acceleration techniques such as TeaCache and Spectrum, but the tool is intentionally generic: drop two images into the browser and compare them.

The result table can be copied as TSV or downloaded as CSV. Both exports contain the same table columns and rows shown in the UI.

`run.bat` starts the app with `--listen`, so the server binds to all network interfaces. The UI's `local network` checkbox controls whether devices other than the local machine may access the app. It is off by default.

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
- `nz_doppelpix_judge/api.py`: HTTP API for automation jobs
- `nz_doppelpix_judge/ui.py`: Gradio interface
- `nz_doppelpix_judge/compare.py`: comparison workflow and result shaping
- `nz_doppelpix_judge/image_io.py`: image loading and pair resizing
- `nz_doppelpix_judge/prompt_metadata.py`: PNG metadata prompt extraction
- `nz_doppelpix_judge/metrics/`: LPIPS, SSIM, FID, PSNR, CLIP Score, and ImageReward implementations
- `tests/`: focused regression tests

Note: FID is designed for image sets, not a single image pair. For one pair this app reports a degenerate FID/Inception-feature distance. It is still useful as a consistent ranking signal across the same experiment setup, but should not be compared directly with dataset-level FID numbers from papers.

## Device selection

The app uses PyTorch CUDA automatically when the active virtual environment has a CUDA-enabled PyTorch build and `torch.cuda.is_available()` returns true. Otherwise it runs on CPU.

- LPIPS, Experimental / FID-like, and CLIP Score use the selected PyTorch device.
- SSIM and PSNR run on CPU through NumPy/scikit-image.
- ImageReward is loaded through the ImageReward package and is not explicitly moved by this app.

## Automation API

The app includes an HTTP API for local AI agents and scripts. The API automates the same comparison workflow as the UI without requiring browser control.

Workflow:

1. Create a comparison job with a Reference PNG, either a Candidate PNG or a server-local Candidate PNG directory path, and optional CLIP Score/ImageReward flags.
2. Poll the job status until it is completed.
3. Download the result CSV, using the same table columns and rows as the UI CSV download.

API jobs also print queued, started, progress, completed, and failed status lines to the server console.

Security requirement: API routes must use the same local network access control as the UI. When `local network` is off, API requests from other machines must be rejected.

Primary endpoints:

```text
POST /api/compare-jobs
GET  /api/compare-jobs/{job_id}
GET  /api/compare-jobs/{job_id}/results.csv
```

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

`run.bat` uses `python app.py --listen` and opens `http://127.0.0.1:7870` on the local machine.

Manual run:

```powershell
python app.py
```

To manually enable network binding:

```powershell
python app.py --listen
```

Open the local Gradio URL shown in the terminal. Without `--listen`, the app binds to `127.0.0.1`; with `--listen`, it binds to `0.0.0.0` and the `local network` checkbox controls access from other devices.

## License

Apache License 2.0. See [LICENSE](LICENSE).
